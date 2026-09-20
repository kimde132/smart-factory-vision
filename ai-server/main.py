# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   FastAPI 서버. WPF가 보낸 사진 한 장을 받아 YOLO로 볼트·너트·와셔 개수를 세고,
#   함께 받은 기대 개수와 비교해 OK/NG 판정을 JSON으로 돌려준다.
#   창구(엔드포인트)는 둘이다.
#     GET  /health   → 서버가 살아 있는지, 모델이 올라왔는지 확인용
#     POST /inspect  → 사진 + 기대 개수 → 판정
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   WPF(C#) ──사진+기대개수──▶ [현재 파일] ──▶ YOLO(best.pt) ──▶ count_boxes ──▶ 판정 ──JSON──▶ WPF
#   앞: runs/exp03_s08overlap/weights/best.pt 가 있어야 한다 (EXP-03 최종 모델, git 제외).
#       scripts/predict_count.py(count_boxes) 와 scripts/crop_session.py(center_square_box) 를 빌려 쓴다.
#   뒤: 다음 단계에서 판정 결과를 MSSQL 에 저장하는 코드가 이 파일의 inspect() 뒤에 붙는다.
#
#   띄우는 법 (ai-server 폴더에서):
#       .venv\Scripts\uvicorn main:app --reload
#     그 뒤 브라우저에서 http://localhost:8000/docs 를 열면 FastAPI 가 만든 시험 화면이 나온다.
#     사진을 올리고 숫자 세 개를 넣고 Execute 를 누르면 응답이 보인다. WPF 없이도 시험할 수 있다.
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   HTTP 요청/응답 : WPF가 보내는 것이 요청, 서버가 돌려주는 것이 응답. 응답은 JSON(딕셔너리와 같은 모양의 글자)이다.
#   엔드포인트    : 요청을 받는 주소. "/inspect" 처럼 쓴다. 메서드(GET/POST)와 짝을 이룬다.
#   데코레이터    : 함수 위에 @app.post("/inspect") 를 붙이면 "이 주소로 POST 요청이 오면 이 함수를 실행해라" 가 된다.
#   multipart/form-data : 사진 같은 파일과 글자(숫자)를 한 요청에 같이 담아 보내는 형식.
#                  FastAPI 에서는 File() 과 Form() 으로 받는다. python-multipart 패키지가 필요하다.
#   async def     : 비동기 함수. 요청을 기다리는 동안 다른 요청도 받을 수 있게 하는 문법.
#                  이 프로젝트에서는 "FastAPI 가 이렇게 쓰라고 한다" 정도로 알면 된다. await 는 그 안에서 기다리는 표시.
#   운영값        : conf 0.4 · iou 0.5 (experiment-log.md EXP-03 에서 확정). 이 값 밑의 박스는 버리고, 이만큼 겹친 같은 클래스 박스는 하나로 합친다.
# ─────────────────────────────────────────────────────────────────────────────

import sys  # 파이썬이 import 할 때 뒤지는 폴더 목록(sys.path)을 고치려고 쓴다
from pathlib import (
    Path,
)  # 경로를 문자열이 아니라 객체로 다룬다. "/" 로 이어붙일 수 있다

import cv2  # OpenCV. 업로드된 사진 바이트를 이미지 배열로 바꾸고(imdecode) 가운데를 자르는 데 쓴다
import numpy as np  # 사진 바이트를 OpenCV 가 읽을 수 있는 숫자 배열로 감싸는 데 쓴다
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)  # 서버 본체, 파일 입력, 글자 입력, 오류 응답, 업로드 파일 타입
from ultralytics import YOLO  # 학습된 best.pt 를 읽어 추론하는 클래스

# __file__ 은 이 파일의 경로. .parent 를 두 번 올라가면 프로젝트 최상위(smart-factory-vision/)다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# scripts/ 폴더를 import 검색 경로 맨 앞에 넣는다. 그래야 아래 두 줄의 from ... import 가 된다.
# predict_count.py 안에서 "from verify_counts import ..." 를 하므로 scripts/ 자체가 경로에 있어야 한다.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from predict_count import (
    count_boxes,
)  # 추론 결과 → {'bolt': n, 'nut': n, 'washer': n}. predict_count.py 65행
from crop_session import (
    center_square_box,
)  # (가로, 세로) → 가운데 정사각형 좌표. 웹캠 16:9 원본을 학습 때와 같은 1:1 로 맞춘다

# EXP-03 최종 모델. 기본값이 EXP-01 인 predict_count.py 와 달리 여기는 운영용이라 최종 모델을 고정한다.
WEIGHTS = PROJECT_ROOT / "runs" / "exp03_s08overlap" / "weights" / "best.pt"
# 운영값. EXP-03 에서 val·s08·s09 로 확정했다. 바꾸려면 experiment-log.md 에 근거를 먼저 남긴다.
CONF = 0.4
IOU = 0.5
# 학습과 같은 입력 크기. 다르면 부품이 차지하는 픽셀 수가 달라져 성능이 바뀐다.
IMGSZ = 640

# 서버 본체. title 은 /docs 화면 맨 위에 보이는 이름일 뿐이다.
app = FastAPI(title="Smart Factory Vision Inspection")

# ★ 모델은 서버가 켜질 때 딱 한 번 읽는다.
# best.pt 를 읽는 데 몇 초가 걸리므로 요청마다 읽으면 검사가 매번 그만큼 느려진다.
# 파일 맨 위(모듈 수준)에 두면 uvicorn 이 이 파일을 import 하는 순간 한 번 실행되고, 이후 요청은 전부 이 객체를 같이 쓴다.
MODEL = YOLO(str(WEIGHTS))


