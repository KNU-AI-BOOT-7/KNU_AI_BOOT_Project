"""화자 구분 + 타임스탬프 + dataset.json 스키마 통합 (OpenRouter API 버전)
   - google/gemini-3.5-flash 멀티모달 모델이 전사·화자 구분·타임스탬프를 한 번에 수행
   - 키는 .env의 OPENROUTER_API_KEY, 모델은 STT_MODEL 환경변수로 변경 가능
"""
import base64
from contextlib import contextmanager
import json
import os
import tempfile
import wave

from openai import OpenAI

from backend.app.paths import ENV_PATH

MODEL = os.environ.get("STT_MODEL", "google/gemini-3.5-flash")

PROMPT = """이 오디오는 보이스피싱 의심 통화이거나 정상 금융 상담 통화다.
전체 통화를 처음부터 끝까지 빠짐없이 한국어로 전사하고 화자를 구분하라.
계좌, 이체, 대출, 개인정보 관련 용어에 유의해 정확히 전사하라.

규칙:
- 화자는 등장 순서대로 "화자A", "화자B", ... 로 표기한다. (이 통화의 화자는 보통 {n}명)
- start/end 는 해당 발화의 시작/끝 시각이며 "MM:SS" 형식이다.
- 발화(문장) 단위로 나누고, 시간 순서대로 정렬한다.
- 아래 JSON 배열만 출력한다. 다른 텍스트나 코드펜스는 출력하지 마라.

[{"start": "MM:SS", "end": "MM:SS", "speaker": "화자A", "text": "..."}]"""

_client = None


@contextmanager
def _open_supported_audio_file(audio_file_path: str):
    """OpenRouter 입력 오디오가 지원하는 mp3/wav로 파일을 준비한다.

    m4a/mp4/aac 컨테이너는 그대로 전송하지 않고 임시 wav 파일로 변환한다.
    """
    ext = os.path.splitext(audio_file_path)[1].lower().lstrip(".")
    if ext in {"mp3", "mpeg", "mpga"}:
        yield audio_file_path, "mp3"
        return
    if ext == "wav":
        yield audio_file_path, "wav"
        return
    if ext in {"m4a", "mp4", "aac"}:
        converted_path = _convert_audio_to_wav(audio_file_path)
        try:
            yield converted_path, "wav"
        finally:
            os.unlink(converted_path)
        return

    raise ValueError(f"지원하지 않는 오디오 파일 형식입니다: .{ext}")


def _convert_audio_to_wav(audio_file_path: str) -> str:
    """PyAV로 m4a 계열 오디오를 16kHz mono wav로 변환한다."""
    import av

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()

    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    try:
        with av.open(audio_file_path) as container, wave.open(tmp.name, "wb") as wav_file:
            audio_stream = next((stream for stream in container.streams if stream.type == "audio"), None)
            if audio_stream is None:
                raise ValueError("오디오 스트림을 찾을 수 없습니다.")

            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)

            for packet in container.demux(audio_stream):
                for frame in packet.decode():
                    for resampled_frame in resampler.resample(frame):
                        pcm = resampled_frame.to_ndarray().reshape(-1)
                        wav_file.writeframes(pcm.tobytes())
    except Exception:
        os.unlink(tmp.name)
        raise

    return tmp.name


def _load_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key and ENV_PATH.exists():
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    return key


def _parse_time(value) -> float:
    """"MM:SS" / "H:MM:SS" / 숫자(초)를 초 단위 float로 변환한다."""
    if isinstance(value, (int, float)):
        return float(value)
    sec = 0.0
    for part in str(value).strip().split(":"):
        sec = sec * 60 + float(part)
    return sec


def _extract_json_array(raw: str) -> list:
    """모델 응답에서 JSON 배열을 견고하게 추출한다.
    코드펜스·설명 문장이 섞여 나와도 가장 바깥 [ ... ]를 파싱한다."""
    raw = raw.strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        raise ValueError(f"JSON 배열 없음: {raw[:80]!r}")
    return json.loads(raw[start:end + 1])


def transcribe_with_speakers(audio_file_path: str, expected_speakers: int = 2, retries: int = 1) -> list[dict]:
    """오디오 파일을 OpenRouter 멀티모달 모델로 전사해 발화 segment 목록을 반환한다.

    반환 형식: [{"start": 초, "end": 초, "speaker": "화자A", "text": "..."}]
    (로컬 모델 버전과 동일한 스키마)
    """
    global _client
    if _client is None:
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=_load_key())

    with _open_supported_audio_file(audio_file_path) as (prepared_audio_path, audio_format):
        with open(prepared_audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT.replace("{n}", str(expected_speakers))},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}},
            ],
        }]

    last_err = None
    for _ in range(retries + 1):
        try:
            r = _client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0,
                max_tokens=32768,
            )
            raw_segments = _extract_json_array(r.choices[0].message.content or "")
            break
        except Exception as e:
            last_err = e
    else:
        raise RuntimeError(f"OpenRouter 전사 실패: {last_err}")

    segments = []
    for seg in raw_segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        segments.append({
            "start": round(_parse_time(seg.get("start", 0)), 2),
            "end": round(_parse_time(seg.get("end", 0)), 2),
            "speaker": str(seg.get("speaker", "화자A")).strip(),
            "text": text,
        })
    return segments


if __name__ == "__main__":
    import platform
    import sys

    # 사용법: python -m backend.app.mp3_json [오디오 폴더 경로] [phishing_type]
    if len(sys.argv) > 1:
        TEST_DIR = sys.argv[1]
        PHISHING_TYPE = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        if platform.system() == "Darwin":
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

    audio_files = [f for f in sorted(os.listdir(TEST_DIR)) if f.lower().endswith((".mp3", ".wav", ".m4a"))]

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
