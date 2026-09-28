# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  db.py — SQLAlchemy 로 SQL Server 에 접속하기 위한 세 가지(engine · SessionLocal · Base)를 만든다   ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 읽히나 ─────────────────────────────────────────────────────────
# │
# │  만드는 것 셋
# │    engine       : DB 접속 담당. SSMS 연결 창에서 Connect 를 누르는 일을 코드로 하는 것.
# │    SessionLocal : 세션을 찍어내는 틀. 세션 = DB 에 시킬 작업을 담는 바구니 (add → commit).
# │    Base         : 모든 모델 클래스(표의 설계를 적은 클래스)의 부모. models.py 의 Inspection 이 이것을 상속한다.
# │
# │  .env ──▶ check_db.load_config ──▶ [현재 파일] ──▶ models.py      (Base 를 상속)
# │                                         ├────────▶ main.py        (SessionLocal 로 세션을 열어 검사 결과를 저장)
# │                                         ├────────▶ export_excel.py (engine 으로 SELECT)
# │                                         └────────▶ Alembic        (engine 과 Base 를 보고 CREATE TABLE 을 만든다)
# │  앞: ai-server/.env 에 접속 정보가 있어야 한다. SQL Server 서비스가 켜져 있어야 한다. 접속 자체는 check_db.py 로 먼저 확인.
# │  뒤: 이 파일은 표를 만들지도, 행을 넣지도 않는다. 접속 수단만 준비한다.
# │
# │  직접 실행하면 접속 시험을 한다 (ai-server 폴더에서):
# │      .venv/Scripts/python db.py
# │
# │  실행 순서: 다른 파일이 import 하는 순간 위에서 아래로 한 번 — build_url 정의 → engine 생성 → SessionLocal 생성 → Base 정의.
# │           맨 아래 if 블록은 직접 실행할 때만.
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : from import def return class pass with if
# │  ② 라이브러리가 정한 이름
# │       quote_plus                         ← urllib.parse (Python 기본)
# │       create_engine text                 ← sqlalchemy
# │       DeclarativeBase sessionmaker       ← sqlalchemy.orm
# │       .connect() .execute() .scalar()    ← 엔진·연결 객체의 메서드
# │  ③ 내가 지은 이름
# │       이 파일: ECHO_SQL build_url engine SessionLocal Base odbc connection name
# │       내 다른 파일: build_connection_string load_config (check_db.py)
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  from urllib.parse import quote_plus                  (Python 기본) → 글자를 URL 에 넣을 수 있게 변환
# │  from sqlalchemy import create_engine, text           (pip)         → 엔진 만들기, SQL 글자 감싸기
# │  from sqlalchemy.orm import DeclarativeBase, sessionmaker (pip)     → 모델 부모, 세션 틀
# │  from check_db import build_connection_string, load_config (내 파일) → .env 읽기, ODBC 문자열 조립
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  ORM      : 표 ↔ 클래스, 행 ↔ 객체를 짝지어 주는 도구. SQLAlchemy 가 Python 의 대표 ORM.
# │  엔진     : 접속 정보를 들고 있다가 필요할 때 DB 와 연결을 맺어 주는 객체. 프로그램에 하나만 둔다.
# │  세션     : 작업 한 묶음. session.add(객체) 로 담고 session.commit() 으로 확정.
# │             commit 을 안 부르면 오류 없이 아무것도 저장되지 않는다 (SQLD 의 COMMIT 과 같은 것).
# │  접속 URL : SQLAlchemy 가 받는 접속 주소 형식. "mssql+pyodbc://…" = "SQL Server 에, pyodbc 를 통해".
# │             우리는 check_db.py 가 만드는 ODBC 연결 문자열을 그대로 실어 보내는 odbc_connect 방식을 쓴다.
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: from urllib.parse(② URL 다루는 모듈) import quote_plus(② 함수)
# ▸ 뜻: 글자를 URL 에 넣을 수 있게 바꿔 준다. 공백 → "+", ";" → "%3B", "{" → "%7B" 처럼.
# ▸ 왜: ODBC 연결 문자열에는 공백·중괄호·세미콜론이 들어 있어서 그대로는 URL 에 못 넣는다.
from urllib.parse import quote_plus

# ▸ 단어 분해: from sqlalchemy import create_engine(② 엔진 만드는 함수), text(② SQL 글자를 실행 가능한 객체로 감싸는 함수)
# ▸ text 는 아래 접속 시험에서만 쓴다. SQLAlchemy 2.0 은 날 문자열 SQL 을 거부하고 text() 로 감싸라고 한다.
from sqlalchemy import create_engine, text

# ▸ 단어 분해: from sqlalchemy.orm(② ORM 부분) import DeclarativeBase(② 모델 부모를 만들 때 상속하는 클래스), sessionmaker(② 세션 틀을 만드는 함수)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ▸ 단어 분해: from check_db(③ 같은 폴더의 check_db.py) import build_connection_string(③), load_config(③)
# ▸ 왜 빌려 쓰나: 접속 정보 읽기와 ODBC 연결 문자열 조립은 8월에 만든 check_db.py 에 이미 있다.
#   같은 일을 두 군데서 하면 .env 항목이 바뀔 때 한쪽만 고치는 실수가 생긴다.
# ▸ 주의: 이 줄 때문에 ai-server 폴더에서 실행해야 한다(Python 은 "지금 폴더" 에서 check_db 를 찾는다). export_excel.py 도 같은 제약.
from check_db import build_connection_string, load_config

