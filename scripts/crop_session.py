# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   웹캠이 16:9(1920x1080)로 찍은 사진을 **가운데 정사각형(1080x1080)** 으로 잘라
#   dataset/rename/<세션>/ → dataset/crop/<세션>/ 으로 저장한다.
#
#   왜 자르는가 (D-007 7절, 선택지 F)
#     YOLO 는 입력을 정사각형(imgsz=640)으로 맞춘다. 16:9 사진을 그대로 넣으면
#     긴 변(1920)을 640 에 맞추느라 전체가 줄고, 위아래에 회색 여백(레터박스)이 붙는다.
#     그러면 와셔가 36픽셀까지 작아져 목표선 40픽셀에 못 미친다.
#     먼저 가운데를 1:1 로 잘라내면 같은 imgsz=640 에서 와셔가 64픽셀이 된다.
#     실제로 같은 사진에서 레터박스는 8/6/6 오답, 1:1 크롭은 6/6/6 정답이었다 (D-007 7-5 검증 3).
#
#   왜 촬영이 아니라 코드로 자르는가 (D-007 Q47)
#     윈도우 카메라 앱이 1:1 저장을 지원하지 않아 1920x1080 으로만 저장된다.
#     그래서 찍은 뒤에 자른다.
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   촬영 → rename_session.py → [이 스크립트] → 라벨링(Label Studio) → 분할 → YOLO 학습
#
#   앞: dataset/rename/<세션>/  (rename_session.py --apply 가 만든 s02_001.jpg ...)
#   뒤: dataset/crop/<세션>/    (Label Studio 에 넣을 입력이 된다)
#
#   ⚠️ 반드시 **라벨링 전에** 돌린다.
#      라벨을 그린 뒤에 자르면 잘라낸 만큼 그림이 밀려서 박스 좌표가 전부 어긋난다.
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   - 중앙 크롭 : 이미지 가운데를 기준으로 정사각형을 오려내는 것.
#                 긴 변(가로)에서 양옆을 같은 양만큼 버리고, 짧은 변(세로)은 그대로 둔다.
#                 그래서 잘라낸 결과의 한 변은 항상 **짧은 변의 길이**가 된다.
#   - 좌표계 : Pillow 의 crop 은 (left, upper, right, lower) 네 값을 받는다.
#              원점 (0, 0) 은 **왼쪽 위**이고 아래로 갈수록 y 가 커진다. 수학 그래프와 반대다.
#              right 와 lower 는 "그 픽셀을 포함하지 않는" 경계다. 즉 [left, right) 구간이다.
#   - 촬영 규칙과 한 쌍이다 : 가운데를 자르므로 **트레이가 화면 정중앙**에 있어야 한다.
#              8/19 에 부품을 가로로 넓게 펼쳐 찍은 사진들을 크롭했더니 부품이 잘려나가
#              오히려 탐지가 나빠졌다 (D-007 7-5). 크롭은 공짜 개선이 아니다.
#   - s01 은 대상이 아니다 : 아이폰이 4284x4284 정사각으로 저장해서 자를 것이 없다.
#              이 스크립트는 이미 정사각인 사진을 만나면 자르지 않고 그대로 복사한다.
#
# 실행 방법
#   미리보기 (파일을 만들지 않고 무엇을 할지만 출력):
#     ai-server\.venv\Scripts\python.exe scripts\crop_session.py s02
#   실제 저장:
#     ai-server\.venv\Scripts\python.exe scripts\crop_session.py s02 --apply
#
# 관련 문서: docs/decisions.md D-007 7절, docs/foundations.md 2-8 / 2-10
# ─────────────────────────────────────────────────────────────────────────────

import argparse  # 명령줄 인자(s02, --apply)를 받아 파싱해주는 표준 라이브러리
import sys  # 오류가 났을 때 종료 코드 1로 빠져나가기 위해 사용 (sys.exit)
from pathlib import (
    Path,
)  # 경로를 문자열이 아니라 객체로 다룬다. 윈도우 역슬래시를 신경 쓰지 않아도 된다

from PIL import Image  # Pillow. 이미지 열기·자르기·저장을 담당한다

# 윈도우 콘솔 기본 인코딩(CP949)이 표현 못 하는 글자에서 프로그램이 죽는 것을 막는다.
# rename_session.py 에서 실제로 em dash 에 걸렸던 것과 같은 대비다.
sys.stdout.reconfigure(errors="replace")

# ── 경로 상수 ────────────────────────────────────────────────────────────────
# scripts/crop_session.py → scripts → 루트. 어느 폴더에서 실행해도 경로가 어긋나지 않는다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RENAME_DIR = PROJECT_ROOT / "dataset" / "rename"  # 이름을 바꾼 사본이 있는 곳 (입력)
CROP_DIR = PROJECT_ROOT / "dataset" / "crop"  # 정사각으로 자른 사본이 놓일 곳 (출력)

