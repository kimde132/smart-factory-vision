# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  predict_count.py — best.pt 로 폴더의 사진마다 부품 개수를 세고 images.csv 와 대조한다 (사진 단위 개수 정답률)   ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  학습이 끝난 모델(best.pt)로 폴더의 사진을 한 장씩 추론해 **클래스별 부품 개수**를 세고,
# │  metadata/images.csv 에 적힌 실제 개수와 대조해 **틀린 사진 목록과 사진 단위 개수 정답률**을 출력한다.
# │  --save 를 붙이면 박스와 클래스 이름을 그려 넣은 사진을 runs/predict/ 에 저장한다.
# │
# │  ★ 이 프로젝트의 지표는 mAP 가 아니라 이 스크립트가 내는 "사진 단위 개수 정답률" 이다.
# │    mAP 는 박스 하나하나를 채점하지만, 검사 장비의 OK/NG 는 사진 한 장의 세 개수가 전부 맞아야 OK 다.
# │    혼동 행렬에는 안 보이는 오류(한 물체에 박스 두 개, 가장자리 헛것)가 여기서 드러난다 (experiment-log.md EXP-01).
# │
# │  train.py(Colab) → best.pt 를 runs/<실험명>/weights/ 에 받아옴 → [현재 파일] → 틀린 사진을 눈으로 확인(#21 실패 분석)
# │  앞: runs/exp01_6sessions/weights/best.pt(기본값) 와 metadata/images.csv 가 있어야 한다. 대상 폴더의 사진 이름(s04_005)이 images.csv 의 image_name 과 같아야 한다.
# │  뒤: 여기의 "추론 → 개수 세기 → 기대 개수와 대조" 세 단계가 그대로 main.py 의 OK/NG 판정 로직이 됐다. main.py 는 count_boxes 를 import 해서 쓴다.
# │
# │  실행 (프로젝트 최상위에서, 반드시 ai-server 가상환경의 파이썬으로)
# │      ai-server\.venv\Scripts\python.exe scripts\predict_count.py dataset\result_data\images\val --save
# │      ai-server\.venv\Scripts\python.exe scripts\predict_count.py dataset\result_data\images\val --conf 0.4 --weights runs\exp03_s08overlap\weights\best.pt
# │
# │  실행 순서: main() → 인자 파싱 → YOLO(가중치) → predict_folder() 가 장마다 count_boxes() → load_planned_counts() → compare() → 출력
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : import from def return for in if is not None raise
# │  ② 라이브러리가 정한 이름
# │       argparse.ArgumentParser .add_argument .parse_args   ← argparse (Python 기본)
# │       Path .iterdir .suffix .stem .name .is_dir .mkdir   ← pathlib (Python 기본)
# │       YOLO .predict                                       ← ultralytics
# │       result.boxes.cls .names .save                       ← ultralytics Results 객체의 속성·메서드
# │       .tolist()                                           ← PyTorch 텐서의 메서드
# │       sorted len print                                    ← Python 내장 함수
# │  ③ 내가 지은 이름
# │       상수: PROJECT_ROOT DEFAULT_WEIGHTS CSV_PATH CLASS_NAMES IMAGE_SUFFIXES
# │       함수: count_boxes predict_folder compare main
# │       변수: counts cls_id predicted image_paths image_path result mismatches name pred plan parser args image_dir save_dir model planned total correct
# │       내 다른 파일: load_planned_counts (verify_counts.py)
# │       명령줄 인자 이름: image_dir --weights --conf --save
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  import argparse                          (Python 기본) → 명령줄 인자 받기
# │  from pathlib import Path                 (Python 기본) → 경로 객체
# │  from ultralytics import YOLO             (pip)         → 모델 읽기·추론
# │  from verify_counts import load_planned_counts (내 파일, 같은 폴더) → images.csv → {사진: {부품: 개수}}
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  추론(inference)   : 학습이 끝난 모델에 새 사진을 넣어 답을 받는 것. 학습과 달리 가중치를 고치지 않는다.
# │  추론 결과의 모양  : model.predict(사진) 은 리스트를 돌려주고 [0] 이 그 사진의 결과(Results 객체)다.
# │      result.boxes.cls  → shape (박스 수,)     각 박스의 클래스 번호. 예: tensor([2., 0., 1.])   ← 이 파일이 쓰는 것
# │      result.boxes.conf → shape (박스 수,)     각 박스의 확신도 0~1
# │      result.boxes.xyxy → shape (박스 수, 4)   각 행이 [x1, y1, x2, y2] 픽셀 좌표
# │      result.names      → {0: 'bolt', 1: 'nut', 2: 'washer'}  (학습 때 data.yaml 에서 가져온 것)
# │  conf 임계값        : 모델은 확신도가 낮은 박스도 잔뜩 내놓는다. conf 이상인 것만 남긴다.
# │      올리면 헛것이 줄고 진짜를 놓치기 시작한다. 개수 정답률을 직접 바꾸는 손잡이라 인자로 받는다.
# │      EXP-01 val 기준: 0.25 → 80.0%, 0.4 → 85.7%, 0.6 → 85.7%(진짜 와셔를 놓치기 시작). 운영값 0.4.
# │  NMS (Non-Max Suppression) : 한 물체에 겹쳐 나온 박스들을 하나로 정리하는 절차. 모델 안에서 predict 때 자동으로 돈다.
# │      같은 클래스끼리만 합치고, 겹침(IoU)이 0.7 미만이면 같은 클래스여도 안 합친다.
# │      그래서 한 와셔에 nut 0.52 + washer 0.39 두 박스가 남는 일이 생긴다(s04_008).
# │      이 스크립트는 iou 인자를 안 받아 기본 0.7 이다. main.py 는 iou=0.5 (EXP-03 에서 확정). 9/20 채점은 임시 스크립트로 했다(상태판).
# │
# │  자료 모양
# │    counts (dict)     : {'bolt': 1, 'nut': 3, 'washer': 5}                       ← count_boxes 출력, images.csv 쪽과 같은 모양
# │    predicted (dict)  : {'s04_001': {'bolt': 0, 'nut': 2, 'washer': 4}, …}       ← predict_folder 출력
# │    mismatches (list) : [('s04_004', 계획 dict, 예측 dict), …]                    ← compare 출력
# │
# │  관련 문서: docs/experiment-log.md EXP-01 3절 (이 스크립트가 낸 결과와 오류 세 종류),
# │            docs/decisions.md D-004 (너트↔와셔 혼동 리스크), scripts/verify_counts.py (CSV 읽는 함수의 원본)
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ argparse(② 모듈): 명령줄 인자(폴더, --weights, --conf, --save)를 받아 파싱해 주는 표준 라이브러리. "python 파일 인자들" 의 "인자들" 을 읽는다.
import argparse  # 명령줄 인자(폴더, --weights, --conf, --save)를 받아 파싱해주는 표준 라이브러리

