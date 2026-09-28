# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  main.py — FastAPI 서버. 사진 한 장 + 기대 개수 → YOLO 로 세기 → OK/NG → DB 저장 → JSON 응답     ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  창구(엔드포인트)는 둘이다.
# │    GET  /health   → 서버가 살아 있는지, 모델이 올라왔는지 확인용
# │    POST /inspect  → 사진 + 기대 개수 → 판정 + inspection 표에 한 줄 저장
# │
# │  WPF(C#) ──사진+기대개수──▶ [현재 파일] ──▶ YOLO(best.pt) ──▶ count_boxes ──▶ 판정 ──▶ DB 저장 ──JSON──▶ WPF
# │                                                                                     └─▶ MSSQL inspection 표 (db.py · models.py)
# │  앞: runs/exp03_s08overlap/weights/best.pt 가 있어야 한다 (EXP-03 최종 모델, git 제외).
# │      scripts/predict_count.py(count_boxes) 와 scripts/crop_session.py(center_square_box) 를 빌려 쓴다.
# │      SQL Server 가 켜져 있고 inspection 표가 있어야 한다 (alembic upgrade head). 없으면 판정은 되지만 저장에서 500 오류.
# │  뒤: 저장된 행은 export_excel.py 가 읽어 엑셀로 뽑는다. (GET /history 는 범위 밖으로 남겼다)
# │
# │  띄우는 법 (ai-server 폴더에서):
# │      .venv/Scripts/uvicorn main:app --reload      (PowerShell 에서도 / 로 된다. --reload = 파일 고치면 자동 재시작)
# │  그 뒤 브라우저에서 http://localhost:8000/docs 를 열면 FastAPI 가 만든 시험 화면이 나온다.
# │  사진을 올리고 숫자 세 개를 넣고 Execute 를 누르면 응답이 보인다. WPF 없이도 시험할 수 있다.
# │
# │  실행 순서
# │    uvicorn 이 이 파일을 import → 모듈 수준 코드가 위에서 아래로 한 번 실행 (경로 계산, 모델 로딩, app 생성)
# │      → 이후 요청이 올 때마다 health() 또는 inspect() 만 실행된다
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : import from def async await return if else raise with
# │  ② 라이브러리가 정한 이름 (import 로 가져온 것. 한 글자도 못 바꾼다)
# │       FastAPI File Form HTTPException UploadFile   ← fastapi
# │       YOLO                                        ← ultralytics
# │       cv2.imdecode cv2.IMREAD_COLOR               ← cv2 (OpenCV)
# │       np.frombuffer np.uint8                      ← numpy
# │       Path                                        ← pathlib
# │       sys.path                                    ← sys
# │       .read() .predict() .shape .add() .commit()  ← 각 객체의 메서드·속성
# │  ③ 내가(또는 내 다른 파일이) 지은 이름
# │       이 파일: PROJECT_ROOT WEIGHTS MODEL_NAME CONF IOU IMGSZ app MODEL health inspect
# │                data frame height width left upper right lower result counts expected verdict record session
# │       내 다른 파일: SessionLocal(db.py) Inspection(models.py) count_boxes(predict_count.py) center_square_box(crop_session.py)
# │       요청 칸 이름: image bolt nut washer  ← WPF 의 form.Add(…, "image") 와 글자까지 같아야 한다
# │       응답 키 이름: "result" "counts" "expected"  ← WPF 의 GetProperty("result") 와 같아야 한다
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  import sys                              (Python 기본)  → sys.path 에 폴더 추가
# │  from pathlib import Path               (Python 기본)  → 경로 객체
# │  import cv2                             (pip: opencv)  → 바이트 → 이미지 배열
# │  import numpy as np                     (pip)          → 바이트를 숫자 배열로 감싸기
# │  from fastapi import …                  (pip)          → 서버 본체와 요청 칸 선언
# │  from ultralytics import YOLO           (pip)          → 모델 읽기·추론
# │  from db import SessionLocal            (내 파일)      → DB 세션 틀
# │  from models import Inspection          (내 파일)      → inspection 표 한 행
# │  from predict_count import count_boxes  (내 파일, scripts/) → 박스 → 클래스별 개수
# │  from crop_session import center_square_box (내 파일, scripts/) → 가운데 정사각 좌표
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  HTTP 요청/응답   : WPF 가 보내는 것이 요청, 서버가 돌려주는 것이 응답. 응답은 JSON(딕셔너리와 같은 모양의 글자).
# │  엔드포인트       : 요청을 받는 주소. "/inspect" 처럼 쓴다. 메서드(GET/POST)와 짝을 이룬다.
# │  데코레이터       : 함수 위의 @app.post("/inspect"). "이 주소로 POST 요청이 오면 이 함수를 실행해라" 를 함수에 붙이는 문법.
# │  multipart/form-data : 사진 같은 파일과 글자(숫자)를 한 요청에 같이 담아 보내는 형식. FastAPI 는 File() 과 Form() 으로 받는다.
# │                     python-multipart 패키지가 필요하다. WPF 쪽은 MultipartFormDataContent 로 만든다.
# │  async def / await : 비동기 함수. 요청을 기다리는 동안 다른 요청도 받을 수 있게 하는 문법. C# 의 async/await 와 같은 발상.
# │                     이 프로젝트에서는 "FastAPI 가 이렇게 쓰라고 한다" 정도로 알면 된다.
# │  운영값           : conf 0.4 · iou 0.5 (experiment-log.md EXP-03 에서 확정). conf 밑의 박스는 버리고, iou 만큼 겹친 같은 클래스 박스는 하나로 합친다.
# │  세션(session)    : DB 에 시킬 작업을 담는 바구니. session.add(객체) 로 담고 session.commit() 으로 확정.
# │                     commit 을 안 부르면 오류 없이 아무것도 저장되지 않는다. with 블록으로 열면 끝날 때 자동으로 닫힌다.
# │
# │  자료 모양
# │    data (bytes)                 : 업로드된 jpg 파일의 날것. 길이 = 파일 크기
# │    frame (numpy, uint8)         : (세로, 가로, 3). 마지막 3 은 B,G,R. 크롭 뒤엔 (변, 변, 3) 정사각
# │    result (ultralytics Results) : 한 장의 추론 결과. result.boxes.cls → (탐지수,) 값 0/1/2, .conf → (탐지수,), .xyxy → (탐지수, 4)
# │    counts / expected (dict)     : {"bolt": 3, "nut": 3, "washer": 3}
# │    응답 (JSON)                  : {"result": "OK"|"NG", "counts": {...}, "expected": {...}}
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import — 사전 열기
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: import(①) sys(② 인터프리터 설정 모듈)
# ▸ 왜: Python 이 import 할 때 뒤지는 폴더 목록(sys.path)에 scripts/ 를 넣으려고. 아래 PROJECT_ROOT 다음 줄에서 쓴다.
import sys

