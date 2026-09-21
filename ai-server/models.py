# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   검사 이력 표 inspection 의 설계를 Python 클래스 Inspection 으로 적는다.
#   검사 한 번 = 행 하나 = Inspection 객체 하나.
#   SSMS 에서 손으로 쳤던 CREATE TABLE 의 내용을 Python 으로 옮긴 것이라고 보면 된다.
#
#   ★ 여기서 "모델" 은 YOLO 모델이 아니다. DB 쪽에서 모델 = 표의 설계를 적은 클래스.
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   db.py (Base) ──▶ [현재 파일] ──▶ Alembic : 이 클래스를 보고 CREATE TABLE 을 만들어 실제 DB 에 표를 만든다
#                          └──────▶ main.py : 검사할 때마다 Inspection(...) 객체를 만들어 세션에 add → commit
#   앞: db.py 의 Base 가 있어야 한다.
#   뒤: 이 파일을 고친다고 DB 의 표가 바뀌지는 않는다. 표를 실제로 바꾸는 것은 Alembic 이다.
#
#   직접 실행하면 이 클래스에서 만들어질 CREATE TABLE 문을 찍어 본다. DB 에는 아무것도 하지 않는다 (ai-server 폴더에서):
#       .venv/Scripts/python models.py
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   표 설계 (2026-09-21 확정) :
#       id                                          INT, 기본 키, 자동 번호
#       created_at                                  DATETIME2, NOT NULL, 기본값 = 지금 시각
#       result                                      NVARCHAR(2), NOT NULL        'OK' / 'NG'
#       bolt_count / nut_count / washer_count       INT, NOT NULL                모델이 센 개수
#       bolt_expected / nut_expected / washer_expected  INT, NOT NULL            기대 개수
#       model_name                                  NVARCHAR(50), NOT NULL       판정한 YOLO 모델 이름. 예: 'exp03_s08overlap'
#     센 개수와 기대 개수를 둘 다 두는 이유: result 만 있으면 NG 가 "무엇이 몇 개 틀려서" 났는지 알 수 없다.
#     model_name 을 두는 이유: 재학습으로 모델을 바꾼 뒤, 어느 행이 어느 모델의 판정인지 구분하려고.
#     사진 경로 컬럼은 일부러 뺐다. 나중에 Alembic 두 번째 마이그레이션으로 추가한다.
#   컬럼 한 줄의 모양 (SQLAlchemy 2.0 문법) :
#       이름: Mapped[파이썬타입] = mapped_column(DB타입, 규칙들)
#       Mapped[int]   → "이 속성은 DB 컬럼과 짝지어져 있고 Python 에서는 int 다". 편집기가 타입 실수를 잡아 준다.
#       mapped_column → DB 쪽 타입과 규칙(NOT NULL, 기본 키, 기본값)을 적는 자리.
#   SQL ↔ SQLAlchemy 대응 :
#       INT            ↔ Integer
#       NVARCHAR(2)    ↔ Unicode(2)         (SQL Server 에 접속하면 SQLAlchemy 가 NVARCHAR 로 바꾼다)
#       DATETIME2      ↔ DATETIME2          (SQL Server 전용 타입이라 mssql 방언에서 가져온다)
#       NOT NULL       ↔ nullable=False
#       PRIMARY KEY    ↔ primary_key=True   (정수 기본 키는 SQL Server 에서 자동으로 IDENTITY 가 된다)
#       DEFAULT SYSDATETIME() ↔ server_default=func.sysdatetime()
# ─────────────────────────────────────────────────────────────────────────────

# datetime : Python 의 날짜·시각 타입. created_at 의 Python 쪽 타입 표시(Mapped[datetime])에 쓴다.
from datetime import datetime

# Integer, Unicode : DB 컬럼 타입.  func : SQL 함수를 Python 에서 부르는 통로. func.sysdatetime() → SQL 의 SYSDATETIME()
from sqlalchemy import Integer, Unicode, func

# DATETIME2 는 SQL Server 에만 있는 타입이라 공용(sqlalchemy)이 아니라 mssql 방언 모듈에서 가져온다.
from sqlalchemy.dialects.mssql import DATETIME2

