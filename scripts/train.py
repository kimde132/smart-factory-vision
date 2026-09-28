# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  train.py — YOLO11n 을 우리 데이터(볼트·너트·와셔)로 파인튜닝한다. Colab 에서 돌린다.                 ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  result_data/ 의 train(EXP-03 기준 215장)으로 YOLO 모델을 파인튜닝(fine-tuning)하고 val(35장)로 채점한다.
# │  (9/6 첫 실행은 s01 28장뿐인 배관 점검 → 9/14 EXP-01 6세션 140장 → 9/19 EXP-02 그림자 세션 s07 40장을 더한 180장
# │   → 9/20 EXP-03 겹침·가장자리 세션 s08 35장을 더한 215장)
# │  COCO 로 미리 학습된 가중치에서 출발해, 볼트·너트·와셔 3종만 새로 가르친다.
# │  결과물은 runs/<name>/weights/best.pt — 부품을 찾을 줄 아는 모델 가중치. main.py 와 predict_count.py 가 읽는다.
# │
# │  ★ 이 파일은 노트북(Windows)에서 직접 실행하지 않는다. Colab 셀에 옮겨 붙인다.
# │    노트북에 NVIDIA GPU 가 없어서 학습은 Colab 에서 한다(D-002).
# │    그럼에도 git 에 두는 이유는 "어떤 설정으로 학습했는가" 가 남아야 하기 때문이다.
# │    설정이 기록되지 않으면 나중에 결과가 달라졌을 때 무엇을 바꿔서인지 알 수 없다.
# │
# │  촬영 → 라벨링 → verify_counts.py → split_dataset.py → result_data/ → data.yaml → [현재 파일]
# │    → runs/<name>/weights/best.pt → 결과 해석(experiment-log.md) → predict_count.py 채점 → main.py 운영
# │  앞: data.yaml 과 result_data/ 가 Google Drive 에 올라가 있어야 한다.
# │  뒤: best.pt 와 학습 곡선(results.png)·혼동 행렬(confusion_matrix.png) 그림이 나온다.
# │
# │  Colab 에서 이 코드보다 먼저 실행해야 하는 셀 3개
# │    1) !nvidia-smi                       GPU 가 붙었는지 확인. Tesla T4 가 보이면 정상. 안 보이면 런타임 → 런타임 유형 변경 → T4 GPU. CPU 로 돌면 4분이 몇 시간이 된다.
# │    2) from google.colab import drive    Drive 를 /content/drive 에 붙인다. 이걸 해야 아래 경로가 존재한다.
# │       drive.mount('/content/drive')
# │    3) !pip install ultralytics          Colab 에는 기본으로 없다. 세션을 새로 켤 때마다 다시 설치해야 한다.
# │       앞의 ! 는 "이 줄은 파이썬이 아니라 리눅스 명령어" 라는 Colab 전용 표시다.
# │
# │  실행 순서: 이 파일은 함수가 없다. 위에서 아래로 두 문장 — 모델 객체 만들기 → .train() 호출. 학습은 4~9분(T4).
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : from import
# │  ② 라이브러리가 정한 이름
# │       YOLO                                  ← ultralytics (클래스)
# │       .train()                              ← YOLO 객체의 메서드
# │       data epochs imgsz batch project name  ← .train() 의 키워드 인자 이름 (ultralytics 가 정함. 60개 넘는 것 중 6개만 씀)
# │       "yolo11n.pt"                          ← ultralytics 가 정한 사전학습 가중치 파일 이름
# │  ③ 내가 지은 이름
# │       model results  /  "exp03_s08overlap"(실험 이름)  /  Drive 경로 두 개
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  from ultralytics import YOLO   (pip: ultralytics)  → 학습·추론 클래스. main.py 와 predict_count.py 도 같은 클래스를 쓴다.
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  가중치(weights)      : 모델의 실체인 수백만 개의 숫자. 학습이란 이 숫자를 조금씩 고치는 것.
# │  사전학습 / 파인튜닝  : 숫자를 무작위로 놓고 시작하면 수만 장이 필요하다. 우리는 200장이 안 된다.
# │                         그래서 COCO(80종 12만 장)로 학습된 가중치에서 출발한다. 그 모델은 볼트를 모르지만 "윤곽", "금속 광택" 같은 일반 특징은 이미 안다.
# │                         그 위에 우리 3종만 새로 가르치는 것이 파인튜닝이다.
# │  epoch                : 학습 데이터 전체를 한 바퀴 훑는 것. train 140장(EXP-01) / batch 16 이면 한 바퀴가 9묶음이고,
# │                         가중치는 묶음당 한 번 고쳐지므로 1 epoch = 9번 수정. EXP-02 180장이면 12묶음, EXP-03 215장이면 14묶음.
# │                         9/6 s01 28장(2묶음)일 때는 10 epoch 동안 cls_loss 가 3.5에서 안 움직였는데, 140장(9묶음)에서는 2 epoch 만에 2.3으로 떨어졌다.
# │                         같은 epoch 수라도 데이터가 많으면 더 많이 배운다.
# │  loss                 : "틀린 정도". 줄어들면 배우는 중. box(위치) / cls(종류) / dfl(경계 정밀도) 셋이 나온다.
# │  best.pt / last.pt    : val 점수가 가장 좋았던 epoch 의 가중치 / 마지막 epoch 의 가중치. 우리는 best.pt 를 쓴다.
# │
# │  관련 문서: data.yaml (클래스와 데이터 경로), docs/decisions.md D-002(학습은 Colab)·D-003(분할 기준),
# │            docs/experiment-log.md (실험별 설정·결과·판단), scripts/split_dataset.py (train/val/test 가 어떻게 나뉘었나)
# └────────────────────────────────────────────────────────────────────────────────────────


