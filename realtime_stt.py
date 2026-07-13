"""실시간 통화 전사 (스트리밍 STT) — realtime_detector.py 의 입력(발화 청크)을 만든다.

mp3_json.py(배치 전사)와의 차이:
  - 파일 전체가 아니라 PCM 청크를 feed 받아 buffer 단위로 전사한다.
    buffer 끝 TAIL_SEC 은 문장이 잘렸을 수 있어 미확정으로 남기고,
    그 앞까지만 발화로 확정(commit)해 내보낸다.
  - 화자 구분: diarization 대신 채널 분리를 쓴다. 전화 오디오는 송신/수신이
    분리되므로 채널마다 ChannelTranscriber 인스턴스를 하나씩 두면 된다.
  - 프롬프트: "보이스피싱 의심 통화" 같은 판단 프레이밍을 빼고(정상 통화가
    대부분인 실시간에서 피싱 어휘 환청 → 오경보 유발) 중립 어휘 바이어스만 남긴다.
    이미 확정된 직전 전사 문맥을 프롬프트 뒤에 이어붙여 청크 간 일관성을 유지한다.

RealtimeDetector 연결 예:
    from realtime_detector import RealtimeDetector
    from realtime_stt import ChannelTranscriber

    det = RealtimeDetector(use_llm=True)
    tx = ChannelTranscriber("speaker_a")
    for pcm in audio_chunks():            # 16kHz mono float32
        for seg in tx.feed(pcm):
            risk = det.add(seg["text"], seg["speaker"])
    for seg in tx.flush():                # 통화 종료
        risk = det.add(seg["text"], seg["speaker"])
"""
import os
import platform
import subprocess

import numpy as np

IS_MAC = platform.system() == "Darwin"
SAMPLE_RATE = 16000

if IS_MAC:
    import mlx_whisper
    WHISPER_MODEL = "mlx-community/whisper-large-v3-mlx"
else:
    from faster_whisper import WhisperModel
    WHISPER_MODEL = "large-v3"
    _fw_model = None

# 판단 프레이밍 없는 중립 어휘 바이어스 (지시문은 whisper에 효과가 없다 —
# 프롬프트에 등장한 어휘/문체 쪽으로 디코딩이 편향될 뿐이다)
DOMAIN_PROMPT = (
    "여보세요, 안녕하세요. 금융 관련 전화 통화입니다. "
    "계좌, 이체, 대출, 개인정보, 검찰청, 금융감독원, 원격 제어 앱, "
    "안전 계좌, 상환, 명의 도용 같은 용어가 나올 수 있습니다."
)

PROCESS_SEC = 5.0        # buffer가 이만큼 쌓이면 전사 시도
TAIL_SEC = 2.0           # buffer 끝의 미확정 구간 (다음 회차에 재전사)
MAX_BUFFER_SEC = 30.0    # 침묵 등으로 확정이 안 나도 buffer가 이 이상 자라지 않게 강제 절단
MAX_CONTEXT_CHARS = 150  # 프롬프트에 이어붙일 직전 전사 문맥 길이


def _transcribe(audio: np.ndarray, prompt: str) -> list[dict]:
    """buffer를 전사해 단어 단위 (start, end, word, seg_idx) 리스트를 반환한다."""
    if IS_MAC:
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=WHISPER_MODEL,
            language="ko",
            initial_prompt=prompt,
            condition_on_previous_text=False,  # 반복 루프 방지
            word_timestamps=True,
        )
        segments = [
            {"text": seg["text"].strip(), "words": seg.get("words", [])}
            for seg in result["segments"]
            if seg["text"].strip() and seg.get("no_speech_prob", 0) <= 0.6
        ]
    else:
        global _fw_model
        if _fw_model is None:
            _fw_model = WhisperModel(
                WHISPER_MODEL,
                device="cuda",
                compute_type=os.environ.get("FW_COMPUTE", "float16"),
            )
        fw_segments, _ = _fw_model.transcribe(
            audio,
            language="ko",
            initial_prompt=prompt,
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=True,  # 침묵 구간 hallucination 억제
        )
        segments = [
            {
                "text": seg.text.strip(),
                "words": [{"word": w.word, "start": w.start, "end": w.end} for w in (seg.words or [])],
            }
            for seg in fw_segments
            if seg.text.strip() and seg.no_speech_prob <= 0.6
        ]

    # 같은 텍스트가 3회 이상 연속 반복되면(hallucination loop) 첫 발화만 남긴다
    cleaned, run_start = [], 0
    for i in range(len(segments) + 1):
        if i < len(segments) and segments[i]["text"] == segments[run_start]["text"]:
            continue
        run_len = i - run_start
        cleaned.extend([segments[run_start]] if run_len >= 3 else segments[run_start:i])
        run_start = i

    words = []
    for seg_idx, seg in enumerate(cleaned):
        for w in seg["words"]:
            words.append({"start": w["start"], "end": w["end"], "word": w["word"], "seg_idx": seg_idx})
    return words


