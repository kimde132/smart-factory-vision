# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  rename_session.py — 카메라가 붙인 이름(IMG_E8821.JPG)을 우리 규칙(s01_001.jpg)으로 바꿔 복사한다       ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  dataset/origin/<세션>/ → dataset/rename/<세션>/ 으로 복사하면서 이름을 바꾼다. 원본(origin/)은 건드리지 않는다.
# │  순서는 파일 이름이나 파일 수정 시각이 아니라 **사진 안에 박혀 있는 EXIF 촬영 시각**으로 정한다.
# │  파일 수정 시각은 PC 로 옮기는 순간 "옮긴 시각" 으로 바뀌어버려서 믿을 수 없다.
# │
# │  촬영 → [현재 파일] → crop_session.py(웹캠만) → 라벨링(Label Studio) → verify_counts.py → split_dataset.py → train.py
# │  앞: 사람이 손으로 카메라에서 PC 로 옮겨둔 dataset/origin/<세션>/ + metadata/images.csv 에 그 세션의 행(촬영 전에 미리 채운 계획표)
# │  뒤: dataset/rename/<세션>/ — 아이폰 세션(s01, s06)은 이것이 Label Studio 입력, 웹캠 세션은 crop_session.py 를 한 번 더 거친다.
# │
# │  실행 (프로젝트 최상위에서)
# │      ai-server\.venv\Scripts\python.exe scripts\rename_session.py s01            ← 미리보기 (파일 안 건드림)
# │      ai-server\.venv\Scripts\python.exe scripts\rename_session.py s01 --apply    ← 실제 복사
# │
# │  실행 순서: main() → build_mapping(세션) [collect_origin_images + load_expected_rows + 장마다 read_shot_time → 시각 정렬 → csv 행과 zip]
# │            → 매핑표 출력 → (--apply 면) 복사 + _rename_map.csv 기록
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : import from def return with if not raise for in and or lambda try except as
# │  ② 라이브러리가 정한 이름
# │       argparse.ArgumentParser                          ← argparse (Python 기본)
# │       csv.DictReader csv.writer .writerow              ← csv (Python 기본)
# │       shutil.copy2                                     ← shutil (Python 기본)
# │       sys.stdout.reconfigure sys.exit                  ← sys (Python 기본)
# │       Path .resolve .parent .is_dir .iterdir .is_file .suffix .name .exists .mkdir  ← pathlib (Python 기본)
# │       Image.open .getexif .get_ifd   ExifTags.TAGS     ← PIL (pip: Pillow)
# │       sorted zip len any str open print                ← Python 내장
# │       "DateTimeOriginal" "SubsecTimeOriginal" 0x8769   ← EXIF 표준이 정한 태그 이름·주소
# │  ③ 내가 지은 이름
# │       상수: PROJECT_ROOT ORIGIN_DIR RENAME_DIR IMAGES_CSV IMAGE_SUFFIXES TAG_ID EXIF_IFD_POINTER
# │       함수: read_shot_time load_expected_rows collect_origin_images build_mapping main
# │       변수: exif exif_ifd shot_time subsec rows folder files expected shot_times seen path stamp files_sorted
# │             parser args mapping out_dir mode src new_name row map_path writer _sub e
# │       csv 컬럼: image_name bolt_count nut_count washer_count layout  /  기록 파일 컬럼: new_name origin_name shot_time
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  import argparse                     (Python 기본) → 명령줄 인자
# │  import csv                          (Python 기본) → images.csv 읽기, _rename_map.csv 쓰기
# │  import shutil                       (Python 기본) → 파일 복사
# │  import sys                          (Python 기본) → 콘솔 인코딩, 종료 코드
# │  from pathlib import Path            (Python 기본) → 경로 객체
# │  from PIL import Image, ExifTags     (pip: Pillow)  → 이미지 열기, EXIF 태그 이름표
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  EXIF            : 사진 파일 안에 같이 저장되는 촬영 정보(시각, 카메라, 렌즈 등). 이미지 데이터와 한 파일에 들어 있어서 복사해도 따라다닌다.
# │                    카톡·메일로 보내면 지워진다. 태그는 숫자 ID 로 저장되고, 촬영 관련 태그는 하위 구역(Exif IFD, 주소 0x8769)에 모여 있다.
# │  원본을 덮어쓰지 않는다 : origin/ 은 손대지 않고 rename/ 에 사본을 만든다. 규칙이 틀렸다는 걸 나중에 알아도 origin/ 에서 다시 시작할 수 있다 (D-009 Q17).
# │  순서가 곧 정답  : metadata/images.csv 는 촬영 전에 미리 채워둔 "의도한 개수" 표. 001번 사진이 CSV 1행과 짝이 맞는다는 전제가 깨지면
# │                    라벨링 검수(verify_counts.py)가 전부 무의미해진다. 그래서 개수가 다르면 멈추고, 시각이 겹쳐도 멈춘다.
# │  미리보기 → --apply : crop_session.py · split_dataset.py 와 같은 구조.
# │
# │  자료 모양
# │    read_shot_time 출력   : ("2026:08:18 23:21:28", "482")  — (촬영시각, 1초미만). 둘 다 문자열
# │    load_expected_rows 출력: [{"image_name": "s01_001", "bolt_count": "0", …, "layout": "tight"}, …]  — 값은 전부 문자열
# │    build_mapping 출력    : [(Path(".../IMG_E8821.JPG"), "s01_001.jpg", {csv 행}), …]  — 촬영 시각 순
# │
# │  관련 문서: docs/decisions.md D-009 (4·5·7절), metadata/README.md
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ argparse(② 모듈): 명령줄 인자(s01, --apply).
import argparse  # 명령줄 인자(s01, --apply)를 받아 파싱해주는 표준 라이브러리
# ▸ csv(② 모듈): metadata/images.csv 를 읽는다. 쉼표 분리를 직접 짜면 값 안의 쉼표에서 깨진다.
import csv  # metadata/images.csv 를 읽는다. 쉼표 분리를 직접 짜면 값 안의 쉼표에서 깨진다
# ▸ shutil(② 모듈): 파일 복사(shutil.copy2). copy2 는 내용뿐 아니라 수정 시각까지 함께 복사한다.
import shutil  # 파일 복사(shutil.copy2). copy2 는 내용뿐 아니라 수정 시각까지 함께 복사한다
# ▸ sys(② 모듈): 종료 코드(sys.exit), 콘솔 인코딩(sys.stdout).
import sys  # 오류가 났을 때 종료 코드 1로 빠져나가기 위해 사용 (sys.exit)
# ▸ Path(② 클래스). 괄호·줄바꿈은 포매터가 넣은 것.
from pathlib import (
    Path,
)  # 경로를 문자열이 아니라 객체로 다룬다. 윈도우 역슬래시를 신경 쓰지 않아도 된다

