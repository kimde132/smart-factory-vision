# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   카메라가 붙인 이름(IMG_E8821.JPG)을 우리 규칙(s01_001.jpg)으로 바꿔서
#   dataset/origin/<세션>/ → dataset/rename/<세션>/ 으로 복사한다.
#
#   순서는 파일 이름이나 파일 수정 시각이 아니라
#   **사진 안에 박혀 있는 EXIF 촬영 시각**으로 정한다.
#   파일 수정 시각은 PC로 옮기는 순간 "옮긴 시각"으로 바뀌어버려서 믿을 수 없다.
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   촬영(s01 35장) → [이 스크립트] → 라벨링(Label Studio) → 분할 스크립트 → YOLO 학습
#
#   앞: 사람이 손으로 카메라에서 PC로 옮겨둔 dataset/origin/<세션>/
#   뒤: dataset/rename/<세션>/ 이 Label Studio에 넣을 입력이 된다
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   - EXIF : 사진 파일 안에 같이 저장되는 촬영 정보(시각, 카메라, 렌즈 등).
#            이미지 데이터와 한 파일에 들어 있어서 복사해도 따라다닌다.
#   - 원본을 덮어쓰지 않는다 : origin/ 은 손대지 않고 rename/ 에 사본을 만든다.
#            규칙이 틀렸다는 걸 나중에 알아도 origin/ 에서 다시 시작할 수 있다 (D-009 Q17).
#   - 순서가 곧 정답 : metadata/images.csv 는 촬영 전에 미리 채워둔 "의도한 개수" 표다.
#            001번 사진이 CSV 1행과 짝이 맞는다는 전제가 깨지면
#            라벨링 검수(labeling-guide.md 7절)가 전부 무의미해진다.
#
# 실행 방법
#   미리보기 (파일을 건드리지 않고 무엇을 할지만 출력):
#     ai-server\.venv\Scripts\python.exe scripts\rename_session.py s01
#   실제 복사:
#     ai-server\.venv\Scripts\python.exe scripts\rename_session.py s01 --apply
#
# 관련 문서: docs/decisions.md D-009 (4·5·7절), metadata/README.md
# ─────────────────────────────────────────────────────────────────────────────

import argparse  # 명령줄 인자(s01, --apply)를 받아 파싱해주는 표준 라이브러리
import csv       # metadata/images.csv 를 읽는다. 쉼표 분리를 직접 짜면 값 안의 쉼표에서 깨진다
import shutil    # 파일 복사(shutil.copy2). copy2 는 내용뿐 아니라 수정 시각까지 함께 복사한다
import sys       # 오류가 났을 때 종료 코드 1로 빠져나가기 위해 사용 (sys.exit)
from pathlib import Path  # 경로를 문자열이 아니라 객체로 다룬다. 윈도우 역슬래시를 신경 쓰지 않아도 된다

from PIL import Image, ExifTags  # Pillow. 이미지 열기와 EXIF 태그 이름표를 제공한다

# 윈도우 콘솔의 기본 인코딩은 CP949(한국어 완성형)라서 유니코드 기호 일부를 출력하지 못하고
# UnicodeEncodeError 로 프로그램 전체가 죽는다. 실제로 여기서 em dash(—)에 걸렸다.
# errors="replace" 는 표현 못 하는 글자를 '?' 로 바꿔서 넘어가게 한다.
# 출력 한 글자 때문에 35장 처리가 통째로 실패하는 것보다 낫다.
sys.stdout.reconfigure(errors="replace")

