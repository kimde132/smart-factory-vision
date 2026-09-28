# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  models.py — 검사 이력 표 inspection 의 설계를 Python 클래스 Inspection 으로 적는다              ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 읽히나 ─────────────────────────────────────────────────────────
# │
# │  검사 한 번 = 행 하나 = Inspection 객체 하나.
# │  SSMS 에서 손으로 쳤던 CREATE TABLE 의 내용을 Python 으로 옮긴 것이라고 보면 된다.
# │  ★ 여기서 "모델" 은 YOLO 모델이 아니다. DB 쪽에서 모델 = 표의 설계를 적은 클래스.
# │
# │  db.py (Base) ──▶ [현재 파일] ──▶ Alembic : 이 클래스를 보고 CREATE TABLE 을 만들어 실제 DB 에 표를 만든다
# │                         └──────▶ main.py : 검사할 때마다 Inspection(...) 객체를 만들어 세션에 add → commit
# │  앞: db.py 의 Base 가 있어야 한다.
# │  뒤: 이 파일을 고친다고 DB 의 표가 바뀌지는 않는다. 표를 실제로 바꾸는 것은 Alembic (revision --autogenerate → upgrade head).
# │
# │  직접 실행하면 이 클래스에서 만들어질 CREATE TABLE 문을 찍어 본다. DB 에는 아무것도 하지 않는다 (ai-server 폴더에서):
# │      .venv/Scripts/python models.py
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : from import class if
# │  ② 라이브러리가 정한 이름
# │       datetime                       ← datetime (Python 기본)
# │       Integer Unicode func           ← sqlalchemy
# │       DATETIME2                      ← sqlalchemy.dialects.mssql
# │       Mapped mapped_column           ← sqlalchemy.orm
# │       __tablename__ __table__        ← SQLAlchemy 가 정한 특수 속성 이름 (밑줄 두 개 = 약속된 이름)
# │       CreateTable                    ← sqlalchemy.schema (아래 시험 블록에서만)
# │  ③ 내가 지은 이름
# │       Inspection(클래스), 컬럼 10개: id created_at result bolt_count nut_count washer_count
# │                                     bolt_expected nut_expected washer_expected model_name
# │       ★ 컬럼 속성 이름이 곧 DB 컬럼 이름이고, main.py 의 Inspection(bolt_count=…) 키워드 이름이고, export_excel.py 의 COLUMN_NAMES_KO 키다.
# │         하나를 바꾸면 세 곳이 같이 바뀌어야 한다.
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  from datetime import datetime                    (Python 기본) → created_at 의 Python 쪽 타입 표시
# │  from sqlalchemy import Integer, Unicode, func    (pip) → DB 컬럼 타입 둘, SQL 함수 통로
# │  from sqlalchemy.dialects.mssql import DATETIME2  (pip) → SQL Server 전용 타입
# │  from sqlalchemy.orm import Mapped, mapped_column (pip) → 컬럼 선언 문법
# │  from db import Base                             (내 파일) → 모델의 부모
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  표 설계 (2026-09-21 확정) :
# │      id                                          INT, 기본 키, 자동 번호
# │      created_at                                  DATETIME2, NOT NULL, 기본값 = 지금 시각
# │      result                                      NVARCHAR(2), NOT NULL        'OK' / 'NG'
# │      bolt_count / nut_count / washer_count       INT, NOT NULL                모델이 센 개수
# │      bolt_expected / nut_expected / washer_expected  INT, NOT NULL            기대 개수
# │      model_name                                  NVARCHAR(50), NOT NULL       판정한 YOLO 모델 이름. 예: 'exp03_s08overlap'
# │    센 개수와 기대 개수를 둘 다 두는 이유: result 만 있으면 NG 가 "무엇이 몇 개 틀려서" 났는지 알 수 없다.
# │    model_name 을 두는 이유: 재학습으로 모델을 바꾼 뒤, 어느 행이 어느 모델의 판정인지 구분하려고.
# │    사진 경로 컬럼은 일부러 뺐다. 나중에 Alembic 두 번째 마이그레이션으로 추가한다 (9/28 오독 사례가 그 필요성의 증거).
# │
# │  컬럼 한 줄의 모양 (SQLAlchemy 2.0 문법) :
# │      이름: Mapped[파이썬타입] = mapped_column(DB타입, 규칙들)
# │      Mapped[int]   → "이 속성은 DB 컬럼과 짝지어져 있고 Python 에서는 int 다". 편집기가 타입 실수를 잡아 준다. 대괄호 안이 타입 = 제네릭 문법.
# │      mapped_column → DB 쪽 타입과 규칙(NOT NULL, 기본 키, 기본값)을 적는 자리.
# │
# │  SQL ↔ SQLAlchemy 대응 :
# │      INT            ↔ Integer
# │      NVARCHAR(2)    ↔ Unicode(2)         (SQL Server 에 접속하면 SQLAlchemy 가 NVARCHAR 로 바꾼다)
# │      DATETIME2      ↔ DATETIME2          (SQL Server 전용 타입이라 mssql 방언에서 가져온다)
# │      NOT NULL       ↔ nullable=False
# │      PRIMARY KEY    ↔ primary_key=True   (정수 기본 키는 SQL Server 에서 자동으로 IDENTITY 가 된다)
# │      DEFAULT SYSDATETIME() ↔ server_default=func.sysdatetime()
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ datetime(② 클래스): Python 의 날짜·시각 타입. 아래 Mapped[datetime] 타입 표시에만 쓴다. 실제 값은 DB 가 채운다.
from datetime import datetime

