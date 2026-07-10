"""화자 구분 + 타임스탬프 + dataset.json 스키마 통합 (로컬 모델 버전)
   - ASR: faster-whisper small 기본값, 단어 단위 타임스탬프
     · WHISPER_BACKEND=mlx 설정 시 macOS Apple Silicon에서 mlx-whisper 사용 가능
     · WHISPER_MODEL 환경변수로 small, medium, large-v3 등을 선택
   - 화자 구분: sherpa-onnx (pyannote segmentation 3.0 + NeMo TitaNet)
     → 화자 turn 경계에 맞춰 whisper 단어를 재조립 (한 segment에 두 화자 섞임 방지)
   - API 키·HF 토큰 불필요, 완전 로컬 실행
   - repetition(hallucination) 정리, coverage 검증
"""
import os
import json
import platform
import numpy as np

IS_MAC = platform.system() == "Darwin"
SAMPLE_RATE = 16000
WHISPER_BACKEND = os.environ.get("WHISPER_BACKEND", "faster-whisper").strip().lower()
WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL",
    "mlx-community/whisper-large-v3-mlx" if WHISPER_BACKEND == "mlx" else "small",
)
NO_SPEECH_THRESHOLD = float(os.environ.get("WHISPER_NO_SPEECH_THRESHOLD", "0.98"))
_fw_model = None
INITIAL_PROMPT = (
    "이 통화는 보이스피싱 의심 통화이거나 정상 금융 상담 통화입니다. "
    "계좌, 이체, 대출, 개인정보 관련 용어에 유의해 정확히 전사하세요."
)

MODEL_DIR = os.path.expanduser("~/.cache/sherpa-onnx")
SEGMENTATION_MODEL = os.path.join(MODEL_DIR, "sherpa-onnx-pyannote-segmentation-3-0/model.onnx")
EMBEDDING_MODEL = os.path.join(MODEL_DIR, "nemo_en_titanet_large.onnx")

_diarizer = None


def has_diarization_models() -> bool:
    """화자 분리 ONNX 모델 파일이 준비되어 있는지 확인한다."""
    return os.path.exists(SEGMENTATION_MODEL) and os.path.exists(EMBEDDING_MODEL)


def get_diarizer(n_speakers: int):
    """sherpa-onnx 화자 분리 모델을 실제 분석 시점에만 로드한다."""
    import sherpa_onnx

    global _diarizer
    if _diarizer is None:
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=SEGMENTATION_MODEL
                ),
                num_threads=4,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=EMBEDDING_MODEL,
                num_threads=4,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(num_clusters=n_speakers),
            min_duration_on=0.2,
            min_duration_off=0.5,
        )
        _diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
    return _diarizer


def collapse_repetition(segments: list[dict], threshold: int = 3) -> list[dict]:
    """같은 텍스트가 연속으로 threshold회 이상 반복되면(hallucination loop) 첫 발화만 남긴다."""
    if not segments:
        return []

    cleaned = []
    run_start = 0
    for i in range(len(segments) + 1):
        if i < len(segments) and segments[i]["text"] == segments[run_start]["text"]:
            continue
        run_len = i - run_start
        if run_len >= threshold:
            print(f"  ⚠️ repetition loop 정리: '{segments[run_start]['text'][:20]}...' x{run_len} → 1개 유지")
            cleaned.append(segments[run_start])
        else:
            cleaned.extend(segments[run_start:i])
        run_start = i
    return cleaned


def load_audio_np(audio_file_path: str) -> np.ndarray:
    """16kHz mono float32 numpy 배열로 오디오를 로드한다."""
    if WHISPER_BACKEND == "mlx":
        from mlx_whisper.audio import load_audio

        return np.array(load_audio(audio_file_path))

    from faster_whisper.audio import decode_audio

    return decode_audio(audio_file_path, sampling_rate=SAMPLE_RATE)


def transcribe_words(audio: np.ndarray) -> list[dict]:
    """whisper로 전사하고 단어 단위 (start, end, word) 리스트를 반환한다."""
    if WHISPER_BACKEND == "mlx":
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=WHISPER_MODEL,
            language="ko",
            initial_prompt=INITIAL_PROMPT,
            condition_on_previous_text=False,  # 반복 루프 방지
            word_timestamps=True,
        )
        segments = [
            {"text": seg["text"].strip(), "words": seg.get("words", [])}
            for seg in result["segments"]
            if seg["text"].strip() and seg.get("no_speech_prob", 0) < NO_SPEECH_THRESHOLD
        ]
    else:
        from faster_whisper import WhisperModel

        global _fw_model
        if _fw_model is None:
            _fw_model = WhisperModel(
                WHISPER_MODEL,
                device=os.environ.get("FW_DEVICE", "cpu"),
                compute_type=os.environ.get("FW_COMPUTE", "int8"),
            )
        fw_segments, _ = _fw_model.transcribe(
            audio,
            language="ko",
            initial_prompt=INITIAL_PROMPT,
            condition_on_previous_text=False,  # 이전 문맥 반복으로 생기는 환각 문장 방지
            word_timestamps=True,
            vad_filter=False,
        )
        segments = []
        for seg in fw_segments:
            text = seg.text.strip()
            if not text or seg.no_speech_prob >= NO_SPEECH_THRESHOLD:
                continue

            words = [{"word": w.word, "start": w.start, "end": w.end} for w in (seg.words or [])]
            if not words:
                # 단어 타임스탬프가 비어도 segment 텍스트는 탐지에 필요하므로 보존한다.
                words = [{"word": text, "start": seg.start, "end": seg.end}]
            segments.append({"text": text, "words": words})
    segments = collapse_repetition(segments)

    words = []
    for seg_idx, seg in enumerate(segments):
        for w in seg["words"]:
            words.append({"start": w["start"], "end": w["end"], "word": w["word"], "seg_idx": seg_idx})
    return words


