"""
NIA 금융분야 고객상담 데이터(Validation) -> 통합 JSON 변환 스크립트

원본 폴더 안의 모든 *.json 파일을 읽어서, 아래 구조로 하나의 JSON 파일에 합친다.

{
  "cases": [
    {
      "id": "...",
      "label": 0 or 1,
      "turns": [
        {"turn_index": 1, "role": "speaker_a", "text": "..."},
        ...
      ]
    },
    ...
  ]
}

주의:
- 이 원본 폴더(Validation/02.라벨링데이터)에는 보이스피싱 여부를 나타내는 필드가
  없다(은행/보험/증권 일반 상담 데이터). 따라서 label은 전부 0(정상)으로 고정한다.
  만약 실제 보이스피싱 라벨 데이터를 합칠 때는 LABEL_VALUE 상수만 바꾸거나,
  build_case() 내부에서 원본 필드를 보고 분기하도록 수정하면 된다.
- 발화 원문(consulting_content)은 배열이 아니라 줄바꿈으로 구분된
  "TX ...", "RX ..." 형태의 단일 텍스트다. TX/RX 접두사를 기준으로
  role을 매핑하고 줄 단위로 잘라 turns 배열을 만든다.
"""

import json
from pathlib import Path

# ===================== 경로 설정 =====================
SOURCE_DIR = Path(
    "/Users/seminy/Downloads/25.금융분야 고객상담 데이터/3.개방데이터/2.데이터(NIA)/Validation"
)
OUTPUT_DIR = Path("/Users/seminy/Desktop/Main/Git/GNU_AI_BOOT_Project/data")
OUTPUT_FILENAME = "converted_dataset.json"

# ===================== 매핑 설정 (환경에 맞게 수정) =====================
# id로 사용할 원본 키 경로: data["source"]["source_id"]
ID_KEY_PATH = ("source", "source_id")

# 발화 원문이 들어있는 원본 키 경로: data["source"]["consulting_content"]
CONTENT_KEY_PATH = ("source", "consulting_content")

# 이 데이터셋에는 보이스피싱 라벨이 없으므로 전부 정상(0)으로 고정한다.
LABEL_VALUE = 0

# 발화 줄 접두사 -> role 매핑
SPEAKER_ROLE_MAP = {
    "TX": "speaker_a",  # 상담사로 추정
    "RX": "speaker_b",  # 고객으로 추정
}


def get_nested(data: dict, key_path: tuple):
    """중첩 딕셔너리에서 key_path를 따라 값을 꺼낸다. 없으면 None."""
    value = data
    for key in key_path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def parse_turns(content: str) -> list:
    """
    "TX ...\nRX ...\n..." 형태의 텍스트를 줄 단위로 잘라
    turns 배열([{turn_index, role, text}, ...])로 변환한다.
    """
    turns = []
    turn_index = 1

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        prefix, sep, text = line.partition(" ")
        if not sep or prefix not in SPEAKER_ROLE_MAP:
            # TX/RX 접두사가 없는 줄은 건너뛴다 (원본 포맷 예외 케이스 방어)
            continue

        turns.append(
            {
                "turn_index": turn_index,
                "role": SPEAKER_ROLE_MAP[prefix],
                "text": text.strip(),
            }
        )
        turn_index += 1

    return turns


def build_case(data: dict, file_path: Path) -> dict | None:
    """파일 하나(data)를 목표 JSON의 case 구조로 변환. 파싱 불가 시 None."""
    case_id = get_nested(data, ID_KEY_PATH)
    content = get_nested(data, CONTENT_KEY_PATH)

    if not case_id or not content:
        print(f"[SKIP] id 또는 content 없음: {file_path}")
        return None

    turns = parse_turns(content)
    if not turns:
        print(f"[SKIP] 파싱된 turns 없음: {file_path}")
        return None

    return {
        "id": case_id,
        "label": LABEL_VALUE,
        "turns": turns,
    }


def main():
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"원본 폴더가 존재하지 않습니다: {SOURCE_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_files = sorted(SOURCE_DIR.rglob("*.json"))
    print(f"대상 파일 수: {len(json_files)}")

    cases = []
    skipped = 0

    for file_path in json_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[SKIP] JSON 파싱 실패: {file_path} ({e})")
            skipped += 1
            continue

        case = build_case(data, file_path)
        if case is None:
            skipped += 1
            continue

        cases.append(case)

    output_path = OUTPUT_DIR / OUTPUT_FILENAME
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"cases": cases}, f, ensure_ascii=False, indent=2)

    print(f"변환 완료: {len(cases)}건 저장, {skipped}건 스킵")
    print(f"저장 경로: {output_path}")


if __name__ == "__main__":
    main()
