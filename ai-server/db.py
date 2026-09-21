# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   SQLAlchemy 로 SQL Server 에 접속하기 위한 세 가지를 만들어 둔다.
#     engine       : DB 접속 담당. SSMS 연결 창에서 Connect 를 누르는 일을 코드로 하는 것.
#     SessionLocal : 세션을 찍어내는 틀. 세션 = DB 에 시킬 작업을 담는 바구니 (add → commit).
#     Base         : 모든 모델 클래스(표의 설계를 적은 클래스)의 부모. models.py 의 Inspection 이 이것을 상속한다.
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   .env ──▶ check_db.load_config ──▶ [현재 파일] ──▶ models.py (Base 를 상속)
#                                          └────────▶ main.py   (SessionLocal 로 세션을 열어 검사 결과를 저장)
#                                          └────────▶ Alembic   (engine 과 Base 를 보고 CREATE TABLE 을 만든다)
#   앞: ai-server/.env 에 접속 정보가 있어야 한다. SQL Server 서비스가 켜져 있어야 한다.
#       접속 자체가 되는지는 check_db.py 로 먼저 확인할 수 있다.
#   뒤: 이 파일은 표를 만들지도, 행을 넣지도 않는다. 접속 수단만 준비한다.
#
#   직접 실행하면 접속 시험을 한다 (ai-server 폴더에서):
#       .venv/Scripts/python db.py
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   ORM     : 표 ↔ 클래스, 행 ↔ 객체를 짝지어 주는 도구. SQLAlchemy 가 Python 의 대표 ORM 이다.
#   엔진    : 접속 정보를 들고 있다가 필요할 때 DB 와 연결을 맺어 주는 객체. 프로그램에 하나만 둔다.
#   세션    : 작업 한 묶음. session.add(객체) 로 담고 session.commit() 으로 확정한다.
#             commit 을 안 부르면 오류 없이 아무것도 저장되지 않는다 (SQLD 의 COMMIT 과 같은 것).
#   접속 URL: SQLAlchemy 가 받는 접속 주소 형식. "mssql+pyodbc://..." = "SQL Server 에, pyodbc 를 통해".
#             우리는 check_db.py 가 만드는 ODBC 연결 문자열을 그대로 실어 보내는 odbc_connect 방식을 쓴다.
# ─────────────────────────────────────────────────────────────────────────────

# quote_plus : 글자를 URL 에 넣을 수 있게 바꿔 준다. 공백 → "+", ";" → "%3B" 처럼.
#              ODBC 연결 문자열에는 공백·중괄호·세미콜론이 들어 있어서 그대로는 URL 에 못 넣는다.
from urllib.parse import quote_plus

# create_engine : 접속 URL 을 받아 엔진을 만든다.  text : SQL 글자를 SQLAlchemy 가 실행할 수 있는 객체로 감싼다 (아래 접속 시험에서만 쓴다).
from sqlalchemy import create_engine, text

# DeclarativeBase : 모델 클래스들의 부모를 만들 때 상속하는 클래스.  sessionmaker : 세션을 찍어내는 틀을 만든다.
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 접속 정보 읽기와 ODBC 연결 문자열 조립은 8월에 만든 check_db.py 의 함수를 그대로 빌린다.
# 같은 일을 두 군데서 하면 .env 항목이 바뀔 때 한쪽만 고치는 실수가 생긴다.
from check_db import build_connection_string, load_config

# 배우는 동안 True 로 둔다. SQLAlchemy 가 DB 로 보내는 실제 SQL 이 터미널에 찍힌다.
# "객체를 add 했더니 어떤 INSERT 문이 나가는가" 를 눈으로 볼 수 있다. 로그가 시끄러우면 False.
ECHO_SQL = True


def build_url() -> str:
    """SQLAlchemy 가 받는 접속 URL 을 만든다.

    입력: 없음 (.env 를 check_db.load_config 로 읽는다)
    출력: str. 예: "mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC+Driver+18+for+SQL+Server%7D%3BSERVER%3Dlocalhost%2C1433%3B..."
          비밀번호가 들어 있으므로 이 값을 print 하거나 로그에 남기지 않는다.
    실패 시: .env 가 없거나 필수 항목이 비면 load_config 가 안내문을 찍고 SystemExit 로 끝낸다.
    """
    # "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;..." 한 줄.
    odbc = build_connection_string(load_config())
    # mssql+pyodbc : "SQL Server 방언으로, pyodbc 를 통해". 이 앞부분을 보고 SQLAlchemy 가 TOP/IDENTITY 같은 SQL Server 문법을 고른다.
    # odbc_connect= 뒤에 ODBC 문자열을 URL 용으로 바꿔 통째로 붙인다.
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


# 엔진. 첫 번째 인자가 접속 URL, echo 는 보내는 SQL 을 터미널에 찍을지.
# 이 줄에서는 아직 접속하지 않는다. 엔진은 실제로 SQL 을 보낼 때 처음 연결을 맺는다.
# build_url 에 괄호를 붙여야 URL(글자)이 넘어간다. 괄호를 빼면 함수 자체가 넘어가 오류가 난다.
engine = create_engine(build_url(), echo=ECHO_SQL)

# 세션을 찍어내는 틀. bind=engine 은 "이 틀로 만든 세션은 위 엔진으로 접속하라" 는 뜻이라 engine 보다 아래에 있어야 한다.
# 돌려받는 것은 세션이 아니라 틀(클래스처럼 쓰는 것)이라 이름을 대문자로 시작한다.
# main.py 에서 SessionLocal() 처럼 괄호를 붙여 부르면 그때 세션 하나가 나온다.
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """모든 모델 클래스의 부모. 내용은 비어 있고 상속만 받아 둔다.

    SQLAlchemy 는 "Base 를 상속한 클래스 = 표" 로 알아보고 그 목록을 Base.metadata 에 모은다.
    Alembic 이 이 목록을 실제 DB 와 비교해서 CREATE TABLE 을 만든다.
    pass 는 "본문이 없다" 는 Python 문법이다.
    """

    pass


# 이 파일을 직접 실행했을 때만 도는 접속 시험. main.py 나 Alembic 이 import 할 때는 돌지 않는다.
if __name__ == "__main__":
    # with : 블록을 나갈 때 연결을 자동으로 닫아 준다. 닫지 않으면 연결이 쌓인다.
    # engine.connect() 가 실제로 DB 에 붙는 첫 순간이다. 접속 정보가 틀렸으면 여기서 오류가 난다.
    with engine.connect() as connection:
        # DB_NAME() : 지금 접속한 데이터베이스 이름을 돌려주는 SQL Server 함수.
        # .scalar() : 결과가 한 칸일 때 그 값 하나만 꺼낸다.
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"[성공] SQLAlchemy 로 접속했습니다. 데이터베이스: {name}")
