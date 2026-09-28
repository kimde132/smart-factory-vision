# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  split_dataset.py — 9세션의 사진·라벨을 촬영 세션 단위로 train / val / test 폴더에 복사한다             ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  어느 세션이 어느 폴더로 가는지는 아래 SPLIT_OF_SESSION 표 하나로 정해진다.
# │  랜덤으로 섞지 않는다 (docs/decisions.md D-003). 세션을 통째로 val·test 에 두어야 "본 적 없는 조명·기기에서도 맞히는가" 를 잴 수 있다.
# │
# │  촬영 → rename_session.py → crop_session.py → 라벨링 → verify_counts.py → [현재 파일] → data.yaml → train.py
# │  앞: dataset/crop/sXX/ (s01만 dataset/rename/s01/) 에 사진이, dataset/export/<최신 폴더>/labels/ 에 Label Studio 가 내보낸 라벨 320개(s08·s09 추가 뒤)가 있어야 한다.
# │      verify_counts.py 가 "검사완료 이상 없음" 을 낸 뒤에 돌린다.
# │  뒤: dataset/result_data/{images,labels}/{train,val,test}/ 가 채워지고, data.yaml 이 그 폴더를 가리켜 Colab 에서 학습한다.
# │
# │  실행 (프로젝트 최상위에서)
# │      ai-server\.venv\Scripts\python.exe scripts\split_dataset.py            ← 미리보기
# │      ai-server\.venv\Scripts\python.exe scripts\split_dataset.py --apply    ← 실제 복사
# │
# │  실행 순서: main() → build_plan() [find_label_dir → 라벨마다 parse_label_filename → 세션 → SPLIT_OF_SESSION → image_path_of] → print_summary 또는 apply_plan
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : import from def return for in if not raise try except as
# │  ② 라이브러리가 정한 이름
# │       argparse.ArgumentParser                          ← argparse (Python 기본)
# │       shutil.copy2                                     ← shutil (Python 기본)
# │       Path .resolve .parent .iterdir .is_dir .is_file .glob .name .mkdir  ← pathlib (Python 기본)
# │       sorted len any print                             ← Python 내장
# │       "images" "labels" "train" "val" "test"           ← YOLO 가 정한 폴더 이름 규칙. 바꾸면 YOLO 가 못 찾는다
# │  ③ 내가 지은 이름
# │       상수: PROJECT_ROOT EXPORT_DIR CROP_DIR RENAME_DIR RESULT_DIR SPLIT_OF_SESSION
# │       함수: find_label_dir image_path_of build_plan print_summary apply_plan main
# │       변수: folders session_id base_dir path label_dir plan label_path name split names sessions kind out_dir image_path parser args e
# │       내 다른 파일: parse_label_filename (verify_counts.py)
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  import argparse                                  (Python 기본) → --apply
# │  import shutil                                    (Python 기본) → 파일 복사
# │  from pathlib import Path                         (Python 기본) → 경로 객체
# │  from verify_counts import parse_label_filename   (내 파일)     → "02faa2d9__crop%5Cs02%5Cs02_005.txt" → "s02_005"
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  ★ YOLO 가 라벨을 찾는 방식 : 사진 경로의 "images" 를 "labels" 로 바꾸고 확장자를 .txt 로 바꿔 라벨을 찾는다.
# │        result_data/images/train/s02_005.jpg  →  result_data/labels/train/s02_005.txt
# │      그래서 사진과 라벨은 이름이 확장자만 빼고 똑같아야 한다. Label Studio export 라벨은 난수·경로가 붙어 있어 그대로 두면 짝이 안 맞는다.
# │      이 스크립트가 복사하면서 이름을 "s02_005.txt" 로 다시 짓는다. 이름이 어긋나면 에러가 나지 않고 "라벨 0개" 로 조용히 학습한다. 가장 찾기 어려운 사고.
# │  ★ 빈 라벨 파일(0바이트)도 데이터다 : 빈 트레이(sXX_029)의 라벨은 줄이 하나도 없다. YOLO 는 그것을 "여기엔 아무것도 없다" 는 배경(negative) 이미지로 배운다(D-005). 건너뛰지 않고 똑같이 복사한다.
# │  ★ 복사이지 이동이 아니다 : crop/ 과 rename/ 은 그대로 둔다. 분할이 잘못되면 result_data/ 만 비우고 다시 돌린다.
# │  미리보기 → --apply : rename_session.py · crop_session.py 와 같은 구조.
# │
# │  자료 모양
# │    plan (list) : [(image_path Path, label_path Path, split str, name str), …]  길이 = 라벨 수(320)
# │    결과 폴더   : result_data/images/{train,val,test}/sXX_NNN.jpg  +  result_data/labels/{train,val,test}/sXX_NNN.txt
# │
# │  관련 문서: docs/decisions.md D-003 (세션 단위 분할), D-011 (6세션 배정: Train 4 / Val 1 / Test 1. s07 은 EXP-02 용으로 train 에 추가),
# │            D-007 2절 (세션별 조명·기기 표), data.yaml (이 폴더를 읽는 쪽)
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ argparse(② 모듈): 명령줄 인자(--apply).
import argparse  # 명령줄 인자(--apply)를 받아 파싱해주는 표준 라이브러리
# ▸ shutil(② 모듈): 파일 복사. copy2 는 내용과 수정 시각까지 그대로 복사한다.
import shutil  # 파일 복사 표준 라이브러리. copy2 는 내용과 수정 시각까지 그대로 복사한다