# ▸ 단어 분해: from PIL import Image(② 이미지 클래스), ExifTags(② EXIF 태그 번호↔이름 표를 가진 모듈)
from PIL import Image, ExifTags  # Pillow. 이미지 열기와 EXIF 태그 이름표를 제공한다

# ▸ 단어 분해: sys.stdout.reconfigure(errors="replace")
# ▸ 왜: 윈도우 콘솔의 기본 인코딩은 CP949(한국어 완성형)라서 유니코드 기호 일부를 출력하지 못하고 UnicodeEncodeError 로 프로그램 전체가 죽는다. 실제로 여기서 em dash(—)에 걸렸다.
#   errors="replace" 는 표현 못 하는 글자를 '?' 로 바꿔서 넘어가게 한다. 출력 한 글자 때문에 35장 처리가 통째로 실패하는 것보다 낫다.
sys.stdout.reconfigure(errors="replace")

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  상수
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ PROJECT_ROOT(③) = Path(__file__).resolve()(절대 경로로).parent(scripts/).parent(최상위). 어느 폴더에서 실행해도 경로가 어긋나지 않는다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ▸ 폴더 셋. ORIGIN_DIR(입력) → RENAME_DIR(출력). IMAGES_CSV 는 사진당 1행짜리 계획표.
ORIGIN_DIR = PROJECT_ROOT / "dataset" / "origin"  # 카메라에서 꺼낸 원본이 있는 곳
RENAME_DIR = PROJECT_ROOT / "dataset" / "rename"  # 규칙대로 이름을 바꾼 사본이 놓일 곳
IMAGES_CSV = PROJECT_ROOT / "metadata" / "images.csv"  # 사진당 1행짜리 계획표