# 처리 대상 확장자. 소문자로 비교한다 (D-009 Q15에서 파일명은 소문자로 정했다).
IMAGE_SUFFIXES = {".jpg", ".jpeg"}

# JPEG 저장 품질. 자르고 다시 저장하면 JPEG 이 한 번 더 압축되므로 화질이 조금 깎인다.
# 95 는 육안으로 차이를 알기 어려우면서 파일 크기가 지나치게 커지지 않는 값이다.
# 100 으로 두면 압축을 거의 안 해 용량만 커지고 얻는 것이 없다.
JPEG_QUALITY = 95


def center_square_box(width, height):
    """이미지 크기를 받아 가운데 정사각형의 자르기 좌표를 계산한다.

    입력:
        width  (int): 원본 가로 픽셀 수. 예: 1920
        height (int): 원본 세로 픽셀 수. 예: 1080
    출력:
        (left, upper, right, lower) 네 정수로 이루어진 튜플.
        Pillow 의 Image.crop 에 그대로 넘길 수 있는 형태다.
        예: (1920, 1080) → (420, 0, 1500, 1080)
            가로 1920 에서 양옆 420 씩 버리면 1080 이 남는다.
    실패 시:
        너비나 높이가 0 이하이면 ValueError.
    """
    # 방어: 0이나 음수가 들어오면 이후 계산이 조용히 이상해진다. 여기서 멈추는 편이 낫다.
    if width <= 0 or height <= 0:
        raise ValueError(f"이미지 크기가 이상하다: {width}x{height}")

    # 정사각형 한 변은 가로·세로 중 **짧은 쪽**이다.
    # 긴 쪽을 기준으로 잡으면 원본 밖의 영역을 자르게 되어 검은 여백이 생긴다.
    side = min(width, height)

    # 버릴 양(긴 변 - side)을 양쪽에 반씩 나눈다. 그래야 가운데가 남는다.
    # // 는 몫만 남기는 나눗셈(정수 나눗셈)이다. / 를 쓰면 420.0 같은 소수가 나오는데,
    # 픽셀 좌표는 정수여야 해서 Pillow 가 받아주지 않는다.
    # 1920 → (1920 - 1080) // 2 = 420. 세로는 (1080 - 1080) // 2 = 0 이라 위아래는 안 자른다.
    left = (width - side) // 2
    upper = (height - side) // 2

    # 오른쪽·아래쪽 경계는 시작점에서 한 변 길이만큼 더한 값이다.
    # (left, right) 가 [left, right) 반열린 구간이라 right - left 가 정확히 side 가 된다.
    right = left + side
    lower = upper + side

    return (left, upper, right, lower)


def build_plan(session_id):
    """세션 폴더를 훑어서 "무엇을 어떻게 자를지" 목록을 만든다.

    파일을 만들지 않고 계획만 세운다. 미리보기와 실제 저장이 **같은 계획**을 쓰게 하려는 것이다.
    미리보기에서 본 것과 다른 일이 벌어지면 미리보기의 의미가 없어진다.

    입력:
        session_id (str): 세션 번호. 예: "s02"
    출력:
        리스트. 각 원소는 (src, dst, size, box) 네 개짜리 튜플이다.
            src  (Path)  : 입력 파일 경로
            dst  (Path)  : 출력 파일 경로
            size (tuple) : 원본 크기 (가로, 세로). 예: (1920, 1080)
            box  (tuple) : 자를 좌표. 이미 정사각이면 None (자르지 않고 복사한다는 뜻)
        예: [(.../s02_001.jpg, .../s02_001.jpg, (1920, 1080), (420, 0, 1500, 1080)), ...]
    실패 시:
        입력 폴더가 없으면 FileNotFoundError.
        폴더에 대상 이미지가 하나도 없으면 ValueError.
    """
    src_dir = RENAME_DIR / session_id

    # 폴더가 없으면 세션 번호를 잘못 쳤거나 rename_session.py 를 아직 안 돌린 것이다.
    if not src_dir.is_dir():
        raise FileNotFoundError(
            f"입력 폴더가 없다: {src_dir}\n"
            f"  rename_session.py {session_id} --apply 를 먼저 돌렸는지 확인할 것"
        )

    # sorted 로 이름순 정렬한다. 이 단계에서는 촬영 시각이 필요 없다 —
    # 번호(s02_001, s02_002 ...)는 rename_session.py 가 이미 시각 순으로 붙여놨기 때문이다.
    # 정렬하는 이유는 미리보기 출력이 매번 같은 순서로 나오게 하기 위해서다.
    files = sorted(
        p
        for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )

    if not files:
        raise ValueError(f"자를 이미지가 없다: {src_dir}")

    plan = []
    for src in files:
        # with 문: 블록을 벗어나면 파일을 자동으로 닫는다.
        # 35개를 열어놓고 안 닫으면 파일 핸들이 쌓여 나중에 저장이 실패할 수 있다.
        with Image.open(src) as im:
            width, height = im.size  # im.size 는 (가로, 세로) 튜플이다

        # 이미 정사각이면 자를 것이 없다. box 를 None 으로 두어 "그대로 복사"를 표시한다.
        # s01(아이폰 4284x4284)이 이 경우다. 굳이 crop 을 부르면 같은 그림을 다시 저장할 뿐이고,
        # JPEG 은 저장할 때마다 다시 압축되므로 화질만 깎인다.
        box = None
        if width != height:
            box = center_square_box(width, height)

        plan.append((src, CROP_DIR / session_id / src.name, (width, height), box))

    return plan