# ▸ Path(② 클래스): 경로 객체. "/" 로 이어 붙이고 .stem, .is_file() 같은 메서드를 쓴다.
from pathlib import Path

# ▸ 단어 분해: from verify_counts(③ 같은 scripts/ 폴더) import parse_label_filename(③)
# ▸ 뜻: "02faa2d9__crop%5Cs02%5Cs02_005.txt" → "s02_005" 로 바꿔 주는 함수. 이미 검증된 것이라 새로 짜지 않는다.
# ▸ 왜 바로 되나: "python scripts\split_dataset.py" 로 실행하면 파이썬이 그 스크립트가 있는 폴더를 먼저 찾아본다.
from verify_counts import parse_label_filename

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  상수
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ PROJECT_ROOT(③) = Path(__file__).resolve().parent.parent : 어느 폴더에서 실행하든 아래 경로가 흔들리지 않게.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ▸ 폴더 넷. 입력 셋(EXPORT_DIR 라벨 / CROP_DIR s02~s09 사진 / RENAME_DIR s01 사진) → 출력 하나(RESULT_DIR, data.yaml 이 가리킨다).
EXPORT_DIR = PROJECT_ROOT / "dataset" / "export"
CROP_DIR = PROJECT_ROOT / "dataset" / "crop"
RENAME_DIR = PROJECT_ROOT / "dataset" / "rename"
RESULT_DIR = PROJECT_ROOT / "dataset" / "result_data"

# ▸ 단어 분해: SPLIT_OF_SESSION(③) = { "s01"(세션): "train"(폴더), … }   (딕셔너리)
# ▸ ★ 이 표가 D-003 · D-011 그 자체다. 세션 → split 이 고정되어 있고 난수가 어디에도 없다.
#   Train : s01(아이폰) s02(웹캠) s03(웹캠, 천장등+스탠드 강) s06(아이폰, 조명 없음)
#           s07(웹캠, s04 와 같은 조명의 그림자 전용 40장 — EXP-02 에서 추가. val 의 '그림자 안 와셔→너트' 오류를 줄이려는 것)
#           s08(웹캠, 천장등만, 겹침 17장·가장자리 17장 — EXP-03 에서 추가. 넣기 전에 EXP-02 모델로 채점하니 74.3% 였다)
#   Val   : s04(웹캠, 스탠드 약만) — 학습 중 채점용. 모델이 이것으로 배우지 않는다
#   Test  : s05(웹캠, 천장등+스탠드 측면) — EXP-01 에서 이미 한 번 썼다(97.1%). 이후 모델은 s05 로 채점하지 않는다
#           s09(웹캠, 스탠드 측면만, 배치 4종 섞음) — 최종 시험지. 최종 모델로 딱 한 번만 쓴다 (D-011 8절)
#           둘이 같은 test 폴더에 들어가지만 학습은 train·val 폴더만 읽으므로 섞이지 않는다. 채점할 때는 파일 이름(s09_)으로 고른다.
# ▸ 새 세션을 찍으면 여기에 한 줄을 더해야 한다. 안 더하면 build_plan 이 멈춘다 (조용히 train 에 섞이지 않게).
# ▸ 다른 선택: 값을 "val" 로 바꾸면 그 세션이 통째로 val 로 간다. 한 세션을 반씩 나누는 건 이 표로는 못 한다 — 그게 D-003 의 의도.
SPLIT_OF_SESSION = {
    "s01": "train",
    "s02": "train",
    "s03": "train",
    "s06": "train",
    "s04": "val",
    "s05": "test",
    "s07": "train",
    "s08": "train",
    "s09": "test",
}


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  함수 여섯 — export 폴더 찾기 / 사진 경로 / 계획 / 요약 / 복사 / 진입점
# ═══════════════════════════════════════════════════════════════════════════════════════════