# ▸ 경로를 문자열이 아니라 객체로. / 로 이어 붙이고 .parent .name .relative_to 를 쓸 수 있다.
from pathlib import Path

# ▸ 단어 분해: import cv2(② OpenCV 의 Python 이름. 패키지 이름은 opencv-python 인데 import 할 때는 cv2)
# ▸ 왜: 업로드된 사진 바이트를 이미지 배열로 바꾸고(imdecode) 가운데를 자르는 데 쓴다.
import cv2
# ▸ 단어 분해: import numpy(② 숫자 배열 라이브러리) as np(③ 관례 별명)
# ▸ 왜: 사진 바이트를 OpenCV 가 읽을 수 있는 숫자 배열로 감싸는 데 쓴다(frombuffer).
import numpy as np

# ▸ 단어 분해: from fastapi import FastAPI(② 서버 본체 클래스), File(② 파일 칸 선언), Form(② 글자 칸 선언), HTTPException(② 오류 응답), UploadFile(② 업로드 파일 타입)
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
# ▸ YOLO(② 클래스): 학습된 best.pt 를 읽어 추론하는 객체를 만든다. scripts/train.py 에서 학습할 때 쓴 것과 같은 클래스.
from ultralytics import YOLO

# ▸ 단어 분해: from db(③ 같은 폴더의 db.py) import ( SessionLocal(③ db.py 가 만든 변수) , )
# ▸ 뜻: 세션을 찍어내는 틀. SessionLocal() 로 부르면 DB 작업 바구니 하나가 나온다.
# ▸ 괄호와 줄바꿈은 코드 정렬 도구(포매터)가 넣은 것. from db import SessionLocal 과 같다.
# ▸ 왜 바로 import 되나: uvicorn 을 ai-server 에서 띄우므로 "지금 폴더" 의 db.py 가 보인다.
from db import (
    SessionLocal,
)  # 세션을 찍어내는 틀. SessionLocal() 로 부르면 DB 작업 바구니 하나가 나온다
# ▸ Inspection(③ models.py 의 클래스): inspection 표 한 행 = Inspection 객체 하나.
from models import Inspection  # inspection 표 한 행 = Inspection 객체 하나

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  경로와 상수 — uvicorn 이 이 파일을 import 하는 순간 한 번 정해진다
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: PROJECT_ROOT(③) = Path(__file__(① 이 파일 경로)).resolve(② 절대 경로로)().parent(② 폴더 = ai-server).parent(② 그 위 = 최상위)
# ▸ 뜻: smart-factory-vision/ 의 절대 경로. export_excel.py 와 같은 계산.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ▸ 단어 분해: sys.path(② import 검색 폴더 목록).insert(② 끼워 넣기)(0(맨 앞에), str(② Path → 문자열)(PROJECT_ROOT / "scripts"))
# ▸ 뜻: scripts/ 폴더를 import 검색 경로 맨 앞에 넣는다. 그래야 아래 두 줄의 from … import 가 된다.
# ▸ 왜 맨 앞: predict_count.py 안에서 "from verify_counts import …" 를 하므로 scripts/ 자체가 경로에 있어야 한다.
# ▸ 왜 str: sys.path 는 문자열 목록이라 Path 객체를 그대로 넣으면 안 된다.
# ▸ 다른 선택: scripts/ 를 패키지로 만들어(빈 __init__.py) 정식 import 하는 방법도 있다. 파일 두 개 빌리는 데는 이게 짧다.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
# ▸ count_boxes(③ predict_count.py 의 함수): 추론 결과 → {'bolt': n, 'nut': n, 'washer': n}. predict_count.py 65행.
# ▸ 이 import 는 위 sys.path 줄 "뒤" 에 있어야 한다. 순서를 바꾸면 ModuleNotFoundError.
from predict_count import count_boxes