class ChannelTranscriber:
    """한 채널(=한 화자)의 PCM 스트림을 받아 확정된 발화 segment를 내놓는다."""

    def __init__(self, speaker: str):
        self.speaker = speaker
        self.buffer = np.zeros(0, dtype=np.float32)
        self.offset = 0.0    # buffer[0]의 통화 시작 기준 절대 시각(초)
        self.context = ""    # 확정된 전사 누적 (프롬프트 문맥용)

    def feed(self, pcm: np.ndarray) -> list[dict]:
        """16kHz mono float32 청크를 추가하고, 새로 확정된 segment 목록을 반환한다."""
        self.buffer = np.concatenate([self.buffer, np.asarray(pcm, dtype=np.float32)])
        if len(self.buffer) / SAMPLE_RATE < PROCESS_SEC:
            return []
        return self._process(final=False)

    def flush(self) -> list[dict]:
        """통화 종료: 남은 buffer 전체를 확정한다."""
        if len(self.buffer) / SAMPLE_RATE < 0.3:
            return []
        return self._process(final=True)

    def _process(self, final: bool) -> list[dict]:
        duration = len(self.buffer) / SAMPLE_RATE
        prompt = DOMAIN_PROMPT + (" " + self.context if self.context else "")
        words = _transcribe(self.buffer, prompt)

        commit_until = duration if final else duration - TAIL_SEC
        committed = [w for w in words if w["end"] <= commit_until]
        base = self.offset  # 이번 buffer 단어 시각의 절대 기준점 (절단 전 값)

        # buffer 절단 지점: 마지막 확정 단어 끝. 확정이 없으면 침묵으로 보고
        # MAX_BUFFER_SEC 초과 시에만 강제 절단(끝 TAIL_SEC 은 보존).
        if committed:
            cut_sec = committed[-1]["end"]
        elif final:
            cut_sec = duration
        elif duration > MAX_BUFFER_SEC:
            cut_sec = duration - TAIL_SEC
        else:
            cut_sec = 0.0
        if cut_sec > 0:
            self.buffer = self.buffer[int(cut_sec * SAMPLE_RATE):]
            self.offset += cut_sec

        # 확정 단어를 whisper 문장(seg_idx) 단위로 묶어 segment로 만든다
        segments, cur = [], None
        for w in committed:
            if cur and w["seg_idx"] == cur["seg_idx"] and w["start"] - cur["end"] <= 1.0:
                cur["end"] = w["end"]
                cur["text"] += w["word"]
            else:
                if cur:
                    segments.append(cur)
                cur = dict(w)
                cur["text"] = w["word"]
        if cur:
            segments.append(cur)

        out = []
        for s in segments:
            text = s["text"].strip()
            if not text:
                continue
            out.append({
                "start": round(base + s["start"], 2),
                "end": round(base + s["end"], 2),
                "speaker": self.speaker,
                "text": text,
            })
            self.context = (self.context + " " + text)[-MAX_CONTEXT_CHARS:]
        return out


def load_channels(audio_file_path: str) -> list[np.ndarray]:
    """오디오를 채널별 16kHz float32 배열로 로드한다 (모노 1개 / 스테레오 2개)."""
    out = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", audio_file_path,
         "-f", "f32le", "-ac", "2", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True,
    ).stdout
    pcm = np.frombuffer(out, dtype=np.float32).reshape(-1, 2)
    left, right = pcm[:, 0].copy(), pcm[:, 1].copy()
    if np.array_equal(left, right):  # 원본이 모노면 ffmpeg가 양 채널에 복제한다
        return [left]
    return [left, right]


if __name__ == "__main__":
    import sys

    # 사용법: python realtime_stt.py <오디오 파일>
    # 파일을 0.5초 청크로 흘려보내며 확정되는 발화를 즉시 출력하는 데모.
    if len(sys.argv) < 2:
        sys.exit("사용법: python realtime_stt.py <오디오 파일>")

    channels = load_channels(sys.argv[1])
    speakers = ["speaker_a", "speaker_b"]
    txs = [ChannelTranscriber(speakers[i]) for i in range(len(channels))]
    print(f"채널 {len(channels)}개 감지 → 화자 {', '.join(t.speaker for t in txs)}")

    step = int(SAMPLE_RATE * 0.5)
    total = max(len(c) for c in channels)
    for pos in range(0, total, step):
        for tx, ch in zip(txs, channels):
            for seg in tx.feed(ch[pos:pos + step]):
                print(f"[{seg['start']:7.2f}–{seg['end']:7.2f}] {seg['speaker']}: {seg['text']}")
    for tx in txs:
        for seg in tx.flush():
            print(f"[{seg['start']:7.2f}–{seg['end']:7.2f}] {seg['speaker']}: {seg['text']}")