# ▸ IMAGE_SUFFIXES(③): 처리 대상 확장자. 대소문자를 섞어 쓰는 카메라가 있어 소문자로 비교한다. 아이폰은 .JPG(대문자)로 저장하는데 우리 규칙은 소문자 .jpg (D-009 Q15).
IMAGE_SUFFIXES = {".jpg", ".jpeg"}

# ▸ 단어 분해: TAG_ID(③) = { name: num for num, name in ExifTags.TAGS(② {숫자: 이름} 사전).items() }   (딕셔너리 컴프리헨션, 키와 값을 뒤집음)
# ▸ 뜻: EXIF 태그는 파일 안에 숫자 ID 로 저장된다. 사람이 읽는 이름 → 숫자 ID 사전을 만들어 둔다. 예: "DateTimeOriginal" → 36867.
# ▸ 왜 뒤집나: ExifTags.TAGS 는 {숫자: 이름} 인데 우리는 이름으로 찾고 싶다.
TAG_ID = {name: num for num, name in ExifTags.TAGS.items()}

# ▸ EXIF_IFD_POINTER(③) = 0x8769(16진수 = 34665) : EXIF 안에서 촬영 관련 태그들이 모여 있는 하위 구역(Exif IFD)의 주소. EXIF 표준이 정한 값.
# ▸ DateTimeOriginal 은 최상위가 아니라 이 하위 구역에 들어 있다. 그래서 아래에서 get_ifd(0x8769) 를 먼저 한다.
EXIF_IFD_POINTER = 0x8769


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  함수 다섯 — EXIF 읽기 / csv 행 / 원본 목록 / 짝짓기(핵심) / 진입점
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: def read_shot_time(③)(path(③): Path(타입 힌트)) -> tuple[str, str](문자열 둘짜리 튜플을 돌려줌):
def read_shot_time(path: Path) -> tuple[str, str]:
    """사진 한 장의 EXIF에서 촬영 시각을 읽는다.

    입력:
        path (Path): 읽을 이미지 파일 경로.
                     예) dataset/origin/s01/IMG_E8821.JPG

    출력:
        (촬영시각, 1초미만) 두 문자열의 튜플.
        예) ("2026:08:18 23:21:28", "482")
        1초 미만 값이 없는 카메라도 있어서 그때는 "" 를 돌려준다.
        정렬할 때 이 튜플을 그대로 기준으로 쓴다 — 같은 초에 두 장이 찍혀도
        1초 미만 값으로 앞뒤가 갈린다.

    실패 시:
        촬영 시각이 아예 없으면 ValueError 를 낸다.
        메신저나 메일로 사진을 주고받으면 EXIF가 지워지는데,
        그러면 촬영 순서를 복원할 방법이 없으므로 조용히 넘어가지 않고 멈춘다.
    """
    # ▸ 단어 분해: with Image.open(path) as im(③): exif(③) = im.getexif(② 최상위 EXIF 읽기)()
    # ▸ with: 파일을 열고, 블록이 끝나면 예외가 나든 말든 반드시 닫아 준다. exif 는 dict 처럼 쓰지만 실제로는 Exif 객체다. 블록 밖에서도 값은 남는다.
    with Image.open(path) as im:
        exif = im.getexif()  # 최상위 EXIF. dict 처럼 쓰지만 실제로는 Exif 객체다

    # ▸ exif_ifd(③) = exif.get_ifd(② 하위 구역 꺼내기)(EXIF_IFD_POINTER)
    # ▸ 뜻: 촬영 정보가 모여 있는 하위 구역. EXIF 가 없는 파일이면 빈 dict 가 돌아온다(예외 아님).
    exif_ifd = exif.get_ifd(EXIF_IFD_POINTER)

    # ▸ 단어 분해: shot_time(③) = exif_ifd.get(② 없으면 None)( TAG_ID["DateTimeOriginal"](이름 → 36867) )
    # ▸ 뜻: 촬영한 순간의 시각. 파일을 복사해도 바뀌지 않는다.
    # ▸ 다른 선택: TAG_ID["DateTime"] 은 "파일이 마지막으로 손댄 시각" 이라 목적이 다르다. 편집 앱을 거치면 바뀐다.
    shot_time = exif_ifd.get(TAG_ID["DateTimeOriginal"])

    # ▸ if not shot_time: None 이거나 빈 글자면 raise ValueError. 조용히 넘어가면 순서를 복원할 방법이 없다.
    if not shot_time:
        raise ValueError(
            f"{path.name}: EXIF 촬영 시각(DateTimeOriginal)이 없습니다.\n"
            f"  카톡·메일로 옮기면 EXIF가 지워집니다. 케이블이나 구글 드라이브로 다시 옮기세요."
        )

    # ▸ 단어 분해: subsec(③) = exif_ifd.get( TAG_ID.get("SubsecTimeOriginal")(이름이 표에 없을 수도 있어 .get), ""(없으면 빈 글자) ) or(① 왼쪽이 거짓이면 오른쪽) ""
    # ▸ 뜻: 1초 미만 단위. 연사로 찍으면 같은 초에 여러 장이 들어가므로 정렬의 보조 기준. 없는 카메라도 있어서 기본값 "".
    # ▸ 왜 or "": .get 이 None 을 돌려주는 경우(값이 None 으로 들어 있을 때)까지 "" 로 통일하려고. 아래 str() 과 짝.
    subsec = exif_ifd.get(TAG_ID.get("SubsecTimeOriginal"), "") or ""

    # ▸ return str(shot_time), str(subsec)  — 괄호 없는 튜플. 왜 str(): 카메라에 따라 숫자 타입으로 들어오는 경우가 있는데 정렬할 때 문자열과 숫자가 섞이면 파이썬이 비교하지 못하고 터진다(TypeError).
    return str(shot_time), str(subsec)