# ▸ Path(② 클래스): 경로를 객체로. "/" 로 이어 붙이고 .stem, .is_dir() 같은 메서드를 쓴다.
from pathlib import Path  # 경로를 문자열이 아니라 객체로 다룬다. "/" 로 이어붙이고 .stem, .is_dir() 같은 메서드를 쓴다

# ▸ YOLO(② 클래스): .pt 파일을 주면 모델을 메모리에 올리고, .predict() 로 추론한다. train.py·main.py 와 같은 클래스.
from ultralytics import YOLO

# ▸ 단어 분해: from verify_counts(③ 같은 scripts/ 폴더의 파일) import load_planned_counts(③ 그 안의 함수)
# ▸ 뜻: images.csv 를 {사진이름: {'bolt': n, 'nut': n, 'washer': n}} 로 읽어 주는 함수를 빌린다 (split_dataset.py 와 같은 방식).
# ▸ ★ 아래 count_boxes 가 내는 예측 결과도 정확히 이 모양으로 맞춘다. 모양이 같아야 == 한 번으로 비교된다.
# ▸ 왜 바로 import 되나: 이 파일을 실행하면 Python 이 "이 파일이 있는 폴더(scripts/)" 를 검색 경로에 넣기 때문. main.py 는 sys.path 에 scripts/ 를 직접 넣어서 같은 효과를 낸다.
from verify_counts import load_planned_counts

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  상수
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: PROJECT_ROOT(③) = Path(__file__).resolve().parent(scripts/).parent(최상위)
# ▸ 어디서 실행하든 경로가 흔들리지 않는다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ▸ DEFAULT_WEIGHTS(③): 기본 가중치. EXP-01 의 best.pt (epoch 80). 다른 실험을 채점할 때는 --weights 로 바꾼다.
# ▸ 다른 선택: 이 기본값을 EXP-03 으로 바꾸면 명령이 짧아지지만, 상태판은 "기본값은 아직 EXP-01" 로 적혀 있다. 바꾸면 상태판도 같이.
DEFAULT_WEIGHTS = PROJECT_ROOT / "runs" / "exp01_6sessions" / "weights" / "best.pt"
# ▸ CSV_PATH(③): 사진별 실제 개수(채점표). 9/3 이후 실제 값과 일치한다 (verify_counts.py 로 검증됨).
CSV_PATH = PROJECT_ROOT / "metadata" / "images.csv"
# ▸ 단어 분해: CLASS_NAMES(③) = ("bolt", "nut", "washer")   (튜플: 바뀌지 않는 목록)
# ▸ 순서는 data.yaml / labeling-guide.md 1-1 과 같다(0=bolt, 1=nut, 2=washer). 개수 딕셔너리의 키를 만들 때 쓴다.
# ▸ verify_counts.py 는 같은 것을 {0: "bolt", …} 딕셔너리로 갖고 있다. 여기선 이름만 필요해서 튜플.
CLASS_NAMES = ("bolt", "nut", "washer")
# ▸ 단어 분해: IMAGE_SUFFIXES(③) = {".jpg", ".jpeg"}   (집합: in 검사가 빠르다)
# ▸ 대상 폴더에서 사진만 고르기 위한 확장자 집합. 소문자로 비교한다(아래 .lower()).
IMAGE_SUFFIXES = {".jpg", ".jpeg"}


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  함수 넷 — 개수 세기 / 폴더 추론 / 대조 / 진입점
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: def count_boxes(③)(result(③ 인자)):   (타입 힌트 없음. Python 은 선택)
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
    # ▸ 단어 분해: counts(③) = { name(③): 0 for(①) name in(①) CLASS_NAMES }   (딕셔너리 컴프리헨션)
    # ▸ 뜻: {'bolt': 0, 'nut': 0, 'washer': 0}. 세 클래스를 먼저 0 으로 깔아 둔다.
    # ▸ 왜: 안 그러면 탐지 0개인 클래스가 딕셔너리에 없어서 CSV 쪽과 모양이 달라지고 비교가 어긋난다. verify_counts.count_classes 와 같은 이유.
    counts = {name: 0 for name in CLASS_NAMES}
    # ▸ 단어 분해: for cls_id(③) in result.boxes(② 박스 묶음).cls(② 클래스 번호 텐서, shape (박스수,)).tolist(② 텐서 → 파이썬 리스트)():
    # ▸ 뜻: 박스 하나씩 클래스 번호를 꺼낸다. 값이 2.0 처럼 실수(float)로 들어 있다.
    # ▸ 왜 tolist: PyTorch 텐서를 그대로 돌아도 되지만, 원소가 텐서라 int() 변환이 번거롭다. 리스트로 바꾸면 그냥 숫자.
    for cls_id in result.boxes.cls.tolist():
        # ▸ 단어 분해: counts[ result.names(② {0:'bolt',…})[ int(cls_id)(2.0 → 2) ] ] +=(① 더해서 다시 넣기) 1
        # ▸ 뜻: 번호 → 이름을 찾고, 그 이름의 칸을 1 올린다. 같은 클래스가 여러 개 탐지되므로 누적한다.
        # ▸ 왜 int(): names 의 키가 정수 0/1/2 라 2.0 으로는 못 찾는다(KeyError).
        counts[result.names[int(cls_id)]] += 1
    return counts