# ▸ 단어 분해: from(①) ultralytics(② 패키지) import(①) YOLO(② 클래스)
# ▸ 뜻: ultralytics 패키지에서 YOLO 클래스 하나만 꺼내온다. 'from A import B' 는 A 안의 B 만 가져오는 문법.
# ▸ 왜: import ultralytics 로 통째로 불러온 뒤 매번 ultralytics.YOLO 라고 길게 쓰지 않기 위해서.
# ▸ 클래스는 "물건을 찍어내는 틀" 이라 이 줄만으로는 아직 실체가 없다.
from ultralytics import YOLO

# ▸ 단어 분해: model(③) = YOLO(② 클래스)("yolo11n.pt"(② 사전학습 가중치 파일 이름))
# ▸ 뜻: 클래스 이름 뒤에 괄호를 붙여 호출하면 실제 물건 하나가 만들어진다(인스턴스화). list() 나 dict() 를 부르는 것과 같은 문법.
#   model 은 이제 "학습할 줄 알고 탐지할 줄 아는 물건" 이 된다. C# 의 new YOLO("…") 와 같다.
# ▸ "yolo11n.pt" 해부:
#     yolo11 : YOLO 11번째 버전
#     n      : nano. n < s < m < l < x 중 가장 작고 빠른 크기.
#              큰 모델이 무조건 좋은 게 아니다. 140장으로 큰 모델을 돌리면 데이터를 통째로 외운다(과적합).
#              최종 목표가 웹캠 실시간 검사라 가벼운 쪽이 유리하기도 하다. 노트북 CPU 에서 0.15초/장.
#     .pt    : PyTorch 가중치 파일 확장자
# ▸ 이 파일은 Drive 에도 노트북에도 없다. 파일명만 적으면 ultralytics 가 인터넷에서 내려받는다(약 5MB).
# ▸ 다른 선택: "yolo11s.pt" 로 바꾸면 한 단계 큰 모델(약 19MB, 느리지만 정확도 여지). 구버전 ultralytics 라면 yolo11n.pt 가 없으므로 "yolov8n.pt".
#   main.py 처럼 YOLO("runs/…/best.pt") 를 주면 "우리 모델에서 이어서 학습" 이 된다.
model = YOLO("yolo11n.pt")