def find_label_dir():
    """dataset/export/ 아래 export 폴더를 찾아 그 안의 labels/ 경로를 돌려준다.

    export 폴더 이름은 내보낼 때마다 바뀐다 (project-1-at-2026-09-13-21-06-8725257a 처럼).
    그래서 코드에 못 박지 못하고 매번 찾아야 한다.

    입력:
        없음. 모듈 상수 EXPORT_DIR 을 본다.

    출력:
        Path. 예: .../dataset/export/project-1-at-2026-09-13-21-06-8725257a/labels

    실패 시:
        export 폴더가 정확히 1개가 아니면 ValueError.
        2개면 어느 것이 최신인지 코드가 고르면 안 되고, 0개면 export 를 안 한 것이다.
        verify_counts.py 가 중복 export 에서 멈추는 것과 같은 철학이다.
    """
    # ▸ 단어 분해: folders(③) = [ p for p in EXPORT_DIR.iterdir() if p.is_dir()(폴더인 것만) ]   (리스트 컴프리헨션)
    # ▸ 압축 파일(.zip)이 남아 있어도 is_dir() 에서 걸러진다.
    folders = [p for p in EXPORT_DIR.iterdir() if p.is_dir()]
    # ▸ if len(folders) != 1: 정확히 하나가 아니면 멈춘다.
    if len(folders) != 1:
        raise ValueError(
            f"dataset/export 에 폴더가 {len(folders)}개다. 최신 export 하나만 남길 것"
        )
    # ▸ return folders[0] / "labels" : Label Studio YOLO export 는 폴더 안에 labels/ 와 classes.txt 를 만든다. 라벨은 labels/ 안에.
    return folders[0] / "labels"


# ▸ 단어 분해: def image_path_of(③)(name(③)):
def image_path_of(name):
    """정규화된 이름으로 원본 사진의 경로를 찾는다.

    입력:
        name (str): 난수·경로·확장자를 뗀 이름. 예: "s02_005"

    출력:
        Path. 예: .../dataset/crop/s02/s02_005.jpg
              s01 만 .../dataset/rename/s01/s01_001.jpg

    실패 시:
        그 경로에 파일이 없으면 FileNotFoundError.
        조용히 건너뛰면 라벨만 있고 사진이 없는 상태가 되는데, YOLO 는 그것을 에러 없이 무시한다.
        그래서 여기서 크게 멈춰야 한다.
    """
    # ▸ 단어 분해: session_id(③) = name.split(② 쪼개기)("_")[0](첫 조각)
    # ▸ 뜻: "s02_005" → ["s02", "005"] → "s02".
    # ▸ 다른 선택: name[:3] 으로 잘라도 되지만 세션 번호가 두 자리를 넘으면(s100) 깨진다. 밑줄 기준이 안전.
    session_id = name.split("_")[0]
    # ▸ 단어 분해: base_dir(③) = RENAME_DIR if session_id == "s01" else CROP_DIR   (조건식)
    # ▸ 왜: s01 은 아이폰 원본이 이미 정사각이라 crop_session.py 를 거치지 않았고, 그래서 rename/ 에만 있다. (s06 도 아이폰이지만 crop/ 에 복사본이 있다 — 상태판 9/11 "s06 은 정사각이라 복사만")
    base_dir = RENAME_DIR if session_id == "s01" else CROP_DIR
    # ▸ path = base_dir / session_id / f"{name}.jpg" : 사진은 세션 폴더 안에 있고 확장자는 전부 .jpg (rename_session.py 가 그렇게 만든다).
    path = base_dir / session_id / f"{name}.jpg"
    if not path.is_file():
        raise FileNotFoundError(f"사진이 없다: {path}")
    return path