# ▸ 단어 분해: def load_expected_rows(③)(session_id: str) -> list[dict](딕셔너리 목록을 돌려줌):
def load_expected_rows(session_id: str) -> list[dict]:
    """metadata/images.csv 에서 이 세션의 행만 골라 순서대로 돌려준다.

    입력:
        session_id (str): 세션 번호. 예) "s01"

    출력:
        CSV 한 행이 dict 하나인 리스트. CSV에 적힌 순서를 그대로 유지한다.
        예) [{"image_name": "s01_001", "bolt_count": "0", ..., "layout": "tight"}, ...]

    실패 시:
        해당 세션 행이 하나도 없으면 ValueError.
        촬영 전에 CSV를 미리 채우기로 했으므로(metadata/README.md),
        행이 없다는 건 순서가 뒤바뀌었다는 뜻이다.
    """
    # ▸ 단어 분해: with open(IMAGES_CSV, newline=""(② csv 모듈이 요구하는 관례), encoding="utf-8-sig"(② BOM 을 벗겨 주는 인코딩)) as f:
    # ▸ 왜 newline="": 이걸 빼면 윈도우에서 빈 줄이 끼어 읽힌다.
    # ▸ 왜 utf-8-sig: 메모장으로 저장하면 파일 맨 앞에 BOM(눈에 안 보이는 표식)이 붙는데, 그러면 첫 컬럼 이름이 "﻿image_name" 이 되어 row["image_name"] 가 KeyError 로 터진다. -sig 는 있으면 벗기고 없으면 그냥 읽는다.
    with open(IMAGES_CSV, newline="", encoding="utf-8-sig") as f:
        # ▸ reader = csv.DictReader(f) : 첫 줄을 컬럼 이름으로 삼아 각 행을 dict 로. row[0] 대신 row["bolt_count"] 로 쓸 수 있어 컬럼 순서가 바뀌어도 안전하다. verify_counts.py 와 같다.
        reader = csv.DictReader(f)
        # ▸ 단어 분해: rows(③) = [ r for r in reader if r["image_name"].startswith(② 이 글자로 시작하나)(session_id + "_") ]   (리스트 컴프리헨션)
        # ▸ 뜻: image_name 이 "s01_" 로 시작하는 행만. "s01_001" 형태이므로 이걸로 세션이 갈린다. (별도 session_id 컬럼을 두지 않은 이유 — metadata/README.md)
        # ▸ 왜 "_" 까지: "s1" 로 시작하나만 보면 s10, s11 도 걸린다. 밑줄까지 붙여야 정확히 s01 만.
        rows = [r for r in reader if r["image_name"].startswith(session_id + "_")]

    if not rows:
        raise ValueError(
            f"metadata/images.csv 에 '{session_id}_' 로 시작하는 행이 없습니다.\n"
            f"  촬영 전에 CSV를 먼저 채우는 것이 규칙입니다 (metadata/README.md)."
        )
    return rows