# ▸ 단어 분해: ECHO_SQL(③ 대문자 = 설정값 관습) = True(①)
# ▸ 뜻: SQLAlchemy 가 DB 로 보내는 실제 SQL 을 터미널에 찍을지. 배우는 동안 True.
# ▸ 왜: "객체를 add 했더니 어떤 INSERT 문이 나가는가" 를 눈으로 볼 수 있다. 로그가 시끄러우면 False.
ECHO_SQL = True


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  접속 URL
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: def build_url(③)() -> str(타입 힌트: 문자열을 돌려줌):
def build_url() -> str:
    """SQLAlchemy 가 받는 접속 URL 을 만든다.

    입력: 없음 (.env 를 check_db.load_config 로 읽는다)
    출력: str. 예: "mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC+Driver+18+for+SQL+Server%7D%3BSERVER%3Dlocalhost%2C1433%3B..."
          비밀번호가 들어 있으므로 이 값을 print 하거나 로그에 남기지 않는다.
    실패 시: .env 가 없거나 필수 항목이 비면 load_config 가 안내문을 찍고 SystemExit 로 끝낸다.
    """
    # ▸ 단어 분해: odbc(③) = build_connection_string(③)(load_config(③)())   (안쪽 함수 결과를 바깥 함수 인자로)
    # ▸ 뜻: .env 를 읽어 "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;…" 한 줄을 만든다. check_db.py 와 똑같은 문자열.
    odbc = build_connection_string(load_config())
    # ▸ 단어 분해: return "mssql+pyodbc:///?odbc_connect="(② SQLAlchemy 가 정한 접두어) +(문자열 잇기) quote_plus(odbc)
    # ▸ 뜻: "SQL Server 방언으로, pyodbc 를 통해, 이 ODBC 문자열로 붙어라".
    # ▸ mssql+pyodbc: 이 앞부분을 보고 SQLAlchemy 가 TOP/IDENTITY 같은 SQL Server 문법을 고른다. postgresql+psycopg2 라면 PostgreSQL 문법.
    # ▸ /// 뒤가 비어 있는 이유: 보통은 사용자:비밀번호@서버/DB 를 여기 적지만, 우리는 전부 odbc_connect 안에 넣었다.
    # ▸ 다른 선택: "mssql+pyodbc://user:pw@localhost:1433/db?driver=ODBC+Driver+18…" 처럼 풀어 쓸 수도 있다. 항목이 많아 문자열을 통째로 싣는 쪽이 짧다.
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  엔진 · 세션 틀 · 모델 부모 — 모듈 수준이라 import 될 때 한 번 만들어진다
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: engine(③) = create_engine(②)(build_url()(접속 URL 글자), echo=ECHO_SQL(SQL 찍기))
# ▸ 뜻: 엔진 하나. 첫 번째 인자가 접속 URL, echo 는 보내는 SQL 을 터미널에 찍을지.
# ▸ 이 줄에서는 아직 접속하지 않는다. 엔진은 실제로 SQL 을 보낼 때 처음 연결을 맺는다(지연 연결).
# ▸ ★ build_url 에 괄호를 붙여야 URL(글자)이 넘어간다. 괄호를 빼면 함수 자체가 넘어가 오류가 난다.
engine = create_engine(build_url(), echo=ECHO_SQL)

# ▸ 단어 분해: SessionLocal(③ 대문자 시작 = 클래스처럼 쓰는 것) = sessionmaker(②)(bind(묶을 엔진)=engine)
# ▸ 뜻: 세션을 찍어내는 틀. bind=engine 은 "이 틀로 만든 세션은 위 엔진으로 접속하라" 는 뜻이라 engine 보다 아래에 있어야 한다.
# ▸ 돌려받는 것은 세션이 아니라 틀(클래스처럼 쓰는 것)이라 이름을 대문자로 시작한다.
# ▸ main.py 에서 SessionLocal() 처럼 괄호를 붙여 부르면 그때 세션 하나가 나온다.
SessionLocal = sessionmaker(bind=engine)


# ▸ 단어 분해: class Base(③) (DeclarativeBase(② 부모)):
class Base(DeclarativeBase):
    """모든 모델 클래스의 부모. 내용은 비어 있고 상속만 받아 둔다.

    SQLAlchemy 는 "Base 를 상속한 클래스 = 표" 로 알아보고 그 목록을 Base.metadata 에 모은다.
    Alembic 이 이 목록을 실제 DB 와 비교해서 CREATE TABLE 을 만든다.
    pass 는 "본문이 없다" 는 Python 문법이다.
    """

    # ▸ pass(①): 클래스 본문이 docstring 뿐이라면 없어도 되지만, "일부러 비워 뒀다" 는 표시로 둔다.
    pass


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  접속 시험 — 이 파일을 직접 실행했을 때만. main.py 나 Alembic 이 import 할 때는 돌지 않는다.
# ═══════════════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ▸ 단어 분해: with engine.connect(② 실제 연결 맺기)() as connection(③):
    # ▸ 뜻: DB 에 붙어 connection 을 얻고, 블록을 나갈 때 자동으로 닫는다. 닫지 않으면 연결이 쌓인다.
    # ▸ engine.connect() 가 실제로 DB 에 붙는 첫 순간이다. 접속 정보가 틀렸으면 여기서 오류가 난다.
    with engine.connect() as connection:
        # ▸ 단어 분해: name(③) = connection.execute(② SQL 실행)(text(② 글자를 SQL 객체로)("SELECT DB_NAME()")).scalar(② 한 칸만 꺼내기)()
        # ▸ DB_NAME() : 지금 접속한 데이터베이스 이름을 돌려주는 SQL Server 함수. check_db.py 에서도 썼다.
        # ▸ .scalar() : 결과가 한 행 한 칸일 때 그 값 하나만. 여러 행이면 .fetchall().
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"[성공] SQLAlchemy 로 접속했습니다. 데이터베이스: {name}")