# ── 경로 상수 ────────────────────────────────────────────────────────────────
# __file__ 은 이 스크립트 파일의 경로. .resolve() 로 절대경로를 만들고
# .parent 를 두 번 올라가면 프로젝트 루트다 (scripts/rename_session.py → scripts → 루트).
# 이렇게 하면 어느 폴더에서 실행해도 경로가 어긋나지 않는다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORIGIN_DIR = PROJECT_ROOT / "dataset" / "origin"   # 카메라에서 꺼낸 원본이 있는 곳
RENAME_DIR = PROJECT_ROOT / "dataset" / "rename"   # 규칙대로 이름을 바꾼 사본이 놓일 곳
IMAGES_CSV = PROJECT_ROOT / "metadata" / "images.csv"  # 사진당 1행짜리 계획표

# 처리 대상 확장자. 대소문자를 섞어 쓰는 카메라가 있어 소문자로 비교한다.
# 아이폰은 .JPG(대문자)로 저장하는데 우리 규칙은 소문자 .jpg 다 (D-009 Q15).
IMAGE_SUFFIXES = {".jpg", ".jpeg"}

# EXIF 태그는 파일 안에 숫자 ID로 저장된다. 사람이 읽는 이름 → 숫자 ID 사전을 만들어 둔다.
# 예: "DateTimeOriginal" → 36867
# ExifTags.TAGS 는 {숫자: 이름} 이므로 뒤집어서 {이름: 숫자} 로 만든다.
TAG_ID = {name: num for num, name in ExifTags.TAGS.items()}