# Mapped : 타입 표시용.  mapped_column : 컬럼 하나를 정의하는 함수.
from sqlalchemy.orm import Mapped, mapped_column

# 모든 모델의 부모. 이것을 상속해야 SQLAlchemy 와 Alembic 이 "표" 로 알아본다.
from db import Base


class Inspection(Base):
    """검사 이력 한 행. 표 이름은 inspection.

    입력(만들 때): Inspection(result="NG", bolt_count=4, nut_count=4, washer_count=0,
                              bolt_expected=3, nut_expected=5, washer_expected=0, model_name="exp03_s08overlap")
                   id 와 created_at 은 적지 않는다. DB 가 채운다.
    출력: 객체 하나. session.add(객체) → session.commit() 을 해야 DB 에 행이 생긴다.
    실패 시: NOT NULL 컬럼을 비우고 commit 하면 sqlalchemy.exc.IntegrityError.
             이 클래스를 만드는 순간이 아니라 commit 하는 순간에 난다 (DB 가 거절하는 것이므로).
    """

    # 실제 DB 에 생길 표 이름. 클래스 이름(Inspection)과 별개로 직접 정한다. SQL 관례대로 소문자.
    __tablename__ = "inspection"

    # 기본 키. 정수 + primary_key=True 이면 SQL Server 에서 IDENTITY(1,1) 이 자동으로 붙는다. 직접 값을 넣지 않는다.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 검사 시각. server_default 는 "DB 쪽 기본값" 이다 → CREATE TABLE 에 DEFAULT sysdatetime() 으로 들어간다.
    # Python 에서 datetime.now() 를 넣지 않고 DB 에 맡기는 이유: 시계가 하나(DB 서버)로 통일된다.
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysdatetime()
    )

    # 판정. 'OK' 또는 'NG' 두 글자라 Unicode(2). main.py 의 verdict 가 들어온다.
    result: Mapped[str] = mapped_column(Unicode(2), nullable=False)

    # 모델이 센 볼트 개수. main.py 의 counts["bolt"] 가 들어온다.
    bolt_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # 모델이 센 너트·와셔 개수. main.py 의 counts["nut"], counts["washer"] 가 들어온다.
    nut_count: Mapped[int] = mapped_column(Integer, nullable=False)
    washer_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # 기대 개수 셋. 요청에 담겨 온 값(main.py 의 expected)이 들어온다.
    # 센 개수와 나란히 저장해야 NG 가 "어느 부품이 몇 개 달라서" 났는지 나중에 SQL 로 집계할 수 있다.
    # 속성 이름이 곧 DB 컬럼 이름이 된다. 철자를 바꾸면 표의 컬럼 이름도 바뀐다.
    bolt_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    nut_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    washer_expected: Mapped[int] = mapped_column(Integer, nullable=False)

    # 판정한 YOLO 모델의 이름. 예: "exp03_s08overlap". 재학습으로 모델을 바꾼 뒤 어느 행이 어느 모델의 판정인지 구분한다.
    # 50 은 실험 이름(지금 가장 긴 것이 16자)에 여유를 둔 값이다. 넘는 글자를 넣으면 DB 가 거절한다.
    model_name: Mapped[str] = mapped_column(Unicode(50), nullable=False)


# 이 파일을 직접 실행했을 때만 돈다. 이 클래스에서 나올 CREATE TABLE 문을 찍어 볼 뿐, DB 에는 접속하지 않는다.
if __name__ == "__main__":
    # CreateTable : 모델의 표 정의를 CREATE TABLE 문으로 바꿔 주는 도구.
    from sqlalchemy.schema import CreateTable

    # engine.dialect : "SQL Server 방언" 정보만 빌린다. 그래야 NVARCHAR, IDENTITY 같은 SQL Server 문법으로 찍힌다.
    from db import engine

    # Inspection.__table__ : 위 클래스에서 SQLAlchemy 가 뽑아낸 표 정의 객체.
    # SSMS 에서 손으로 쳤던 CREATE TABLE practice (...) 와 나란히 놓고 비교해 본다.
    print(CreateTable(Inspection.__table__).compile(dialect=engine.dialect))