# ▸ center_square_box(③ crop_session.py 의 함수): (가로, 세로) → 가운데 정사각형 좌표. 웹캠 16:9 원본을 학습 때와 같은 1:1 로 맞춘다.
from crop_session import center_square_box

# ▸ 단어 분해: WEIGHTS(③) = PROJECT_ROOT / "runs" / "exp03_s08overlap" / "weights" / "best.pt"  (Path 의 / 로 이어 붙임)
# ▸ 뜻: EXP-03 최종 모델 가중치 경로. 기본값이 EXP-01 인 predict_count.py 와 달리 여기는 운영용이라 최종 모델을 고정한다.
# ▸ 다른 선택: 다른 실험으로 바꾸려면 폴더 이름만 바꾼다. 아래 MODEL_NAME 이 자동으로 따라간다.
WEIGHTS = PROJECT_ROOT / "runs" / "exp03_s08overlap" / "weights" / "best.pt"
# ▸ 단어 분해: MODEL_NAME(③) = WEIGHTS.parent(② weights/).parent(② exp03_s08overlap/).name(② 마지막 폴더 이름 글자)
# ▸ 뜻: DB 의 model_name 컬럼에 들어갈 이름 "exp03_s08overlap". 경로에서 실험 폴더 이름을 꺼낸다.
# ▸ 왜 글자로 안 적나: WEIGHTS 를 바꾸면 이름도 따라 바뀌어 둘이 어긋나지 않는다.
MODEL_NAME = WEIGHTS.parent.parent.name
# ▸ 운영값. EXP-03 에서 val·s08·s09 로 확정했다. 바꾸려면 experiment-log.md 에 근거를 먼저 남긴다.
# ▸ CONF: 이 확신도 밑의 박스는 버린다. 0.25 면 헛것이 늘고 0.6 이면 진짜를 놓치기 시작했다(EXP-01 conf 비교).
# ▸ IOU: 같은 클래스 박스가 이만큼 겹치면 하나로 합친다. 0.7(기본) → 0.5 로 낮춰 교차한 볼트의 중복 박스를 지웠다.
CONF = 0.4
IOU = 0.5
# ▸ 학습과 같은 입력 크기(train.py 의 imgsz=640). 다르면 부품이 차지하는 픽셀 수가 달라져 성능이 바뀐다.
IMGSZ = 640