def diarize_turns(audio: np.ndarray, n_speakers: int) -> list[dict]:
    """화자 turn 목록 [{'start', 'end', 'speaker'(int)}] 반환."""
    if not has_diarization_models():
        print("  [warn] sherpa-onnx 화자 분리 모델 파일이 없어 단일 화자로 처리합니다.")
        return []

    try:
        sd = get_diarizer(n_speakers)
        result = sd.process(audio).sort_by_start_time()
        return [{"start": r.start, "end": r.end, "speaker": r.speaker} for r in result]
    except Exception as exc:
        print(f"  [warn] 화자 분리 실패로 단일 화자로 처리합니다: {exc}")
        return []


def resolve_sentence_speakers(words: list[dict]) -> None:
    """whisper 문장 단위로 화자를 확정한다.

    화자가 겹쳐 말하는 구간에서는 turn이 잘게 쪼개져 단어별 배정이 튀므로,
    문장 안에서 충분히 긴(겹침 합 1초 이상, 2단어 이상) run만 진짜 화자 전환으로 인정하고
    나머지는 문장 전체의 화자별 겹침 총합이 큰 쪽(또는 인접한 확실한 run)으로 흡수한다.
    """
    by_seg = {}
    for w in words:
        by_seg.setdefault(w["seg_idx"], []).append(w)

    for seg_words in by_seg.values():
        # 문장 내 화자 run 계산
        runs = []  # [start_i, end_i, speaker]
        for i, w in enumerate(seg_words):
            if runs and runs[-1][2] == w["speaker"]:
                runs[-1][1] = i
            else:
                runs.append([i, i, w["speaker"]])

        def run_overlap(run):
            i, j, spk = run
            return sum(w["overlap"].get(spk, 0.0) for w in seg_words[i:j + 1])

        strong = [r for r in runs if r[1] - r[0] + 1 >= 2 and run_overlap(r) >= 1.0]

        if not strong:
            # 확실한 run이 없으면 문장 전체를 겹침 총합이 가장 큰 화자에게
            totals = {}
            for w in seg_words:
                for spk, ov in w["overlap"].items():
                    totals[spk] = totals.get(spk, 0.0) + ov
            if totals:
                winner = max(totals, key=totals.get)
                for w in seg_words:
                    w["speaker"] = winner
            continue

        # 약한 run은 시간상 가장 가까운 확실한 run의 화자로 흡수
        for r in runs:
            if r in strong:
                continue
            mid = (seg_words[r[0]]["start"] + seg_words[r[1]]["end"]) / 2
            nearest = min(
                strong,
                key=lambda s: min(abs(mid - seg_words[s[0]]["start"]), abs(mid - seg_words[s[1]]["end"])),
            )
            for w in seg_words[r[0]:r[1] + 1]:
                w["speaker"] = nearest[2]