# EXIF 안에서 촬영 관련 태그들이 모여 있는 하위 구역(Exif IFD)의 주소.
# DateTimeOriginal 은 최상위가 아니라 이 하위 구역에 들어 있다.
EXIF_IFD_POINTER = 0x8769


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
    # with 문: 파일을 열고, 블록이 끝나면 예외가 나든 말든 반드시 닫아준다.
    with Image.open(path) as im:
        exif = im.getexif()  # 최상위 EXIF. dict 처럼 쓰지만 실제로는 Exif 객체다

    # get_ifd() 로 촬영 정보가 모여 있는 하위 구역을 꺼낸다.
    # EXIF가 없는 파일이면 빈 dict 가 돌아온다.
    exif_ifd = exif.get_ifd(EXIF_IFD_POINTER)

    # 촬영한 순간의 시각. 파일을 복사해도 바뀌지 않는다.
    # (참고: DateTime 은 "파일이 마지막으로 손댄 시각"이라 목적이 다르다)
    shot_time = exif_ifd.get(TAG_ID["DateTimeOriginal"])

    if not shot_time:
        raise ValueError(
            f"{path.name}: EXIF 촬영 시각(DateTimeOriginal)이 없습니다.\n"
            f"  카톡·메일로 옮기면 EXIF가 지워집니다. 케이블이나 구글 드라이브로 다시 옮기세요."
        )

    # 1초 미만 단위. 연사로 찍으면 같은 초에 여러 장이 들어가므로 정렬의 보조 기준이 된다.
    # 없는 카메라도 있어서 기본값을 "" 로 둔다.
    subsec = exif_ifd.get(TAG_ID.get("SubsecTimeOriginal"), "") or ""

    # str() 로 감싸는 이유: 카메라에 따라 숫자 타입으로 들어오는 경우가 있는데
    # 정렬할 때 문자열과 숫자가 섞이면 파이썬이 비교하지 못하고 터진다.
    return str(shot_time), str(subsec)


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
    # newline="" 는 csv 모듈이 요구하는 관례다. 이걸 빼면 윈도우에서 빈 줄이 끼어 읽힌다.
    # encoding="utf-8-sig" 는 파일 맨 앞에 BOM(눈에 안 보이는 표식)이 있어도 벗겨준다.
    # 메모장으로 저장하면 BOM이 붙는데, 그러면 첫 컬럼 이름이 "﻿image_name" 이 되어
    # row["image_name"] 가 KeyError 로 터진다.
    with open(IMAGES_CSV, newline="", encoding="utf-8-sig") as f:
        # DictReader: 첫 줄을 컬럼 이름으로 삼아 각 행을 dict 로 만들어준다.
        # row[0] 대신 row["bolt_count"] 로 쓸 수 있어 컬럼 순서가 바뀌어도 안전하다.
        reader = csv.DictReader(f)
        # 리스트 컴프리헨션: for 를 한 줄로 쓴 것. 조건에 맞는 행만 골라 리스트로 만든다.
        # image_name 이 "s01_001" 형태이므로 "s01_" 로 시작하는지 보면 세션이 갈린다.
        # (별도 session_id 컬럼을 두지 않은 이유가 이것이다 — metadata/README.md)
        rows = [r for r in reader if r["image_name"].startswith(session_id + "_")]

    if not rows:
        raise ValueError(
            f"metadata/images.csv 에 '{session_id}_' 로 시작하는 행이 없습니다.\n"
            f"  촬영 전에 CSV를 먼저 채우는 것이 규칙입니다 (metadata/README.md)."
        )
    return rows


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

    # iterdir(): 폴더 안의 항목을 하나씩 돌려준다.
    # p.suffix 는 확장자(".JPG"), .lower() 로 소문자로 만들어 대소문자 차이를 없앤다.
    # p.is_file() 로 하위 폴더는 걸러낸다.
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]

    if not files:
        raise FileNotFoundError(f"{folder} 안에 이미지 파일이 없습니다.")
    return files


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

    # 각 파일의 촬영 시각을 미리 읽어둔다.
    # {경로: ("2026:08:18 23:21:28", "482")} 형태의 사전.
    # 정렬할 때마다 파일을 다시 여는 것을 피하려고 한 번만 읽는다.
    shot_times = {p: read_shot_time(p) for p in files}

    # 촬영 시각이 겹치는 사진이 있는지 검사한다.
    # 겹치면 정렬 결과가 실행할 때마다 달라질 수 있고,
    # 그러면 CSV의 개수와 사진이 어긋나는데 눈으로는 알아채기 어렵다.
    seen: dict[tuple[str, str], Path] = {}
    for path, stamp in shot_times.items():
        if stamp in seen:
            raise ValueError(
                f"촬영 시각이 같은 사진이 두 장 있습니다: {seen[stamp].name}, {path.name} ({stamp[0]})\n"
                f"  어느 쪽이 먼저인지 정할 수 없어 중단합니다. 둘 중 하나가 중복 사진인지 확인하세요."
            )
        seen[stamp] = path

    # 촬영 시각 순으로 줄을 세운다. key= 에 넘긴 함수의 반환값이 정렬 기준이 된다.
    # shot_times[p] 는 ("시각", "1초미만") 튜플이고, 튜플은 앞 원소부터 차례로 비교된다.
    files_sorted = sorted(files, key=lambda p: shot_times[p])

    # 사진 수와 CSV 행 수가 맞는지 본다. 여기서 걸리면 뒤 작업이 전부 어긋나므로 반드시 멈춘다.
    if len(files_sorted) != len(expected):
        raise ValueError(
            f"사진 {len(files_sorted)}장 / CSV {len(expected)}행 — 개수가 다릅니다.\n"
            f"  실패한 사진을 안 지웠거나, 계획표대로 다 찍지 않았을 수 있습니다.\n"
            f"  개수를 맞추기 전에는 이름을 바꾸지 않습니다."
        )

    # zip(): 두 리스트를 앞에서부터 짝지어 준다. 짧은 쪽에서 멈추지만
    # 바로 위에서 길이가 같다는 걸 확인했으므로 안전하다.
    # CSV의 image_name 에는 확장자가 없으므로(metadata/README.md) 여기서 ".jpg" 를 붙인다.
    return [
        (path, row["image_name"] + ".jpg", row)
        for path, row in zip(files_sorted, expected)
    ]


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
    # action="store_true": 값을 받지 않고 붙었는지 여부만 True/False 로 준다.
    # 기본을 미리보기로 둔 이유는, 잘못된 매핑으로 35개 파일을 만들어 놓고
    # 나중에 알아채는 것보다 먼저 눈으로 보는 편이 훨씬 싸기 때문이다.
    parser.add_argument("--apply", action="store_true",
                        help="실제로 복사한다. 붙이지 않으면 무엇을 할지 출력만 한다")
    args = parser.parse_args()

    # try/except: 위 함수들이 낸 오류를 잡아서 파이썬 기본 오류 화면(Traceback) 대신
    # 사람이 읽을 수 있는 메시지로 보여준다.
    try:
        mapping = build_mapping(args.session_id)
    except (ValueError, FileNotFoundError) as e:
        print(f"\n[중단] {e}\n")
        return 1

    out_dir = RENAME_DIR / args.session_id

    # 이미 결과가 있으면 덮어쓰기 전에 멈춘다.
    # 라벨링을 끝낸 뒤 실수로 다시 돌리면 Label Studio가 물고 있는 파일이 바뀌어버린다.
    if args.apply and out_dir.exists() and any(out_dir.iterdir()):
        print(f"\n[중단] {out_dir} 에 이미 파일이 있습니다.")
        print("  덮어쓰지 않습니다. 폴더를 비우거나 옮긴 뒤 다시 실행하세요.\n")
        return 1

    # 매핑표를 출력한다. CSV의 의도한 개수를 함께 보여줘서
    # 사진 몇 장만 열어봐도 짝이 맞는지 바로 확인할 수 있게 한다.
    mode = "실제 복사" if args.apply else "미리보기 (파일을 만들지 않음)"
    print(f"\n세션 {args.session_id} / {len(mapping)}장 / {mode}")
    print(f"{'새 이름':<16} {'원본':<18} {'볼트':>4} {'너트':>4} {'와셔':>4}  배치")
    print("-" * 62)
    for src, new_name, row in mapping:
        print(f"{new_name:<16} {src.name:<18} "
              f"{row['bolt_count']:>4} {row['nut_count']:>4} {row['washer_count']:>4}  {row['layout']}")

    if not args.apply:
        print("\n위 짝이 맞으면 --apply 를 붙여 다시 실행하세요.")
        print(f"  ai-server\\.venv\\Scripts\\python.exe scripts\\rename_session.py {args.session_id} --apply\n")
        return 0

    # mkdir(parents=True): 중간 폴더가 없으면 같이 만든다.
    # exist_ok=True: 이미 있어도 오류를 내지 않는다.
    out_dir.mkdir(parents=True, exist_ok=True)

    # 복사 기록을 남긴다. 새 이름만 남으면 "이 사진이 원래 어느 파일이었나"를 되짚을 수 없다.
    # 라벨링 결과가 이상할 때 원본으로 거슬러 올라가는 유일한 연결고리다.
    map_path = out_dir / "_rename_map.csv"

    for src, new_name, _ in mapping:
        # copy2 는 내용과 함께 수정 시각도 복사한다. 원본(origin/)은 그대로 둔다.
        shutil.copy2(src, out_dir / new_name)

    with open(map_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["new_name", "origin_name", "shot_time"])
        for src, new_name, _ in mapping:
            # 여기서 EXIF를 다시 읽는다. 위에서 읽은 값을 넘겨받아도 되지만
            # 기록 파일에 들어가는 값은 실제 파일에서 방금 읽은 것이어야 신뢰할 수 있다.
            shot_time, _sub = read_shot_time(src)
            writer.writerow([new_name, src.name, shot_time])

    print(f"\n완료: {len(mapping)}장 → {out_dir}")
    print(f"복사 기록: {map_path}")
    print("원본(dataset/origin/)은 그대로 있습니다.\n")
    return 0


# 이 파일을 직접 실행했을 때만 main()을 부른다.
# 다른 파일에서 import 할 때는 실행되지 않는다 — 파이썬의 표준 관용구다.
if __name__ == "__main__":
    sys.exit(main())