@app.get("/health")  # 데코레이터: GET /health 요청이 오면 아래 함수를 실행한다
def health():
    """서버가 살아 있는지 확인하는 창구. WPF 가 연결 전에 한 번 찔러 보는 용도.

    입력: 없음
    출력: {"status": "ok", "weights": "runs/exp03_s08overlap/weights/best.pt"} 모양의 딕셔너리.
          FastAPI 가 딕셔너리를 JSON 으로 바꿔 보낸다.
    실패 시: 없음. 모델 로딩에 실패했으면 서버 자체가 뜨지 않으므로 여기까지 오지 못한다.
    """
    # relative_to 로 프로젝트 최상위 기준 상대 경로만 보여 준다. 절대 경로(C:\Users\...)를 응답에 싣지 않으려는 것.
    return {"status": "ok", "weights": str(WEIGHTS.relative_to(PROJECT_ROOT))}


@app.post("/inspect")  # 데코레이터: POST /inspect 요청이 오면 아래 함수를 실행한다
async def inspect(
    # File(...) : 요청의 파일 칸. "..." 은 필수라는 뜻. UploadFile 은 FastAPI 가 주는 업로드 파일 객체.
    image: UploadFile = File(...),
    # Form(...) : 요청의 글자 칸. int 로 선언하면 FastAPI 가 "3" 을 3 으로 바꿔 주고, 숫자가 아니면 422 오류를 대신 돌려준다.
    bolt: int = Form(...),
    nut: int = Form(...),
    washer: int = Form(...),
):
    """사진 한 장을 받아 부품 개수를 세고 기대 개수와 비교해 OK/NG 를 돌려준다.

    입력:
        image  : 업로드된 사진 파일 (jpg). 웹캠 16:9 원본이어도 되고 1:1 이어도 된다. 가운데 정사각형으로 잘라 쓴다.
        bolt, nut, washer : 기대 개수 (int). 예: 3, 5, 0. 이 값과 같아야 OK 다.
    출력:
        딕셔너리 → FastAPI 가 JSON 으로 바꿔 보낸다. 예:
        {
          "result":   "NG",
          "counts":   {"bolt": 4, "nut": 4, "washer": 0},   ← 모델이 센 개수
          "expected": {"bolt": 3, "nut": 5, "washer": 0}    ← 요청에 담겨 온 기대 개수
        }
    실패 시:
        사진으로 읽을 수 없는 파일이면 HTTPException(400). WPF 쪽에는 상태 코드 400 과 detail 글자가 간다.
        bolt/nut/washer 가 숫자가 아니면 이 함수에 들어오기 전에 FastAPI 가 422 를 돌려준다.
    """
    # await : 파일 전체가 도착할 때까지 기다린다. 결과는 bytes (사진 파일의 날것).
    data = await image.read()
    # bytes → numpy 1차원 배열(uint8) → OpenCV 가 jpg 로 해석해 (세로, 가로, 3) 배열로 푼다. 3 은 B,G,R 세 색.
    # 사진이 아니면 imdecode 는 예외 대신 None 을 돌려준다.
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        # 400 = 요청이 잘못됐다. detail 은 WPF 가 화면에 그대로 띄울 수 있는 한국어 한 줄.
        raise HTTPException(status_code=400, detail="사진으로 읽을 수 없는 파일입니다")

    # frame.shape → (세로, 가로, 3). 순서가 (높이, 너비)라 [1] 이 가로다.
    height, width = frame.shape[0], frame.shape[1]
    # 학습 사진이 전부 1:1 이라 운영 사진도 1:1 이어야 한다. 16:9 그대로 넣으면 8/6/6 처럼 틀린다 (status.md 9/8 실측).
    # crop_session.py 와 같은 함수로 같은 좌표를 얻는다. 이미 1:1 이면 잘리는 부분이 없다.
    left, upper, right, lower = center_square_box(width, height)
    # numpy 슬라이싱 [세로 범위, 가로 범위]. Pillow 의 crop 과 달리 순서가 (행, 열) 이다.
    frame = frame[upper:lower, left:right]

    # TODO 1: 추론. predict_count.py 의 predict_folder 에서 한 줄을 그대로 가져온다.
    #   입력은 경로가 아니라 frame(numpy 배열)이다. YOLO 는 배열도 받는다.
    #   imgsz=IMGSZ, conf=CONF, iou=IOU, verbose=False 를 넘기고, 리스트의 [0] 을 result 에 담는다.
    result = MODEL.predict(frame, imgsz=IMGSZ, conf=CONF, iou=IOU, verbose=False)[0]

    # 모델이 센 개수. {'bolt': n, 'nut': n, 'washer': n}. 탐지 0개인 클래스도 0 으로 들어 있다.
    counts = count_boxes(result)
    # 요청에 담겨 온 기대 개수를 counts 와 같은 모양의 딕셔너리로 만든다. 모양이 같아야 == 한 번으로 비교된다.
    expected = {"bolt": bolt, "nut": nut, "washer": washer}

    # TODO 2: 판정. 세 개수가 전부 같으면 "OK", 하나라도 다르면 "NG" 를 verdict 에 담는다.
    #   딕셔너리끼리 == 로 비교하면 키와 값이 전부 같을 때만 True 다 (predict_count.py 의 compare 와 같은 원리).
    if counts == expected:
        verdict = "OK"
    else:
        verdict = "NG"

    # TODO 3: 응답. 위 docstring 의 "출력" 모양대로 딕셔너리를 만들어 return 한다.
    #   키 이름은 "result", "counts", "expected" 세 개. WPF 가 이 이름으로 꺼내 쓰므로 바꾸면 C# 쪽도 같이 바꿔야 한다.
    return {
        "result": verdict,
        "counts": counts,
        "expected": expected,
    }