def assign_words_to_turns(words: list[dict], turns: list[dict]) -> list[dict]:
    """각 단어를 겹치는 화자 turn에 배정하고, 화자가 이어지는 단어들을 segment로 재조립한다."""
    if not words:
        return []
    if not turns:
        for w in words:
            w["speaker"] = 0
    else:
        for w in words:
            w["overlap"] = {}  # 화자별 겹침 시간 합
            for t in turns:
                ov = min(w["end"], t["end"]) - max(w["start"], t["start"])
                if ov > 0:
                    w["overlap"][t["speaker"]] = w["overlap"].get(t["speaker"], 0.0) + ov
            if w["overlap"]:
                w["speaker"] = max(w["overlap"], key=w["overlap"].get)
            else:  # 겹치는 turn이 없으면 중심점이 가장 가까운 turn
                mid = (w["start"] + w["end"]) / 2
                nearest = min(turns, key=lambda t: min(abs(mid - t["start"]), abs(mid - t["end"])))
                w["speaker"] = nearest["speaker"]
        resolve_sentence_speakers(words)

    # 화자 등장 순서대로 화자A, 화자B, ... 이름 부여
    name_map = {}
    for w in words:
        if w["speaker"] not in name_map:
            name_map[w["speaker"]] = f"화자{chr(ord('A') + len(name_map))}"

    # 같은 화자·같은 whisper 문장 안에서 발화 간격이 짧으면 하나의 segment로 묶기
    segments = []
    cur = None
    for w in words:
        if (
            cur
            and w["speaker"] == cur["speaker_id"]
            and w["seg_idx"] == cur["seg_idx"]
            and w["start"] - cur["end"] <= 1.0
        ):
            cur["end"] = w["end"]
            cur["text"] += w["word"]
        else:
            if cur:
                segments.append(cur)
            cur = {
                "start": w["start"],
                "end": w["end"],
                "speaker_id": w["speaker"],
                "seg_idx": w["seg_idx"],
                "text": w["word"],
            }
    if cur:
        segments.append(cur)

    # 문장이 끝나지 않은 채 잘린 조각은 같은 화자의 다음 segment와 병합
    merged = []
    for s in segments:
        prev = merged[-1] if merged else None
        if (
            prev
            and s["speaker_id"] == prev["speaker_id"]
            and s["start"] - prev["end"] <= 1.0
            and not prev["text"].rstrip().endswith((".", "?", "!", "…"))
            and s["end"] - prev["start"] <= 20.0  # 병합 후 20초 초과 방지
        ):
            prev["end"] = s["end"]
            prev["text"] = prev["text"].rstrip() + " " + s["text"].strip()
        else:
            merged.append(s)

    return [
        {
            "start": float(round(s["start"], 2)),
            "end": float(round(s["end"], 2)),
            "speaker": name_map[s["speaker_id"]],
            "text": s["text"].strip(),
        }
        for s in merged
        if s["text"].strip()
    ]


def check_coverage(segments: list[dict], audio_duration_sec: float) -> None:
    if not segments:
        print(f"  ⚠️ 커버리지 경고: segment 0개 (오디오 길이 {audio_duration_sec:.1f}s)")
        return
    last_end = max(s.get("end", 0) for s in segments)
    gap = audio_duration_sec - last_end
    if gap > 15:
        print(f"  ⚠️ 커버리지 경고: 오디오 {audio_duration_sec:.1f}s, 마지막 발화 {last_end:.1f}s (누락 {gap:.1f}s 의심)")


def transcribe_with_speakers(audio_file_path: str, expected_speakers: int = 2) -> list[dict]:
    audio = load_audio_np(audio_file_path)
    duration = len(audio) / SAMPLE_RATE
    print(f"  [debug] 전체 길이: {duration:.1f}s")

    words = transcribe_words(audio)
    turns = diarize_turns(audio, n_speakers=expected_speakers)
    print(f"  [debug] 단어 {len(words)}개, 화자 turn {len(turns)}개")

    segments = assign_words_to_turns(words, turns)
    check_coverage(segments, duration)
    return segments


if __name__ == "__main__":
    import sys

    # 사용법: python -m backend.app.mp3_json [오디오 폴더 경로] [phishing_type]
    if len(sys.argv) > 1:
        TEST_DIR = sys.argv[1]
        PHISHING_TYPE = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        if IS_MAC:
            TEST_DIR = "/Users/seminy/Desktop/보이스피싱 데이터셋(금감원)/그놈 목소리(수사기관 사칭형)"
        else:
            TEST_DIR = os.path.expanduser("~/dataset/그놈 목소리(수사기관 사칭형)")                  # 원격 서버 데이터셋 경로
        PHISHING_TYPE = "수사기관 사칭형"
    LABEL = "phishing"                 # 이 폴더는 전부 보이스피싱 녹취
    OUTPUT_DIR = os.path.join(TEST_DIR, "results")                       # 결과 파일 저장 폴더
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    OUTPUT_JSON = os.path.join(OUTPUT_DIR, "dataset.json")

    # 중단된 실행 재개: 기존 결과가 있으면 이어서 처리
    dataset = []
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            dataset = json.load(f)
        print(f"기존 결과 {len(dataset)}개 call 로드 — 이어서 진행")
    done_ids = {c["call_id"] for c in dataset}

    audio_files = [f for f in sorted(os.listdir(TEST_DIR)) if f.lower().endswith((".mp3", ".wav"))]

    for idx, filename in enumerate(audio_files, 1):
        call_id = os.path.splitext(filename)[0]
        if call_id in done_ids:
            continue

        print(f"=== [{idx}/{len(audio_files)}] {filename} ===")
        segments_raw = transcribe_with_speakers(os.path.join(TEST_DIR, filename), expected_speakers=2)

        segments = [
            {
                "chunk_id": i + 1,
                "start_time": seg.get("start"),
                "end_time": seg.get("end"),
                "speaker": seg.get("speaker"),
                "text": seg.get("text", "").strip(),
                "matched_patterns": []
            }
            for i, seg in enumerate(segments_raw)
        ]

        dataset.append({
            "call_id": call_id,
            "label": LABEL,
            "phishing_type": PHISHING_TYPE,
            "segments": segments
        })
        print(f"발언 {len(segments)}개 추출\n")

        # 장시간 실행 대비: 파일 하나 끝날 때마다 결과 갱신 저장
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"✅ 총 {len(dataset)}개 call → {OUTPUT_JSON}")