def apply_plan(plan):
    """계획대로 실제 파일을 만든다.

    입력:
        plan (list): build_plan 이 돌려준 목록
    출력:
        없음. 파일 시스템에 이미지를 쓴다.
    실패 시:
        출력 폴더가 이미 있으면 FileExistsError. 덮어쓰지 않고 멈춘다.
    """
    out_dir = plan[0][1].parent  # 모든 dst 가 같은 폴더이므로 첫 항목에서 꺼내면 된다

    # 이미 결과가 있으면 덮어쓰기 전에 멈춘다.
    # 라벨링을 끝낸 뒤 실수로 다시 돌리면 Label Studio 가 물고 있는 파일이 바뀌어버린다.
    # rename_session.py 도 같은 방어를 한다.
    if out_dir.exists():
        raise FileExistsError(
            f"{out_dir}에 이미 파일이 있습니다. 폴더를 비우거나 옮긴 뒤 다시 실행하세요"
        )

    # parents=True: 중간 폴더(dataset/crop)가 없으면 같이 만든다.
    # exist_ok=True: 위 검사를 통과했으므로 여기서 또 예외가 나지 않게 한다.
    out_dir.mkdir(parents=True, exist_ok=True)

    for src, dst, size, box in plan:
        with Image.open(src) as im:
            # box 가 None 이면 이미 정사각이라는 뜻이다. 자르지 않고 원본 그대로 쓴다.
            out = im if box is None else im.crop(box)

            # quality: 위에서 정한 JPEG 압축 품질.
            # subsampling=0: 색 정보를 줄이지 않는다. 부품 경계(육각/원)가 판단 근거라
            #                색을 뭉개면 와셔와 너트를 가르는 외곽선이 흐려질 수 있다.
            out.save(dst, quality=JPEG_QUALITY, subsampling=0)

    print(f"\n{len(plan)}장 저장 완료 -> {out_dir}\n")


def main():
    """명령줄에서 실행됐을 때의 진입점.

    입력:
        명령줄 인자. session_id (필수), --apply (선택)
    출력:
        종료 코드. 0이면 정상, 1이면 오류.
    """
    parser = argparse.ArgumentParser(
        description="웹캠 16:9 사진을 가운데 정사각형으로 잘라 dataset/crop/ 에 저장한다."
    )
    parser.add_argument("session_id", help="세션 번호. 예: s02")
    # action="store_true": 값을 받지 않고 붙었는지 여부만 True/False 로 준다.
    # 기본을 미리보기로 둔 이유는 rename_session.py 와 같다 —
    # 35장을 잘못 잘라놓고 나중에 알아채는 것보다 먼저 눈으로 보는 편이 훨씬 싸다.
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 저장한다. 붙이지 않으면 무엇을 할지 출력만 한다",
    )
    args = parser.parse_args()

    # try/except: 위 함수들이 낸 오류를 파이썬 기본 오류 화면 대신 읽을 수 있는 문장으로 보여준다.
    try:
        plan = build_plan(args.session_id)
    except (ValueError, FileNotFoundError) as e:
        print(f"\n[중단] {e}\n")
        return 1

    if not args.apply:
        print(
            f"\n세션 {args.session_id} / {len(plan)}장 / 미리보기 (파일을 만들지 않음)"
        )
        print("파일             원본 크기      자른 뒤      자르기 좌표")
        print("-" * 66)
        for src, dst, size, box in plan:
            origin = f"{size[0]}x{size[1]}"
            if box is None:
                after = origin
                note = "정사각 - 그대로 복사"
            else:
                side = box[2] - box[0]
                after = f"{side}x{side}"
                note = str(box)
            print(f"{src.name:<16} {origin:>12} {after:>12}   {note}")
        print("\n위가 맞으면 --apply 를 붙여 다시 실행하세요.")
        print(
            f"  ai-server\\.venv\\Scripts\\python.exe scripts\\crop_session.py {args.session_id} --apply\n"
        )
        return 0

    try:
        apply_plan(plan)
    except FileExistsError as e:
        print(f"\n[중단] {e}\n")
        return 1

    return 0


# __name__ == "__main__": 이 파일을 직접 실행했을 때만 main() 을 부른다.
# 다른 파일이 import 했을 때는 실행되지 않는다.
if __name__ == "__main__":
    sys.exit(main())