# ▸ 단어 분해: def collect_origin_images(③)(session_id: str) -> list[Path]:
def collect_origin_images(session_id: str) -> list[Path]:
    """dataset/origin/<세션>/ 안의 이미지 파일 경로를 모은다.

    입력:
        session_id (str): 예) "s01"

    출력:
        이미지 파일 경로 리스트. 이 시점의 순서는 의미가 없다 (뒤에서 촬영 시각으로 다시 정렬한다).

    실패 시:
        폴더가 없거나 이미지가 한 장도 없으면 FileNotFoundError.
    """
    folder = ORIGIN_DIR / session_id
    if not folder.is_dir():
        raise FileNotFoundError(
            f"{folder} 폴더가 없습니다.\n"
            f"  카메라에서 꺼낸 사진을 이 폴더에 먼저 넣으세요."
        )

    # ▸ 단어 분해: files(③) = [ p for p in folder.iterdir()(항목 하나씩) if p.is_file()(파일이고) and p.suffix.lower()(확장자 소문자) in IMAGE_SUFFIXES ]
    # ▸ 뜻: 폴더 안 사진 파일만. 하위 폴더는 is_file() 에서, 다른 파일은 확장자에서 걸러진다. .JPG 도 .lower() 로 잡힌다.
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    ]

    if not files:
        raise FileNotFoundError(f"{folder} 안에 이미지 파일이 없습니다.")
    return files


# ▸ 단어 분해: def build_mapping(③)(session_id: str) -> list[tuple[Path, str, dict]](세 개짜리 튜플의 목록):
def build_mapping(session_id: str) -> list[tuple[Path, str, dict]]:
    """원본 파일과 새 이름을 짝지어 준다. 이 함수가 이 스크립트의 핵심이다.

    입력:
        session_id (str): 예) "s01"

    출력:
        (원본경로, 새파일명, CSV행) 튜플의 리스트. 촬영 시각 순으로 정렬돼 있다.
        예) [(Path(".../IMG_E8821.JPG"), "s01_001.jpg", {"bolt_count": "0", ...}), ...]

    실패 시:
        - 촬영 시각이 같은 사진이 있으면 ValueError (어느 쪽이 먼저인지 정할 수 없다)
        - 사진 수와 CSV 행 수가 다르면 ValueError (지워야 할 실패 사진이 남았거나, 덜 찍었다)
    """
    files = collect_origin_images(session_id)
    expected = load_expected_rows(session_id)

    # ▸ 단어 분해: shot_times(③) = { p: read_shot_time(p) for p in files }   (딕셔너리 컴프리헨션)
    # ▸ 뜻: {경로: ("2026:08:18 23:21:28", "482")} 사전. 각 파일의 촬영 시각을 미리 한 번만 읽어 둔다.
    # ▸ 왜: 정렬할 때마다 파일을 다시 여는 것을 피하려고. sorted 의 key 함수가 여러 번 불리기 때문.
    shot_times = {p: read_shot_time(p) for p in files}

    # ▸ 단어 분해: seen(③): dict[tuple[str, str], Path](타입 힌트: 키는 시각 튜플, 값은 경로) = {}
    # ▸ 뜻: 이미 본 촬영 시각 → 그 파일. 겹치는 시각을 찾기 위한 장부.
    # ▸ 왜: 시각이 겹치면 정렬 결과가 실행할 때마다 달라질 수 있고, 그러면 CSV 의 개수와 사진이 어긋나는데 눈으로는 알아채기 어렵다.
    seen: dict[tuple[str, str], Path] = {}
    # ▸ for path, stamp in shot_times.items(): (경로, 시각튜플) 쌍 하나씩.
    for path, stamp in shot_times.items():
        # ▸ if stamp in seen: 같은 시각을 이미 봤으면 멈춘다. seen[stamp].name 이 먼저 본 파일, path.name 이 지금 파일, stamp[0] 이 시각 글자.
        if stamp in seen:
            raise ValueError(
                f"촬영 시각이 같은 사진이 두 장 있습니다: {seen[stamp].name}, {path.name} ({stamp[0]})\n"
                f"  어느 쪽이 먼저인지 정할 수 없어 중단합니다. 둘 중 하나가 중복 사진인지 확인하세요."
            )
        seen[stamp] = path

    # ▸ 단어 분해: files_sorted(③) = sorted(files, key=lambda(① 이름 없는 한 줄 함수) p: shot_times[p])
    # ▸ 뜻: 촬영 시각 순으로 줄을 세운다. key= 에 넘긴 함수의 반환값이 정렬 기준. lambda p: shot_times[p] = "경로 p 를 받아 그 시각 튜플을 돌려주는 함수".
    # ▸ 튜플 비교: ("시각", "1초미만") 은 앞 원소부터 차례로 비교된다. 시각이 같으면 1초미만으로 갈린다.
    files_sorted = sorted(files, key=lambda p: shot_times[p])

    # ▸ if len(files_sorted) != len(expected): 사진 수와 CSV 행 수가 다르면 반드시 멈춘다. 여기서 걸리면 뒤 작업이 전부 어긋난다.
    if len(files_sorted) != len(expected):
        raise ValueError(
            f"사진 {len(files_sorted)}장 / CSV {len(expected)}행 — 개수가 다릅니다.\n"
            f"  실패한 사진을 안 지웠거나, 계획표대로 다 찍지 않았을 수 있습니다.\n"
            f"  개수를 맞추기 전에는 이름을 바꾸지 않습니다."
        )

    # ▸ 단어 분해: return [ (path, row["image_name"] + ".jpg", row) for path, row in zip(② 두 목록을 앞에서부터 짝짓기)(files_sorted, expected) ]
    # ▸ 뜻: 시각 순 1번 사진 ↔ CSV 1행, 2번 ↔ 2행 … 을 (원본경로, 새이름, csv행) 튜플로. "s01_001" + ".jpg" = "s01_001.jpg".
    # ▸ zip 은 짧은 쪽에서 멈추지만 바로 위에서 길이가 같다는 걸 확인했으므로 안전하다. CSV 의 image_name 에는 확장자가 없으므로(metadata/README.md) 여기서 붙인다.
    return [
        (path, row["image_name"] + ".jpg", row)
        for path, row in zip(files_sorted, expected)
    ]