# ▸ 단어 분해: def predict_folder(③)(model, image_dir, conf, save_dir=None(① 기본값 None = 안 주면 저장 안 함)):
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
    # ▸ 단어 분해: image_paths(③) = sorted(② 정렬)( p(③) for p in image_dir.iterdir(② 폴더 안 항목 하나씩)() if p.suffix(② 확장자).lower(② 소문자)() in IMAGE_SUFFIXES )
    # ▸ 뜻: 폴더 안 항목 중 확장자가 .jpg/.jpeg 인 것만 골라 이름순으로. 괄호 안은 제너레이터 식(리스트 컴프리헨션의 [] 없는 판) — sorted 가 바로 소비한다.
    # ▸ 왜 sorted: iterdir 순서는 OS 마음이라 출력 순서를 s04_001 부터로 고정하려는 것.
    # ▸ 괄호 안 줄바꿈은 포매터가 넣은 것.
    image_paths = sorted(
        p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    )
    for image_path in image_paths:
        # ▸ 단어 분해: result(③) = model.predict(②)( image_path(경로), imgsz=640, conf=conf, verbose=False )[0]
        # ▸ imgsz=640 : 학습(train.py)과 같은 크기. 다르게 주면 부품이 차지하는 픽셀이 달라져 성능이 바뀐다.
        # ▸ conf      : 이 값 미만 박스는 모델 안에서 버려지고 나온다. 인자로 받은 값 그대로.
        # ▸ verbose=False : 장마다 찍히는 로그를 끈다. 35줄이 쏟아지면 결과가 안 보인다.
        # ▸ [0] : predict 는 리스트를 돌려주고(여러 장을 한꺼번에 넣을 수 있어서), 한 장이라 첫 원소만 쓴다.
        # ▸ 다른 선택: iou=0.5 를 추가하면 main.py 와 같은 운영값이 된다(상태판 "--iou 인자 추가" 가 이것). 지금은 기본 0.7.
        result = model.predict(image_path, imgsz=640, conf=conf, verbose=False)[0]
        # ▸ image_path.stem(② 확장자를 뗀 파일명): s04_005.jpg → s04_005. images.csv 의 키와 같다.
        predicted[image_path.stem] = count_boxes(result)
        # ▸ if save_dir is not None: 저장 폴더를 받았을 때만.
        if save_dir is not None:
            # ▸ result.save(② 박스 그린 사진 저장)(filename=str(save_dir / image_path.name(② 확장자 포함 파일명)))
            # ▸ 박스·클래스 이름·확신도를 그려 넣은 사진을 같은 이름으로 저장한다. 틀린 사진을 눈으로 볼 때 쓴다(#21 실패 분석의 재료).
            result.save(filename=str(save_dir / image_path.name))
    return predicted