# ▸ 단어 분해: app(③) = FastAPI(② 클래스)(title(키워드 인자)="…")
# ▸ 뜻: 서버 본체 객체. uvicorn main:app 의 "app" 이 이 변수다. title 은 /docs 화면 맨 위에 보이는 이름일 뿐이다.
app = FastAPI(title="Smart Factory Vision Inspection")

# ▸ 단어 분해: MODEL(③) = YOLO(② 클래스)(str(WEIGHTS)(경로를 글자로))
# ▸ 뜻: best.pt 를 읽어 추론 준비가 된 모델 객체.
# ▸ ★ 왜 여기(모듈 수준)인가: best.pt 를 읽는 데 몇 초가 걸린다. 요청마다 읽으면 검사가 매번 그만큼 느려진다.
#   파일 맨 위에 두면 uvicorn 이 이 파일을 import 하는 순간 한 번 실행되고, 이후 요청은 전부 이 객체를 같이 쓴다. WPF 의 static HttpClient 와 같은 발상.
# ▸ 실패 시: 파일이 없으면 FileNotFoundError 로 서버가 아예 안 뜬다. 그래서 /health 는 "여기까지 왔으면 모델은 있다" 고 본다.
MODEL = YOLO(str(WEIGHTS))


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  엔드포인트 — 요청이 올 때마다 실행되는 함수들
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: @(① 데코레이터 표시) app.get(② "GET 요청을 이 함수에 연결")("/health"(주소))
# ▸ 뜻: GET /health 요청이 오면 바로 아래 함수를 실행해라. 함수 이름(health)은 주소와 무관하다.
# ▸ 다른 선택: @app.post 로 바꾸면 POST 로만 받는다. 브라우저 주소창은 GET 이라 그러면 주소창으로 못 연다.
@app.get("/health")  # 데코레이터: GET /health 요청이 오면 아래 함수를 실행한다
def health():
    """서버가 살아 있는지 확인하는 창구. WPF 가 연결 전에 한 번 찔러 보는 용도.

    입력: 없음
    출력: {"status": "ok", "weights": "runs/exp03_s08overlap/weights/best.pt"} 모양의 딕셔너리.
          FastAPI 가 딕셔너리를 JSON 으로 바꿔 보낸다.
    실패 시: 없음. 모델 로딩에 실패했으면 서버 자체가 뜨지 않으므로 여기까지 오지 못한다.
    """
    # ▸ 단어 분해: return {"status": "ok", "weights": str(WEIGHTS.relative_to(② 이 기준 상대 경로)(PROJECT_ROOT))}
    # ▸ 왜 relative_to: 절대 경로(C:\Users\…)를 응답에 싣지 않으려는 것. 사용자 이름 같은 정보가 밖으로 나가지 않게.
    return {"status": "ok", "weights": str(WEIGHTS.relative_to(PROJECT_ROOT))}