def build_plan():
    """라벨 210개를 돌면서 "어느 사진·라벨을 어느 split 으로" 목록을 만든다.

    파일을 만들지 않고 계획만 세운다. 미리보기와 실제 복사가 **같은 계획**을 쓰게 하려는 것이다.
    (crop_session.py 의 build_plan 과 같은 이유)

    반복의 기준은 사진이 아니라 라벨이다. 라벨에서 시작해 사진을 찾아가면
    _rename_map.csv 처럼 사진 폴더에 섞여 있는 다른 파일을 걸러낼 필요가 없다.

    입력:
        없음. find_label_dir() 와 SPLIT_OF_SESSION 을 쓴다.

    출력:
        리스트. 각 원소는 (image_path, label_path, split, name) 네 개짜리 튜플.
            image_path (Path): 원본 사진.  예: .../crop/s02/s02_005.jpg
            label_path (Path): 원본 라벨.  예: .../labels/02faa2d9__crop%5Cs02%5Cs02_005.txt
            split      (str) : "train" / "val" / "test"
            name       (str) : 정규화된 이름. 예: "s02_005". 복사할 때 이 이름으로 다시 짓는다
        길이는 라벨 개수와 같다 (9/14 기준 210, 9/20 s08·s09 추가 뒤 320).

    실패 시:
        find_label_dir 의 ValueError, image_path_of 의 FileNotFoundError 가 그대로 올라온다.
        라벨 이름의 세션이 SPLIT_OF_SESSION 에 없으면 ValueError.
    """
    label_dir = find_label_dir()
    plan = []
    # ▸ 단어 분해: for label_path in sorted(label_dir.glob(② 패턴 검색)("*.txt")):
    # ▸ glob("*.txt") 는 그 폴더의 .txt 파일만. sorted 는 출력 순서를 고정하려는 것뿐 (난수 접두사 순이라 사람이 읽기 좋은 순서는 아니다. 결과에는 영향 없다).
    for label_path in sorted(label_dir.glob("*.txt")):
        # ▸ name = parse_label_filename(label_path.name(② 파일명만)) : "s02_005".
        name = parse_label_filename(label_path.name)
        session_id = name.split("_")[0]
        # ▸ if session_id not in SPLIT_OF_SESSION: 배정표에 없는 세션은 멈춘다. 새 세션(s10 등)을 찍고 표를 안 고치면 조용히 train 에 섞이는 사고를 막는 한 줄.
        if session_id not in SPLIT_OF_SESSION:
            raise ValueError(
                f"배정표에 없는 세션이다: {session_id} ({label_path.name})"
            )
        # ▸ split(③) = SPLIT_OF_SESSION[session_id] : 딕셔너리 조회. 위에서 있는 것을 확인했으므로 KeyError 는 나지 않는다.
        split = SPLIT_OF_SESSION[session_id]
        # ▸ plan.append((image_path_of(name), label_path, split, name)) : 사진 경로는 여기서 찾는다(없으면 image_path_of 가 멈춘다).
        plan.append((image_path_of(name), label_path, split, name))
    return plan


def print_summary(plan):
    """split 별 장수와 세션 목록을 세 줄로 출력한다.

    320 줄을 다 찍어봐야 눈으로 못 본다. 배정이 맞는지는 이 세 줄이면 알 수 있다.
    기대값: train 215 (s01, s02, s03, s06, s08 각 35 + s07 40) / val 35 (s04) / test 70 (s05, s09)

    입력:
        plan (list): build_plan 이 돌려준 목록

    출력:
        없음. 화면에 출력만 한다.
    """
    for split in ("train", "val", "test"):
        # ▸ 단어 분해: names(③) = [ name for _, _, s, name in plan if s == split ]
        # ▸ 뜻: 튜플 4개를 "_, _, s, name" 으로 풀어 필요한 둘만 쓴다. "_" 는 "안 쓴다" 는 관례. 이 split 에 속한 이름만 모은다.
        names = [name for _, _, s, name in plan if s == split]
        # ▸ 단어 분해: sessions(③) = sorted( { n.split("_")[0] for n in names } )   (집합 컴프리헨션 { … })
        # ▸ 뜻: 같은 세션이 35번 나와도 집합이라 하나로 합쳐진다. sorted 로 리스트가 된다. 예: ["s01", "s02", "s03", "s06", "s07", "s08"].
        sessions = sorted({n.split("_")[0] for n in names})
        # ▸ f-string 서식: {split:<6} 왼쪽 정렬 6칸, {len(names):>4} 오른쪽 정렬 4칸. ", ".join(sessions) 로 세션 목록을 한 줄에.
        print(f"{split:<6} {len(names):>4}장   {', '.join(sessions)}")