# ▸ 단어 분해: def compare(③)(predicted(③), planned(③)):
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
    # ▸ 단어 분해: for name(③ 키), pred(③ 값) in predicted.items(② (키, 값) 쌍 하나씩)():
    for name, pred in predicted.items():
        # ▸ if name not in planned: images.csv 에 없는 사진이면 raise(① 예외 던지기) KeyError(② 키 없음 예외)(f"…")
        # ▸ 왜 멈추나: 조용히 건너뛰면 아래 정답률 계산의 분모(total)가 틀어진다. 원인(이름 오타·CSV 누락)을 사람이 봐야 한다.
        if name not in planned:
            raise KeyError(f"images.csv 에 없는 사진이다: {name}")
        # ▸ if pred !=(① 다르면) planned[name]:
        # ▸ 두 딕셔너리가 같은 모양({'bolt':..,'nut':..,'washer':..})이라 != 한 번에 세 클래스가 전부 비교된다. 하나라도 다르면 그 사진은 NG.
        # ▸ main.py 의  if counts == expected  가 정확히 이 비교다.
        if pred != planned[name]:
            # ▸ mismatches.append(② 리스트 끝에 추가)( (name, planned[name], pred)(튜플 하나) )
            mismatches.append((name, planned[name], pred))
    return mismatches