# ▸ 단어 분해: def main(③)() -> int(종료 코드를 돌려줌):
def main() -> int:
    """명령줄에서 실행됐을 때의 진입점.

    출력:
        종료 코드. 0이면 정상, 1이면 오류.
        (윈도우에서 `echo %ERRORLEVEL%` 로 확인할 수 있다)
    """
    parser = argparse.ArgumentParser(
        description="촬영 시각 순으로 사진 이름을 s01_001.jpg 형식으로 바꿔 복사한다."
    )
    parser.add_argument("session_id", help="세션 번호. 예: s01")
    # ▸ "--apply" action="store_true": 값을 받지 않고 붙었는지 여부만 True/False.
    # ▸ 왜 기본이 미리보기: 잘못된 매핑으로 35개 파일을 만들어 놓고 나중에 알아채는 것보다 먼저 눈으로 보는 편이 훨씬 싸다.
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 복사한다. 붙이지 않으면 무엇을 할지 출력만 한다",
    )
    args = parser.parse_args()

    # ▸ try / except (ValueError, FileNotFoundError) as e: 위 함수들이 낸 오류를 Traceback 대신 사람이 읽을 수 있는 메시지로.
    try:
        mapping = build_mapping(args.session_id)
    except (ValueError, FileNotFoundError) as e:
        print(f"\n[중단] {e}\n")
        return 1

    out_dir = RENAME_DIR / args.session_id

    # ▸ 단어 분해: if args.apply and out_dir.exists() and any(② 하나라도 참이면)(out_dir.iterdir()):
    # ▸ 뜻: --apply 이고, 출력 폴더가 있고, 그 안에 뭐라도 있으면 멈춘다. 빈 폴더는 통과.
    # ▸ 왜: 라벨링을 끝낸 뒤 실수로 다시 돌리면 Label Studio 가 물고 있는 파일이 바뀌어버린다. crop_session.py 도 같은 방어(그쪽은 폴더 존재만 본다).
    if args.apply and out_dir.exists() and any(out_dir.iterdir()):
        print(f"\n[중단] {out_dir} 에 이미 파일이 있습니다.")
        print("  덮어쓰지 않습니다. 폴더를 비우거나 옮긴 뒤 다시 실행하세요.\n")
        return 1

    # ▸ mode(③) = "실제 복사" if args.apply else "미리보기 (…)"   (조건식). 매핑표는 두 모드 모두 찍는다.
    # ▸ 왜 표를 찍나: CSV 의 의도한 개수를 함께 보여줘서 사진 몇 장만 열어봐도 짝이 맞는지 바로 확인할 수 있게.
    mode = "실제 복사" if args.apply else "미리보기 (파일을 만들지 않음)"
    print(f"\n세션 {args.session_id} / {len(mapping)}장 / {mode}")
    # ▸ f-string 안에 또 서식: {'새 이름':<16} = 글자 "새 이름" 을 왼쪽 정렬 16칸. 머리글 줄.
    print(f"{'새 이름':<16} {'원본':<18} {'볼트':>4} {'너트':>4} {'와셔':>4}  배치")
    print("-" * 62)
    # ▸ for src, new_name, row in mapping: 튜플 셋 언패킹. 두 f-string 을 나란히 두면 하나로 이어진다(암묵적 결합).
    for src, new_name, row in mapping:
        print(
            f"{new_name:<16} {src.name:<18} "
            f"{row['bolt_count']:>4} {row['nut_count']:>4} {row['washer_count']:>4}  {row['layout']}"
        )

    if not args.apply:
        print("\n위 짝이 맞으면 --apply 를 붙여 다시 실행하세요.")
        print(
            f"  ai-server\\.venv\\Scripts\\python.exe scripts\\rename_session.py {args.session_id} --apply\n"
        )
        return 0

    # ▸ out_dir.mkdir(parents=True(중간 폴더도), exist_ok=True(이미 있어도 오류 안 냄))
    out_dir.mkdir(parents=True, exist_ok=True)

    # ▸ map_path(③) = out_dir / "_rename_map.csv" : 복사 기록 파일.
    # ▸ 왜: 새 이름만 남으면 "이 사진이 원래 어느 파일이었나" 를 되짚을 수 없다. 라벨링 결과가 이상할 때 원본으로 거슬러 올라가는 유일한 연결고리.
    # ▸ 앞의 _ 는 사진 목록에서 눈에 띄게 하려는 것. crop_session.py 는 확장자로 걸러서 이 파일을 건드리지 않는다.
    map_path = out_dir / "_rename_map.csv"

    # ▸ for src, new_name, _(① 안 쓰는 값은 _ 로 받는 관례) in mapping:
    for src, new_name, _ in mapping:
        # ▸ shutil.copy2(② 복사)(src(원본), out_dir / new_name(새 경로)) : 내용과 함께 수정 시각도 복사한다. 원본(origin/)은 그대로 둔다.
        # ▸ 다른 선택: shutil.copy 는 수정 시각을 안 가져온다. Path.rename 은 "이동" 이라 원본이 사라진다 — 규칙 위반.
        shutil.copy2(src, out_dir / new_name)

    # ▸ 단어 분해: with open(map_path, "w"(쓰기 모드), newline="", encoding="utf-8") as f: writer(③) = csv.writer(② 행 쓰기 객체)(f)
    with open(map_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # ▸ writer.writerow(② 한 행 쓰기)([머리글 셋])
        writer.writerow(["new_name", "origin_name", "shot_time"])
        for src, new_name, _ in mapping:
            # ▸ shot_time, _sub = read_shot_time(src) : 여기서 EXIF 를 다시 읽는다. 위에서 읽은 값을 넘겨받아도 되지만
            #   기록 파일에 들어가는 값은 실제 파일에서 방금 읽은 것이어야 신뢰할 수 있다. _sub 는 안 쓴다.
            shot_time, _sub = read_shot_time(src)
            writer.writerow([new_name, src.name, shot_time])

    print(f"\n완료: {len(mapping)}장 → {out_dir}")
    print(f"복사 기록: {map_path}")
    print("원본(dataset/origin/)은 그대로 있습니다.\n")
    return 0


# ▸ 이 파일을 직접 실행했을 때만 main() 을 부른다. 다른 파일에서 import 할 때는 실행되지 않는다 — 파이썬의 표준 관용구.
# ▸ sys.exit(main()) : 반환값 0/1 을 종료 코드로.
if __name__ == "__main__":
    sys.exit(main())
