# #20 `scripts/predict_count.py` 작성 가이드 (2026-09-18)

> **임시 문서.** 스크립트가 완성되면 지운다. 대화가 끊겨도 코드를 이어서 칠 수 있게 남긴 것이다.
> 방식: Claude가 "왜 → 코드 → 이유"를 주고 사용자가 타이핑, 주석은 완성 뒤 Claude가 단다.

## 무엇을 만드는가

폴더의 사진을 `best.pt`로 한 장씩 추론해 **클래스별 개수**를 내고, `images.csv`의 실제 개수와 대조해
**틀린 사진 목록과 개수 정답률**을 찍는다. `--save`를 붙이면 박스를 그린 사진을 `runs/predict/`에 저장한다.
이 "개수 대조"가 그대로 FastAPI의 OK/NG 판정 로직이 된다.

## 알아야 할 개념 셋

- **추론 결과의 모양.** `model.predict(사진)`은 리스트를 돌려주고 `[0]`이 그 사진의 결과다.
  `result.boxes.cls` = 박스마다 클래스 번호(0·1·2), `result.boxes.conf` = 확신도, `result.boxes.xyxy` = 좌표(박스 수 × 4).
  `result.names` = `{0:'bolt', 1:'nut', 2:'washer'}`. 개수를 세려면 `cls`만 있으면 된다.
- **conf 임계값.** 확신도가 `conf`(기본 0.25) 이상인 박스만 남긴다. 올리면 헛것이 줄고 놓침이 늘어난다. 개수 정답률을 직접 바꾸는 손잡이라 인자로 받는다.
- **`imgsz`는 학습과 같게 640.** 다르면 부품 크기가 달라져 성능이 바뀐다.

## 코드

### 1. import와 상수

```python
import argparse
from pathlib import Path

from ultralytics import YOLO

from verify_counts import load_planned_counts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS = PROJECT_ROOT / "runs" / "exp01_6sessions" / "weights" / "best.pt"
CSV_PATH = PROJECT_ROOT / "metadata" / "images.csv"
CLASS_NAMES = ("bolt", "nut", "washer")
IMAGE_SUFFIXES = {".jpg", ".jpeg"}
```

- (9/18 저녁 Smart App Control을 껐으므로 torchvision 우회는 필요 없다. 위 코드 그대로.)
- `load_planned_counts`는 `verify_counts.py`의 함수. `images.csv`를 `{사진이름: {'bolt': n, 'nut': n, 'washer': n}}`로 읽어준다.
  예측 결과도 **같은 모양**으로 만들면 `==`로 바로 비교된다. 이것이 설계의 요점이다.

### 2. `count_boxes(result)` — 한 장의 결과에서 개수 세기

```python
def count_boxes(result):
    counts = {name: 0 for name in CLASS_NAMES}
    for cls_id in result.boxes.cls.tolist():
        counts[result.names[int(cls_id)]] += 1
    return counts
```

- 세 클래스를 먼저 0으로 깔아둔다. 안 그러면 탐지 0개인 클래스가 딕셔너리에 없어서 비교가 어긋난다.
- `boxes.cls`는 텐서라 `.tolist()`로 파이썬 리스트로. 값이 `2.0`처럼 실수라 `int()`로 바꿔 `names`에서 이름을 찾는다.

### 3. `predict_folder(model, image_dir, conf, save_dir=None)` — 폴더 전체

```python
def predict_folder(model, image_dir, conf, save_dir=None):
    predicted = {}
    image_paths = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    for image_path in image_paths:
        result = model.predict(image_path, imgsz=640, conf=conf, verbose=False)[0]
        predicted[image_path.stem] = count_boxes(result)
        if save_dir is not None:
            result.save(filename=str(save_dir / image_path.name))
    return predicted
```

- `verbose=False`: 장마다 찍히는 로그를 끈다. 35줄이 쏟아지면 결과가 안 보인다.
- `image_path.stem` = 확장자 뗀 이름 `s04_005`. `images.csv`의 키와 같다.
- `result.save(filename=...)`: 박스와 라벨을 그린 사진을 저장. `save_dir`가 `None`이면 건너뛴다.

### 4. `compare(predicted, planned)` — 대조

```python
def compare(predicted, planned):
    mismatches = []
    for name, pred in predicted.items():
        if name not in planned:
            raise KeyError(f"images.csv 에 없는 사진이다: {name}")
        if pred != planned[name]:
            mismatches.append((name, planned[name], pred))
    return mismatches
```

- 두 딕셔너리가 같은 모양이라 `!=` 한 번에 세 클래스가 비교된다.
- CSV에 없는 사진은 멈춘다. 조용히 건너뛰면 정답률 분모가 틀어진다.

### 5. `main()`

```python
def main():
    parser = argparse.ArgumentParser(
        description="best.pt 로 폴더의 사진마다 부품 개수를 세고 images.csv 와 대조한다."
    )
    parser.add_argument("image_dir", help="사진 폴더. 예: dataset/result_data/images/val")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS), help="모델 가중치 .pt 경로")
    parser.add_argument("--conf", type=float, default=0.25, help="이 확신도 이상인 박스만 센다")
    parser.add_argument("--save", action="store_true", help="박스를 그린 사진을 runs/predict/ 에 저장")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.is_dir():
        print(f"\n[중단] 폴더가 없다: {image_dir}\n")
        return 1

    save_dir = None
    if args.save:
        save_dir = PROJECT_ROOT / "runs" / "predict" / f"{image_dir.name}_conf{args.conf}"
        save_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    predicted = predict_folder(model, image_dir, args.conf, save_dir)
    planned = load_planned_counts(CSV_PATH)
    mismatches = compare(predicted, planned)

    total = len(predicted)
    correct = total - len(mismatches)
    print(f"\n{image_dir.name} {total}장 / conf {args.conf} / 틀린 사진 {len(mismatches)}장 / 개수 정답률 {correct / total:.1%}\n")
    if mismatches:
        print("사진        계획 b/n/w    예측 b/n/w")
        print("-" * 40)
        for name, plan, pred in mismatches:
            print(f"{name:<11} {plan['bolt']}/{plan['nut']}/{plan['washer']:<9}  {pred['bolt']}/{pred['nut']}/{pred['washer']}")
    if save_dir is not None:
        print(f"\n박스 그린 사진 -> {save_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- 저장 폴더 이름에 `conf` 값을 넣어 0.25와 0.4 결과가 안 섞이게 한다. `runs/`는 git 제외.
- `:.1%`는 0.914를 `91.4%`로 찍는 서식.

## 실행

프로젝트 최상위에서, **반드시 ai-server 가상환경의 파이썬**으로:

```powershell
ai-server\.venv\Scripts\python.exe scripts\predict_count.py dataset\result_data\images\val --save
```

35장, CPU로 10초 안쪽. 출력(틀린 사진 목록과 정답률)을 Claude에게 붙인다.
그 다음 `--conf 0.4`, `--conf 0.6`으로 두 번 더 돌려 비교한다. 이것이 EXP-01 3절 "정확한 장수"다.