def main():
    """명령줄에서 실행됐을 때의 진입점.

    입력:
        명령줄 인자. image_dir (필수), --weights, --conf, --save (선택)

    출력:
        종료 코드. 0이면 정상, 1이면 오류. 화면에 정답률과 틀린 사진 표를 찍는다.
    """
    # ▸ 단어 분해: parser(③) = argparse.ArgumentParser(② 인자 해석기 클래스)(description="…"(--help 에 보이는 설명))
    parser = argparse.ArgumentParser(
        description="best.pt 로 폴더의 사진마다 부품 개수를 세고 images.csv 와 대조한다."
    )
    # ▸ parser.add_argument(② 인자 하나 등록)("image_dir"(③ 앞에 -- 가 없으면 "위치 인자" = 필수, 순서로 받음), help="…")
    parser.add_argument(
        "image_dir", help="사진 폴더. 예: dataset/result_data/images/val"
    )
    # ▸ "--weights"(③ -- 로 시작 = 선택 인자, 이름으로 받음) default=str(DEFAULT_WEIGHTS)(안 주면 이 값)
    # ▸ 왜 str(): argparse 의 default 는 문자열이 자연스럽고, YOLO() 도 문자열 경로를 받는다.
    parser.add_argument(
        "--weights", default=str(DEFAULT_WEIGHTS), help="모델 가중치 .pt 경로"
    )
    # ▸ type=float(② 글자를 실수로 바꿔라) default=0.25
    # ▸ 왜 type: 없으면 "0.4" 문자열이 그대로 넘어가 predict 에서 에러가 난다. WPF 의 int.TryParse 가 하던 일을 argparse 가 한다.
    parser.add_argument(
        "--conf", type=float, default=0.25, help="이 확신도 이상인 박스만 센다."
    )
    # ▸ action="store_true"(② 플래그): 붙이면 True, 안 붙이면 False. 값 없이 --save 만 쓴다.
    parser.add_argument(
        "--save", action="store_true", help="박스를 그린 사진을 runs/predict/ 에 저장"
    )
    # ▸ args(③) = parser.parse_args(② 실제 명령줄을 읽어 해석)()  → args.image_dir, args.weights, args.conf, args.save 로 꺼낸다.
    args = parser.parse_args()

    # ▸ image_dir(③) = Path(args.image_dir)  — 글자를 경로 객체로. 그래야 .is_dir(), .name, .iterdir() 를 쓴다.
    image_dir = Path(args.image_dir)
    # ▸ if not image_dir.is_dir(② 폴더인가)(): 없거나 파일이면 안내하고 return 1(종료 코드 1 = 실패).
    if not image_dir.is_dir():
        print(f"\n[중단] 폴더가 없다: {image_dir}\n")
        return 1

    save_dir = None
    # ▸ if args.save: --save 를 붙였을 때만 저장 폴더를 만든다.
    if args.save:
        # ▸ 단어 분해: save_dir = PROJECT_ROOT / "runs" / "predict" / f"{image_dir.name}_conf{args.conf}"
        # ▸ 폴더 이름에 conf 값을 넣어 0.25 와 0.4 결과가 섞이지 않게 한다. 예: runs/predict/val_conf0.25/
        # ▸ runs/ 는 .gitignore 대상이라 사진이 git 에 들어가지 않는다.
        save_dir = (
            PROJECT_ROOT / "runs" / "predict" / f"{image_dir.name}_conf{args.conf}"
        )
        # ▸ save_dir.mkdir(② 폴더 만들기)(parents=True(중간 폴더까지), exist_ok=True(이미 있어도 에러 내지 않는다. 안의 사진은 덮어쓴다))
        save_dir.mkdir(parents=True, exist_ok=True)

    # ▸ model(③) = YOLO(args.weights)  — 가중치 파일을 읽어 모델을 메모리에 올린다. 노트북은 GPU 가 없어 CPU 로 돈다 (1장 약 0.15초).
    model = YOLO(args.weights)
    # ▸ 세 단계. 위 함수 셋을 순서대로. 이 세 줄이 main.py 의 /inspect 본문과 같은 구조다(추론 → 세기 → 대조).
    predicted = predict_folder(model, image_dir, args.conf, save_dir)
    planned = load_planned_counts(CSV_PATH)
    mismatches = compare(predicted, planned)

    # ▸ total(③) = len(predicted)(사진 수) / correct(③) = total - len(mismatches)(틀린 수)
    total = len(predicted)
    correct = total - len(mismatches)
    # ▸ f-string 의 {correct / total:.1%} : 0.857 을 85.7% 로 찍는 서식(:.1% = 소수 1자리 퍼센트). total 이 0 이면 ZeroDivisionError.
    print(
        f"\n{image_dir.name} {total}장 / conf {args.conf} / 틀린 사진 {len(mismatches)}장 / 개수 정답률 {correct / total:.1%}\n"
    )
    # ▸ if mismatches: 빈 리스트는 False. 틀린 게 있을 때만 표를 찍는다.
    if mismatches:
        # ▸ b/n/w = bolt/nut/washer. 계획(images.csv)과 예측을 나란히 보여 어느 클래스가 어긋났는지 바로 보이게 한다.
        print("사진        계획 b/n/w    예측 b/n/w")
        print("-" * 40)
        # ▸ for name, plan, pred in mismatches: 튜플 (이름, 계획, 예측) 을 변수 셋에 나눠 담기(언패킹).
        for name, plan, pred in mismatches:
            # ▸ f-string 서식: {name:<11} = 왼쪽 정렬 11칸, {…:<9} = 마지막 숫자 뒤를 9칸으로 채워 두 열을 맞춘다.
            print(
                f"{name:<11} {plan['bolt']}/{plan['nut']}/{plan['washer']:<9}  {pred['bolt']}/{pred['nut']}/{pred['washer']}"
            )
    if save_dir is not None:
        print(f"\n박스 그린 사진 -> {save_dir}")
    return 0


# ▸ 이 파일을 직접 실행했을 때만 main() 이 돈다. main.py 가 count_boxes 를 import 해도 돌지 않는다.
# ▸ raise SystemExit(main()) : main() 의 반환값(0 또는 1)을 운영체제에 종료 코드로 전달한다. sys.exit(main()) 과 같다.
if __name__ == "__main__":
    raise SystemExit(main())
