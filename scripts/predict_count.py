# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   학습이 끝난 모델(best.pt)로 폴더의 사진을 한 장씩 추론해 **클래스별 부품 개수**를 세고,
#   metadata/images.csv 에 적힌 실제 개수와 대조해 **틀린 사진 목록과 사진 단위 개수 정답률**을 출력한다.
#   --save 를 붙이면 박스와 클래스 이름을 그려 넣은 사진을 runs/predict/ 에 저장한다.
#
#   ★ 이 프로젝트의 지표는 mAP가 아니라 이 스크립트가 내는 "사진 단위 개수 정답률"이다.
#     mAP는 박스 하나하나를 채점하지만, 검사 장비의 OK/NG는 사진 한 장의 세 개수가 전부 맞아야 OK다.
#     혼동 행렬에는 안 보이는 오류(한 물체에 박스 두 개, 가장자리 헛것)가 여기서 드러난다 (experiment-log.md EXP-01).
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   train.py(Colab) → best.pt 를 runs/<실험명>/weights/ 에 받아옴 → [현재 파일] → 틀린 사진을 눈으로 확인(#21 실패 분석)
#
#   앞: runs/exp01_6sessions/weights/best.pt 와 metadata/images.csv 가 있어야 한다.
#       대상 폴더의 사진 이름(s04_005)이 images.csv 의 image_name 과 같아야 한다.
#   뒤: 여기의 "추론 → 개수 세기 → 기대 개수와 대조" 세 단계가 그대로 FastAPI 서버의 OK/NG 판정 로직이 된다.
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   추론(inference) : 학습이 끝난 모델에 새 사진을 넣어 답을 받는 것. 학습과 달리 가중치를 고치지 않는다.
#   추론 결과의 모양 : model.predict(사진) 은 리스트를 돌려주고 [0] 이 그 사진의 결과(Results 객체)다.
#       result.boxes.cls  → shape (박스 수,)     각 박스의 클래스 번호. 예: tensor([2., 0., 1.])
#       result.boxes.conf → shape (박스 수,)     각 박스의 확신도 0~1
#       result.boxes.xyxy → shape (박스 수, 4)   각 행이 [x1, y1, x2, y2] 픽셀 좌표
#       result.names      → {0: 'bolt', 1: 'nut', 2: 'washer'}  (학습 때 data.yaml 에서 가져온 것)
#   conf 임계값 : 모델은 확신도가 낮은 박스도 잔뜩 내놓는다. conf 이상인 것만 남긴다.
#       올리면 헛것이 줄고 진짜를 놓치기 시작한다. 개수 정답률을 직접 바꾸는 손잡이라 인자로 받는다.
#       EXP-01 val 기준: 0.25 → 80.0%, 0.4 → 85.7%, 0.6 → 85.7%(진짜 와셔를 놓치기 시작).
#   NMS (Non-Max Suppression) : 한 물체에 겹쳐 나온 박스들을 하나로 정리하는 절차. 모델 안에서 predict 때 자동으로 돈다.
#       같은 클래스끼리만 합치고, 겹침(IoU)이 0.7 미만이면 같은 클래스여도 안 합친다.
#       그래서 한 와셔에 nut 0.52 + washer 0.39 두 박스가 남는 일이 생긴다(s04_008).
#
# 실행 방법 (프로젝트 최상위에서, 반드시 ai-server 가상환경의 파이썬으로)
#     ai-server\.venv\Scripts\python.exe scripts\predict_count.py dataset\result_data\images\val --save
#     ai-server\.venv\Scripts\python.exe scripts\predict_count.py dataset\result_data\images\val --conf 0.4
#
# 관련 문서:
#   docs/experiment-log.md EXP-01 3절 (이 스크립트가 낸 결과와 오류 세 종류),
#   docs/decisions.md D-004 (너트↔와셔 혼동 리스크), scripts/verify_counts.py (CSV 읽는 함수의 원본)
# ─────────────────────────────────────────────────────────────────────────────

import argparse  # 명령줄 인자(폴더, --weights, --conf, --save)를 받아 파싱해주는 표준 라이브러리

from pathlib import Path  # 경로를 문자열이 아니라 객체로 다룬다. "/" 로 이어붙이고 .stem, .is_dir() 같은 메서드를 쓴다

# ultralytics 의 YOLO 클래스. .pt 파일을 주면 모델을 메모리에 올리고, .predict() 로 추론한다.
from ultralytics import YOLO

# 같은 scripts/ 폴더의 verify_counts.py 에서 함수를 빌린다 (split_dataset.py 와 같은 방식).
# images.csv 를 {사진이름: {'bolt': n, 'nut': n, 'washer': n}} 로 읽어준다.
# ★ 아래 count_boxes 가 내는 예측 결과도 정확히 이 모양으로 맞춘다. 모양이 같아야 == 한 번으로 비교된다.
from verify_counts import load_planned_counts

# __file__ 은 이 파일의 경로. .parent 를 두 번 올라가면 프로젝트 최상위다. 어디서 실행하든 경로가 흔들리지 않는다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 기본 가중치. EXP-01 의 best.pt (epoch 80). 다른 실험을 채점할 때는 --weights 로 바꾼다.
DEFAULT_WEIGHTS = PROJECT_ROOT / "runs" / "exp01_6sessions" / "weights" / "best.pt"
# 사진별 실제 개수(채점표). 9/3 이후 실제 값과 일치한다 (verify_counts.py 로 검증됨).
CSV_PATH = PROJECT_ROOT / "metadata" / "images.csv"
# 클래스 이름. 순서는 data.yaml / labeling-guide.md 1-1 과 같다. 개수 딕셔너리의 키를 만들 때 쓴다.
CLASS_NAMES = ("bolt", "nut", "washer")
# 대상 폴더에서 사진만 고르기 위한 확장자 집합. 소문자로 비교한다.
IMAGE_SUFFIXES = {".jpg", ".jpeg"}


def count_boxes(result):
    """한 장의 추론 결과에서 클래스별 박스 개수를 센다.

    입력:
        result: model.predict(...)[0]. ultralytics Results 객체.
                result.boxes.cls 가 박스마다의 클래스 번호 텐서, result.names 가 번호 → 이름 딕셔너리.

    출력:
        딕셔너리. 예: {'bolt': 1, 'nut': 3, 'washer': 5}
        load_planned_counts 가 돌려주는 안쪽 딕셔너리와 같은 모양이다. 탐지 0개인 클래스도 0 으로 들어 있다.

    실패 시:
        예외는 나지 않는다. 박스가 하나도 없으면 전부 0 인 딕셔너리를 돌려준다 (빈 트레이가 그렇다).
    """
    # 세 클래스를 먼저 0 으로 깔아둔다 (딕셔너리 컴프리헨션).
    # 안 그러면 탐지 0개인 클래스가 딕셔너리에 없어서 CSV 쪽과 모양이 달라지고 비교가 어긋난다.
    counts = {name: 0 for name in CLASS_NAMES}
    # boxes.cls 는 PyTorch 텐서라 .tolist() 로 파이썬 리스트로 바꾼다. 값이 2.0 처럼 실수로 들어 있다.
    for cls_id in result.boxes.cls.tolist():
        # int() 로 정수로 바꿔 names 에서 이름을 찾고, 그 이름의 칸을 1 올린다.
        counts[result.names[int(cls_id)]] += 1
    return counts


def predict_folder(model, image_dir, conf, save_dir=None):
    """폴더의 사진을 한 장씩 추론해 사진별 클래스 개수를 모은다.

    입력:
        model (YOLO): 가중치를 올린 모델 객체
        image_dir (Path): 사진 폴더. 예: dataset/result_data/images/val
        conf (float): 이 확신도 이상인 박스만 센다. 예: 0.25
        save_dir (Path | None): 박스를 그린 사진을 저장할 폴더. None 이면 저장하지 않는다

    출력:
        딕셔너리. {사진이름: {'bolt': n, 'nut': n, 'washer': n}}. 예: {'s04_001': {'bolt': 0, 'nut': 2, 'washer': 4}, ...}
        키는 확장자를 뗀 파일명이라 images.csv 의 image_name 과 바로 맞는다.

    실패 시:
        폴더에 사진이 없으면 빈 딕셔너리를 돌려준다 (main 에서 0 으로 나누다 ZeroDivisionError 가 난다).
        사진 파일이 깨져 있으면 ultralytics 쪽에서 예외가 올라온다.
    """
    predicted = {}
    # iterdir() 로 폴더 안 항목을 훑고, 확장자가 사진인 것만 고른다. sorted 는 출력 순서를 s04_001 부터로 고정하려는 것.
    image_paths = sorted(
        p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    )
    for image_path in image_paths:
        # imgsz=640 : 학습과 같은 크기. 다르게 주면 부품이 차지하는 픽셀이 달라져 성능이 바뀐다.
        # conf      : 이 값 미만 박스는 모델 안에서 버려지고 나온다.
        # verbose=False : 장마다 찍히는 로그를 끈다. 35줄이 쏟아지면 결과가 안 보인다.
        # [0] : predict 는 리스트를 돌려주고(여러 장을 한꺼번에 넣을 수 있어서), 한 장이라 첫 원소만 쓴다.
        result = model.predict(image_path, imgsz=640, conf=conf, verbose=False)[0]
        # .stem 은 확장자를 뗀 파일명. s04_005.jpg → s04_005. images.csv 의 키와 같다.
        predicted[image_path.stem] = count_boxes(result)
        if save_dir is not None:
            # 박스·클래스 이름·확신도를 그려 넣은 사진을 같은 이름으로 저장한다. 틀린 사진을 눈으로 볼 때 쓴다.
            result.save(filename=str(save_dir / image_path.name))
    return predicted


def compare(predicted, planned):
    """예측 개수와 images.csv 의 실제 개수를 사진마다 대조해 다른 것만 모은다.

    입력:
        predicted (dict): predict_folder 가 돌려준 {사진이름: {부품: 개수}}
        planned (dict): load_planned_counts 가 돌려준 {사진이름: {부품: 개수}} (images.csv 전체, 210장)

    출력:
        리스트. 각 원소는 (사진이름, 실제 개수 딕셔너리, 예측 개수 딕셔너리).
        예: [('s04_004', {'bolt': 0, 'nut': 2, 'washer': 4}, {'bolt': 0, 'nut': 3, 'washer': 3}), ...]
        전부 맞으면 빈 리스트.

    실패 시:
        예측한 사진이 images.csv 에 없으면 KeyError. 조용히 건너뛰면 정답률의 분모가 틀어지므로 멈춘다.
    """
    mismatches = []
    for name, pred in predicted.items():
        if name not in planned:
            raise KeyError(f"images.csv 에 없는 사진이다: {name}")
        # 두 딕셔너리가 같은 모양({'bolt':..,'nut':..,'washer':..})이라 != 한 번에 세 클래스가 전부 비교된다.
        # 하나라도 다르면 그 사진은 NG 다.
        if pred != planned[name]:
            mismatches.append((name, planned[name], pred))
    return mismatches


def main():
    """명령줄에서 실행됐을 때의 진입점.

    입력:
        명령줄 인자. image_dir (필수), --weights, --conf, --save (선택)

    출력:
        종료 코드. 0이면 정상, 1이면 오류. 화면에 정답률과 틀린 사진 표를 찍는다.
    """
    parser = argparse.ArgumentParser(
        description="best.pt 로 폴더의 사진마다 부품 개수를 세고 images.csv 와 대조한다."
    )
    parser.add_argument(
        "image_dir", help="사진 폴더. 예: dataset/result_data/images/val"
    )
    # str() 로 감싸는 이유: argparse 의 default 는 문자열이 자연스럽고, YOLO() 도 문자열 경로를 받는다.
    parser.add_argument(
        "--weights", default=str(DEFAULT_WEIGHTS), help="모델 가중치 .pt 경로"
    )
    # type=float 가 없으면 "0.4" 문자열이 그대로 넘어가 predict 에서 에러가 난다.
    parser.add_argument(
        "--conf", type=float, default=0.25, help="이 확신도 이상인 박스만 센다."
    )
    # action="store_true" : 플래그. 붙이면 True, 안 붙이면 False.
    parser.add_argument(
        "--save", action="store_true", help="박스를 그린 사진을 runs/predict/ 에 저장"
    )
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.is_dir():
        print(f"\n[중단] 폴더가 없다: {image_dir}\n")
        return 1

    save_dir = None
    if args.save:
        # 폴더 이름에 conf 값을 넣어 0.25 와 0.4 결과가 섞이지 않게 한다. 예: runs/predict/val_conf0.25/
        # runs/ 는 .gitignore 대상이라 사진이 git 에 들어가지 않는다.
        save_dir = (
            PROJECT_ROOT / "runs" / "predict" / f"{image_dir.name}_conf{args.conf}"
        )
        # parents=True 는 중간 폴더까지 만들고, exist_ok=True 는 이미 있어도 에러 내지 않는다 (덮어쓴다).
        save_dir.mkdir(parents=True, exist_ok=True)

    # 가중치 파일을 읽어 모델을 메모리에 올린다. 노트북은 GPU 가 없어 CPU 로 돈다 (1장 약 0.15초).
    model = YOLO(args.weights)
    predicted = predict_folder(model, image_dir, args.conf, save_dir)
    planned = load_planned_counts(CSV_PATH)
    mismatches = compare(predicted, planned)

    total = len(predicted)
    correct = total - len(mismatches)
    # :.1% 는 0.857 을 85.7% 로 찍는 서식이다.
    print(
        f"\n{image_dir.name} {total}장 / conf {args.conf} / 틀린 사진 {len(mismatches)}장 / 개수 정답률 {correct / total:.1%}\n"
    )
    if mismatches:
        # b/n/w = bolt/nut/washer. 계획(images.csv)과 예측을 나란히 보여 어느 클래스가 어긋났는지 바로 보이게 한다.
        print("사진        계획 b/n/w    예측 b/n/w")
        print("-" * 40)
        for name, plan, pred in mismatches:
            # :<11 은 왼쪽 정렬 11칸, :<9 는 마지막 숫자 뒤를 9칸으로 채워 두 열을 맞춘다.
            print(
                f"{name:<11} {plan['bolt']}/{plan['nut']}/{plan['washer']:<9}  {pred['bolt']}/{pred['nut']}/{pred['washer']}"
            )
    if save_dir is not None:
        print(f"\n박스 그린 사진 -> {save_dir}")
    return 0


# 이 파일을 직접 실행했을 때만 main() 이 돈다. 다른 파일(나중의 FastAPI 서버)이 count_boxes 등을 import 해도 돌지 않는다.
# SystemExit 에 main() 의 반환값(0 또는 1)을 넘겨 운영체제에 종료 코드로 전달한다.
if __name__ == "__main__":
    raise SystemExit(main())