# ▸ 단어 분해: @app.post(② "POST 요청을 이 함수에 연결")("/inspect")
# ▸ 왜 POST: 사진 파일을 본문에 실어 보내야 해서. GET 은 본문이 없다.
@app.post("/inspect")  # 데코레이터: POST /inspect 요청이 오면 아래 함수를 실행한다
# ▸ 단어 분해: async(① 비동기) def inspect(③)( 인자 4개 … ):
# ▸ 인자 한 줄의 모양:  이름(③ 요청 칸 이름): 타입(②) = File(...)/Form(...)(② 어느 칸에서 꺼낼지)
# ▸ ... (줄임표) 는 Python 의 Ellipsis 객체. FastAPI 는 이것을 "필수" 라는 뜻으로 쓴다. 기본값을 주면(Form(0)) 선택 칸이 된다.
async def inspect(
    # File(...) : 요청의 파일 칸. "..." 은 필수라는 뜻. UploadFile 은 FastAPI 가 주는 업로드 파일 객체.
    # 이름 image 는 WPF 의 form.Add(new ByteArrayContent(jpeg), "image", "frame.jpg") 의 "image" 와 같아야 한다.
    image: UploadFile = File(...),
    # Form(...) : 요청의 글자 칸. int 로 선언하면 FastAPI 가 "3" 을 3 으로 바꿔 주고, 숫자가 아니면 422 오류를 대신 돌려준다.
    # 그래서 이 함수 안에는 "숫자인지 확인" 하는 코드가 없다. 타입 선언이 곧 검사다.
    bolt: int = Form(...),
    nut: int = Form(...),
    washer: int = Form(...),
):
    """사진 한 장을 받아 부품 개수를 세고 기대 개수와 비교해 OK/NG 를 돌려준다.

    입력:
        image  : 업로드된 사진 파일 (jpg). 웹캠 16:9 원본이어도 되고 1:1 이어도 된다. 가운데 정사각형으로 잘라 쓴다.
        bolt, nut, washer : 기대 개수 (int). 예: 3, 5, 0. 이 값과 같아야 OK 다.
    출력:
        딕셔너리 → FastAPI 가 JSON 으로 바꿔 보낸다. 그 전에 같은 내용을 inspection 표에 한 줄 저장한다. 예:
        {
          "result":   "NG",
          "counts":   {"bolt": 4, "nut": 4, "washer": 0},   ← 모델이 센 개수
          "expected": {"bolt": 3, "nut": 5, "washer": 0}    ← 요청에 담겨 온 기대 개수
        }
    실패 시:
        사진으로 읽을 수 없는 파일이면 HTTPException(400). WPF 쪽에는 상태 코드 400 과 detail 글자가 간다.
        bolt/nut/washer 가 숫자가 아니면 이 함수에 들어오기 전에 FastAPI 가 422 를 돌려준다.
        DB 가 꺼져 있거나 표가 없으면 commit 에서 sqlalchemy.exc.OperationalError/ProgrammingError → FastAPI 가 500 을 돌려준다.
    """
    # ── 1. 바이트 → 이미지 ───────────────────────────────────────────────────────────
    # ▸ 단어 분해: data(③) = await(① 끝날 때까지 기다림) image.read(② UploadFile 의 메서드)()
    # ▸ 뜻: 파일 전체가 도착할 때까지 기다린 뒤 bytes(사진 파일의 날것)로 받는다.
    # ▸ 왜 await: read() 가 "기다려야 하는 함수(코루틴)" 라서. await 없이 부르면 bytes 가 아니라 코루틴 객체가 와서 다음 줄이 죽는다.
    data = await image.read()
    # ▸ 단어 분해: frame(③) = cv2.imdecode(② 메모리의 이미지 파일을 배열로)( np.frombuffer(② 바이트를 배열로 감쌈)(data, dtype=np.uint8(0~255 정수)) , cv2.IMREAD_COLOR(② 컬러로) )
    # ▸ 뜻: bytes → numpy 1차원 배열(uint8) → OpenCV 가 jpg 로 해석해 (세로, 가로, 3) 배열로 푼다. 3 은 B,G,R 세 색.
    # ▸ 왜 두 단계: imdecode 는 numpy 배열만 받는다. bytes 를 복사 없이 배열로 "보이게" 하는 게 frombuffer.
    # ▸ 실패 시: 사진이 아니면 imdecode 는 예외 대신 None 을 돌려준다. 그래서 다음 줄에서 None 을 확인한다.
    # ▸ 다른 선택: cv2.imread(경로) 는 "파일 경로" 에서 읽는 함수. 우리는 파일을 디스크에 안 쓰고 메모리에서 바로 푼다.
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    # ▸ 단어 분해: if frame is(① 같은 객체인가) None(① 없음):
    # ▸ 왜 == 이 아니라 is: numpy 배열에 == 를 쓰면 원소별 비교가 되어 오류가 난다. None 검사는 항상 is.
    if frame is None:
        # ▸ 단어 분해: raise(① 예외 던지기) HTTPException(② FastAPI 오류 응답)(status_code=400, detail="…")
        # ▸ 뜻: 400(요청이 잘못됨) 응답을 보내고 함수를 끝낸다. detail 은 WPF 가 화면에 그대로 띄울 수 있는 한국어 한 줄.
        # ▸ 다른 선택: 그냥 return {"error": …} 하면 상태 코드가 200 이라 WPF 의 IsSuccessStatusCode 분기가 오류를 못 알아본다.
        raise HTTPException(status_code=400, detail="사진으로 읽을 수 없는 파일입니다")

    # ── 2. 가운데 1:1 크롭 ───────────────────────────────────────────────────────────
    # ▸ 단어 분해: height(③), width(③) = frame.shape(② 배열 크기 튜플)[0], frame.shape[1]   (튜플 언패킹: 오른쪽 둘을 왼쪽 둘에 나눠 담음)
    # ▸ frame.shape → (세로, 가로, 3). 순서가 (높이, 너비)라 [0] 이 세로, [1] 이 가로다. 헷갈리기 쉬운 곳.
    height, width = frame.shape[0], frame.shape[1]
    # ▸ 단어 분해: left, upper, right, lower(③ 네 개 언패킹) = center_square_box(③)(width, height)
    # ▸ 뜻: 가운데 정사각형의 (왼쪽 x, 위 y, 오른쪽 x, 아래 y). 인자 순서는 (가로, 세로) — 위 줄의 shape 와 반대라 주의.
    # ▸ 왜: 학습 사진이 전부 1:1 이라 운영 사진도 1:1 이어야 한다. 16:9 그대로 넣으면 8/6/6 처럼 틀린다 (D-007, 9/8 실측).
    # ▸ crop_session.py 와 같은 함수를 쓰므로 학습 데이터를 자른 것과 정확히 같은 좌표가 나온다. 이미 1:1 이면 잘리는 부분이 없다.
    left, upper, right, lower = center_square_box(width, height)
    # ▸ 단어 분해: frame = frame[upper:lower(세로 범위), left:right(가로 범위)]   (numpy 슬라이싱)
    # ▸ 뜻: 배열에서 정사각형 부분만 잘라 frame 에 다시 넣는다.
    # ▸ 순서 주의: numpy 는 [행(세로), 열(가로)]. Pillow 의 crop((left, upper, right, lower)) 과 순서가 다르다.
    frame = frame[upper:lower, left:right]

    # ── 3. 추론 ──────────────────────────────────────────────────────────────────────
    # ▸ 단어 분해: result(③) = MODEL.predict(② 추론)(frame(배열), imgsz=IMGSZ, conf=CONF, iou=IOU, verbose=False(로그 끄기))[0](첫 장)
    # ▸ 뜻: 크롭한 프레임 한 장을 640 으로 줄여 추론하고, 결과 목록의 첫 번째(유일한) 것을 result 에 담는다.
    # ▸ predict 는 여러 장을 받을 수 있어 리스트를 돌려준다. 한 장인 우리는 [0] 만 꺼낸다.
    # ▸ 입력이 경로가 아니라 numpy 배열이다. YOLO 는 배열도 받는다. predict_count.py 의 predict_folder 와 같은 호출.
    # ▸ iou=IOU 가 predict_count.py 에는 없던 인자다 (그쪽은 기본 0.7). 운영값 0.5 는 EXP-03 에서 확정.
    # ▸ verbose=False: 없으면 요청마다 터미널에 "image 1/1 … 3 bolts, 3 nuts …" 가 찍힌다.
    result = MODEL.predict(frame, imgsz=IMGSZ, conf=CONF, iou=IOU, verbose=False)[0]

    # ▸ 단어 분해: counts(③) = count_boxes(③)(result)
    # ▸ 뜻: result.boxes.cls (탐지수,) 를 클래스별로 세어 {'bolt': n, 'nut': n, 'washer': n}. 탐지 0개인 클래스도 0 으로 들어 있다.
    counts = count_boxes(result)
    # ▸ 단어 분해: expected(③) = {"bolt": bolt, "nut": nut, "washer": washer}   (딕셔너리 리터럴. 값은 인자로 받은 int)
    # ▸ 왜 같은 모양으로: counts 와 키 이름·순서가 같아야 아래에서 == 한 번으로 비교된다.
    expected = {"bolt": bolt, "nut": nut, "washer": washer}

    # ── 4. 판정 ──────────────────────────────────────────────────────────────────────
    # ▸ 단어 분해: if counts ==(① 같은 내용인가) expected:
    # ▸ 뜻: 딕셔너리끼리 == 는 키와 값이 전부 같을 때만 True. 세 개수가 모두 맞아야 OK.
    # ▸ 하나라도 다르면 NG. 어느 부품이 틀렸는지는 응답의 counts 와 expected 를 나란히 보면 안다(엑셀의 검출/기대 열).
    if counts == expected:
        verdict = "OK"
    else:
        verdict = "NG"

    # ── 5. DB 저장 ───────────────────────────────────────────────────────────────────
    # ▸ 왜 응답 전에 저장하나: 저장에 실패하면 500 이 나가서 "판정은 됐는데 이력에는 없다" 는 상태를 만들지 않는다.

    # ▸ 단어 분해: record(③) = Inspection(③ models.py 의 클래스)( result=verdict, bolt_count=counts["bolt"], … )   (키워드 인자 8개)
    # ▸ 뜻: 표 한 행을 Python 객체로 만든다. 키워드 인자 이름 = inspection 표의 컬럼 이름 (models.py 의 속성 이름).
    # ▸ 아직 Python 메모리에만 있다. DB 는 이 객체의 존재를 모른다.
    # ▸ id 와 created_at 은 적지 않는다. commit 때 DB 가 자동 번호와 현재 시각으로 채운다(models.py 의 primary_key / server_default).
    # ▸ ★ Inspection(클래스)이다. inspect(이 함수)가 아니다. 한 글자 차이로 자기 자신을 다시 부르게 된다(9/22 실제로 한 번 틀림).
    record = Inspection(
        result=verdict,
        bolt_count=counts["bolt"],
        nut_count=counts["nut"],
        washer_count=counts["washer"],
        bolt_expected=expected["bolt"],
        nut_expected=expected["nut"],
        washer_expected=expected["washer"],
        model_name=MODEL_NAME,
    )

    # ▸ 단어 분해: with(① 블록 끝나면 정리) SessionLocal(③ 틀)()(세션 하나 생성) as(①) session(③):
    # ▸ 뜻: 세션 하나를 열고 블록이 끝나면 자동으로 닫는다. 파일을 with open 으로 여는 것과 같은 문법. C# 의 using var.
    with SessionLocal() as session:
        # ▸ session.add(② 바구니에 담기)(record)
        # ▸ 이 시점에는 DB 로 아무것도 가지 않았다. SSMS 에서 SQL 문장을 "적기만 한" 상태.
        session.add(record)
        # ▸ session.commit(② 확정)()
        # ▸ 여기서 INSERT INTO inspection (...) VALUES (...) 가 만들어져 DB 로 가고 COMMIT 된다 (db.py 의 ECHO_SQL 로 터미널에 보인다).
        # ▸ 이 줄이 없으면 오류 없이 저장이 안 된다 (블록이 끝날 때 ROLLBACK). 가장 흔한 실수. SSMS 의 F5 에 해당.
        session.commit()

    # ── 6. 응답 ──────────────────────────────────────────────────────────────────────
    # ▸ 딕셔너리를 return 하면 FastAPI 가 JSON 으로 바꿔 보낸다. 상태 코드는 자동으로 200.
    # ▸ 키 이름 "result", "counts", "expected" 는 WPF 가 GetProperty("result") 처럼 이 이름으로 꺼내 쓰므로 바꾸면 C# 쪽도 같이 바꿔야 한다.
    return {
        "result": verdict,
        "counts": counts,
        "expected": expected,
    }