# ▸ 단어 분해: from sqlalchemy import Integer(② INT 타입), Unicode(② NVARCHAR 타입), func(② SQL 함수를 Python 에서 부르는 통로)
# ▸ func.sysdatetime() 이라고 쓰면 SQL 의 SYSDATETIME() 이 된다. func.count(), func.max() 도 같은 방식.
from sqlalchemy import Integer, Unicode, func

# ▸ 단어 분해: from sqlalchemy.dialects.mssql(② SQL Server 방언 모듈) import DATETIME2(② 타입)
# ▸ 왜 여기서: DATETIME2 는 SQL Server 에만 있는 타입이라 공용(sqlalchemy)이 아니라 mssql 방언 모듈에서 가져온다.
# ▸ 다른 선택: 공용 DateTime 을 쓰면 SQL Server 에서 DATETIME(정밀도 3ms)이 된다. DATETIME2 가 정밀도가 높고 MS 권장.
from sqlalchemy.dialects.mssql import DATETIME2

# ▸ 단어 분해: from sqlalchemy.orm import Mapped(② 타입 표시용), mapped_column(② 컬럼 하나를 정의하는 함수)
from sqlalchemy.orm import Mapped, mapped_column

# ▸ Base(③ db.py): 모든 모델의 부모. 이것을 상속해야 SQLAlchemy 와 Alembic 이 "표" 로 알아본다.
from db import Base


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  모델 클래스 — 표 하나 = 클래스 하나
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: class Inspection(③)(Base(③ 부모)):
class Inspection(Base):
    """검사 이력 한 행. 표 이름은 inspection.

    입력(만들 때): Inspection(result="NG", bolt_count=4, nut_count=4, washer_count=0,
                              bolt_expected=3, nut_expected=5, washer_expected=0, model_name="exp03_s08overlap")
                   id 와 created_at 은 적지 않는다. DB 가 채운다.
    출력: 객체 하나. session.add(객체) → session.commit() 을 해야 DB 에 행이 생긴다.
    실패 시: NOT NULL 컬럼을 비우고 commit 하면 sqlalchemy.exc.IntegrityError.
             이 클래스를 만드는 순간이 아니라 commit 하는 순간에 난다 (DB 가 거절하는 것이므로).
    """

    # ▸ 단어 분해: __tablename__(② SQLAlchemy 가 정한 특수 이름) = "inspection"(③ 실제 표 이름)
    # ▸ 뜻: 실제 DB 에 생길 표 이름. 클래스 이름(Inspection)과 별개로 직접 정한다. SQL 관례대로 소문자.
    # ▸ 다른 선택: 이 줄을 빼면 SQLAlchemy 가 오류를 낸다(표 이름은 필수).
    __tablename__ = "inspection"

    # ▸ 단어 분해: id(③): Mapped[int](② "int 컬럼") = mapped_column(Integer(② INT), primary_key=True(② 기본 키))
    # ▸ 뜻: 기본 키. 정수 + primary_key=True 이면 SQL Server 에서 IDENTITY(1,1) 이 자동으로 붙는다. 직접 값을 넣지 않는다.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ▸ 단어 분해: created_at: Mapped[datetime] = mapped_column( DATETIME2, nullable=False(NOT NULL), server_default=func.sysdatetime()(DB 쪽 기본값) )
    # ▸ 뜻: 검사 시각. server_default 는 "DB 쪽 기본값" 이다 → CREATE TABLE 에 DEFAULT sysdatetime() 으로 들어간다.
    # ▸ 왜 Python 에서 datetime.now() 를 넣지 않나: 시계가 하나(DB 서버)로 통일된다. 여러 클라이언트가 붙어도 시각이 뒤섞이지 않는다.
    # ▸ 다른 선택: default=datetime.now 는 "Python 쪽 기본값" — SQLAlchemy 가 INSERT 할 때 값을 만들어 보낸다. 시계가 클라이언트마다 달라진다.
    # ▸ 괄호 안 줄바꿈은 포매터가 넣은 것. 한 줄로 써도 같다.
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysdatetime()
    )

    # ▸ 단어 분해: result: Mapped[str] = mapped_column(Unicode(2)(② NVARCHAR(2)), nullable=False)
    # ▸ 뜻: 판정. 'OK' 또는 'NG' 두 글자라 Unicode(2). main.py 의 verdict 가 들어온다.
    # ▸ 다른 선택: 세 글자 이상을 넣으면 DB 가 거절한다(String truncation). 판정 종류가 늘면 길이도 늘려야 한다 → 마이그레이션.
    result: Mapped[str] = mapped_column(Unicode(2), nullable=False)

    # ▸ 모델이 센 볼트 개수. main.py 의 counts["bolt"] 가 들어온다.
    bolt_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # ▸ 모델이 센 너트·와셔 개수. main.py 의 counts["nut"], counts["washer"] 가 들어온다.
    nut_count: Mapped[int] = mapped_column(Integer, nullable=False)
    washer_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # ▸ 기대 개수 셋. 요청에 담겨 온 값(main.py 의 expected)이 들어온다.
    # ▸ 센 개수와 나란히 저장해야 NG 가 "어느 부품이 몇 개 달라서" 났는지 나중에 SQL 로 집계할 수 있다.
    # ▸ 속성 이름이 곧 DB 컬럼 이름이 된다. 철자를 바꾸면 표의 컬럼 이름도 바뀐다(→ 마이그레이션 필요).
    bolt_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    nut_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    washer_expected: Mapped[int] = mapped_column(Integer, nullable=False)

    # ▸ 단어 분해: model_name: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    # ▸ 뜻: 판정한 YOLO 모델의 이름. 예: "exp03_s08overlap". main.py 의 MODEL_NAME 이 들어온다.
    # ▸ 50 은 실험 이름(지금 가장 긴 것이 16자)에 여유를 둔 값이다. 넘는 글자를 넣으면 DB 가 거절한다.
    model_name: Mapped[str] = mapped_column(Unicode(50), nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  시험 — 이 파일을 직접 실행했을 때만. 이 클래스에서 나올 CREATE TABLE 문을 찍어 볼 뿐, DB 에는 접속하지 않는다.
# ═══════════════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ▸ CreateTable(② 클래스): 모델의 표 정의를 CREATE TABLE 문으로 바꿔 주는 도구.
    # ▸ 함수 안에서 import 하는 이유: 이 블록에서만 쓰는 것이라 파일 위에 올리면 main.py 가 import 할 때도 불필요하게 읽힌다.
    from sqlalchemy.schema import CreateTable

    # ▸ engine.dialect(② 방언 정보)만 빌린다. 그래야 NVARCHAR, IDENTITY 같은 SQL Server 문법으로 찍힌다. 접속은 안 한다.
    from db import engine

    # ▸ 단어 분해: print( CreateTable(Inspection.__table__(② 클래스에서 뽑아낸 표 정의 객체)).compile(② 글자로 변환)(dialect=engine.dialect) )
    # ▸ SSMS 에서 손으로 쳤던 CREATE TABLE practice (...) 와 나란히 놓고 비교해 본다.
    print(CreateTable(Inspection.__table__).compile(dialect=engine.dialect))