# ▸ 단어 분해: results(③) = model.train(② 메서드)( 키워드 인자 6개 … )
# ▸ 뜻: model 이라는 물건에게 .train() 이라는 동작을 시킨다(메서드 호출). 끝나면 학습 결과 객체를 results 에 담는다.
# ▸ 인자를 전부 '이름=값' 으로 넘겼다 = 키워드 인자(keyword argument). 순서대로 넘길 수도 있지만 그러지 않는 이유 셋:
#     1) .train() 은 인자가 60개가 넘는다. 순서를 외울 수 없다
#     2) 640 만 있으면 무슨 값인지 모르지만 imgsz=640 은 읽으면 안다
#     3) 필요한 것만 골라 넘기고 나머지 50여 개는 기본값이 쓰인다
# ▸ results 는 지금 쓰지 않지만, 나중에 지표를 코드로 꺼낼 때(results.results_dict 등) 쓴다. 안 받아도 학습은 된다.
results = model.train(
    # ▸ data(② 인자 이름)="…/data.yaml"(③ 내 경로)
    # ▸ 뜻: 학습 설명서 경로. 폴더가 아니라 yaml 파일 하나를 가리킨다. YOLO 는 이 파일을 읽고, 그 안에 적힌 path 를 따라가 사진을 찾는다.
    # ▸ Colab 안에서 보이는 절대경로여야 한다. 노트북 기준 경로(C:\…)가 아니다. /content/drive/MyDrive 가 "내 Drive" 의 루트.
    data="/content/drive/MyDrive/smart-factory-vision/data.yaml",
    # ▸ epochs=100 : 몇 바퀴 돌 것인가. 100 은 ultralytics 기본값이기도 하다.
    # ▸ 215장 / batch 16 이면 한 epoch 14묶음, 총 1400번 가중치를 고친다. (EXP-01 은 140장 · 9묶음 · 900번, EXP-02 는 180장 · 12묶음 · 1200번)
    # ▸ exp01 실제: 12 epoch 에 mAP50 0.99 도달, 이후 90 epoch 은 mAP50-95 만 0.84→0.91 로 천천히 올랐다.
    #   exp02 도 같은 모양이었다 (12 epoch 0.993, mAP50-95 0.85→0.92). epoch 을 바꿀 이유가 없어 그대로 둔다.
    # ▸ 마지막 10 epoch 은 ultralytics 가 mosaic 증강을 자동으로 꺼서 train loss 가 뚝 떨어진다. 정상이다.
    # ▸ 다른 선택: 줄이면 빨리 끝나지만 mAP50-95 가 덜 오른다. 늘리면 시간만 늘고 과적합 위험(val loss 가 다시 오르기 시작하면 그 지점).
    epochs=100,
    # ▸ imgsz=640 : 학습할 때 사진을 정사각형 몇 픽셀로 줄일지. 원본(아이폰 4284, 웹캠 크롭 1080)이 640×640 으로 줄어든다.
    # ▸ ★ 이 프로젝트에서 가장 중요한 숫자다.
    #     D-007 의 "와셔가 64픽셀" 이라는 계산이 이 640 기준이고, 너무 작아지면 너트의 육각 모서리와 와셔의 원이 뭉개져 구분되지 않는다(D-004 최대 리스크).
    #     웹캠 프레임 결정의 선택지 B 가 imgsz 960 이라, 그 판단의 비교 기준으로 640 을 고정했다.
    # ▸ main.py 의 IMGSZ = 640 과 같아야 한다. 학습과 추론의 크기가 다르면 부품이 차지하는 픽셀 수가 달라져 성능이 바뀐다.
    # ▸ 다른 선택: 960 이면 부품이 1.5배 크게 보이지만 메모리 2.25배, 속도 절반. 320 이면 와셔가 32px 라 D-007 뒤집는 조건(40px 미만).
    imgsz=640,
    # ▸ batch=16 : 한 번에 GPU 에 올리는 사진 수. 한 장씩 넣으면 느리고, 다 넣으면 메모리가 터진다.
    # ▸ T4 GPU 16GB + imgsz 640 기준으로 16 이 무난하다.
    # ▸ 다른 선택: CUDA out of memory 가 나면 8 로 줄인다. -1 로 두면 자동 조절도 된다.
    batch=16,
    # ▸ project="…/runs" : 결과를 저장할 상위 폴더.
    # ▸ ★ 이 인자를 빼면 안 된다. 기본값은 /content/runs 인데 /content 는 Colab 세션이 끊기면 통째로 사라진다. 학습 결과가 날아간다. 그래서 Drive 안 경로를 준다.
    project="/content/drive/MyDrive/smart-factory-vision/runs",
    # ▸ name="exp03_s08overlap" : project 안에 만들어질 이번 실험 폴더 이름. 결과는 runs/exp03_s08overlap/ 에.
    # ▸ 실험이 쌓이면 이 이름으로 구분하므로, 무엇을 한 실험인지 알 수 있게 짓는다.
    #   exp03 = 세 번째 정식 실험, s08overlap = train 에 겹침·가장자리 세션 s08 을 더했다는 뜻.
    #   이전: "s01_pipe_check"(9/6 배관 점검) → "exp01_6sessions"(9/14, 140장) → "exp02_s07shadow"(9/19, 그림자 세션 s07 추가, 180장).
    # ▸ 같은 이름으로 다시 돌리면 exp03_s08overlap2 처럼 뒤에 숫자가 붙는다. 실험마다 이름을 바꾼다.
    # ▸ main.py 의 MODEL_NAME 이 이 폴더 이름을 그대로 DB 에 남긴다 — 여기서 지은 이름이 엑셀의 "모델" 열까지 간다.
    name="exp03_s08overlap",
)