def apply_plan(plan):
    """계획대로 사진과 라벨을 result_data/ 로 복사한다.

    입력:
        plan (list): build_plan 이 돌려준 목록

    출력:
        없음. 파일 시스템에 복사본을 만든다.
            result_data/images/<split>/<name>.jpg
            result_data/labels/<split>/<name>.txt

    실패 시:
        6개 출력 폴더 중 하나라도 비어 있지 않으면 FileExistsError. 아무것도 복사하지 않고 멈춘다.
        절반만 복사된 상태가 가장 곤란하므로, 복사를 시작하기 전에 전부 확인한다.
    """
    # ▸ 1단계: 복사하기 전에 6개 폴더(images·labels × train·val·test)가 전부 비었는지 본다. 이중 for 문.
    for split in ("train", "val", "test"):
        for kind in ("images", "labels"):
            out_dir = RESULT_DIR / kind / split
            # ▸ out_dir.mkdir(parents=True(중간 폴더까지), exist_ok=True(이미 있어도 에러 내지 않는다))
            out_dir.mkdir(parents=True, exist_ok=True)
            # ▸ if any(out_dir.iterdir()): 항목이 하나라도 있으면 True. 비어 있어야 통과.
            # ▸ 왜 덮어쓰지 않나: 이전 분할과 섞이면 어느 파일이 어느 분할 것인지 알 수 없게 된다.
            if any(out_dir.iterdir()):
                raise FileExistsError(
                    f"{out_dir} 가 비어 있지 않다. 비우고 다시 실행할 것"
                )
    # ▸ 2단계: 실제 복사. ★ 파일명을 name 으로 다시 짓는 것이 이 스크립트의 핵심이다.
    # ▸ 라벨 원본 이름에는 난수·경로가 붙어 있어 그대로 복사하면 사진과 이름이 안 맞는다 (파일 상단 3절). 빈 트레이의 0바이트 라벨도 똑같이 복사된다. 그것이 배경 이미지다.
    for image_path, label_path, split, name in plan:
        # ▸ shutil.copy2(원본, RESULT_DIR / "images" / split / f"{name}.jpg") : 사진. 이름은 이미 sXX_NNN.jpg 라 그대로.
        shutil.copy2(image_path, RESULT_DIR / "images" / split / f"{name}.jpg")
        # ▸ 라벨. 원본은 "02faa2d9__crop%5C…txt" 인데 목적지 이름을 f"{name}.txt" 로 줘서 복사하며 이름이 바뀐다.
        shutil.copy2(label_path, RESULT_DIR / "labels" / split / f"{name}.txt")
    print(f"\n{len(plan)}쌍 복사 완료 -> {RESULT_DIR}\n")


def main():
    """명령줄에서 실행됐을 때의 진입점.

    입력:
        명령줄 인자. --apply (선택). 세션 인자는 없다 — 한 세션이 아니라 6세션을 한 번에 다룬다.

    출력:
        종료 코드. 0이면 정상, 1이면 오류.
    """
    parser = argparse.ArgumentParser(
        description="6세션 사진·라벨을 세션 단위로 result_data/ 의 train/val/test 에 복사한다."
    )
    # ▸ "--apply" action="store_true" : 플래그. 붙이면 True, 안 붙이면 False. 값을 따로 받지 않는다.
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 복사한다. 붙이지 않으면 계획만 출력한다",
    )
    args = parser.parse_args()

    # ▸ try / except (ValueError, FileNotFoundError) as e: 우리가 raise 로 직접 만든 예외들. 메시지만 찍고 종료 코드 1.
    try:
        plan = build_plan()
    except (ValueError, FileNotFoundError) as e:
        print(f"\n[중단] {e}\n")
        return 1

    # ▸ if not args.apply: 미리보기. 표 대신 세 줄 요약만 찍고 끝낸다.
    if not args.apply:
        print(f"\n{len(plan)}쌍 / 미리보기 (파일을 만들지 않음)\n")
        print_summary(plan)
        print("\n위가 맞으면 --apply 를 붙여 다시 실행하세요.")
        print(
            "  ai-server\\.venv\\Scripts\\python.exe scripts\\split_dataset.py --apply\n"
        )
        return 0

    try:
        apply_plan(plan)
    except FileExistsError as e:
        print(f"\n[중단] {e}\n")
        return 1

    # ▸ 복사가 끝난 뒤 무엇이 어디로 갔는지 한 번 더 남긴다.
    print_summary(plan)
    return 0


# ▸ 이 파일을 직접 실행했을 때만 main() 이 돈다. 다른 파일이 import 하면 돌지 않는다.
# ▸ raise SystemExit(main()) : main() 의 반환값(0 또는 1)을 운영체제에 종료 코드로 전달.
if __name__ == "__main__":
    raise SystemExit(main())
