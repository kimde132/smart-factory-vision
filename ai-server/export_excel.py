# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  export_excel.py — DB 의 검사 이력 표(inspection)를 Excel 파일 한 장으로 저장하는 스크립트     ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  "검사 결과는 MSSQL 에 저장하고 Excel 로 추출한다" 의 뒷부분. 현장에서 품질 담당자가 엑셀로 이력을 받아 보는 상황을 흉내 낸다.
# │
# │  WPF "검사" ──▶ FastAPI /inspect ──▶ inspection 표에 행 추가        (여기까지는 이미 됨)
# │                                           │
# │                                           └──▶ [현재 파일] ──▶ storage/inspection_YYYYMMDD_HHMMSS.xlsx
# │
# │  서버(uvicorn)나 WPF 와는 무관하게, 터미널에서 따로 한 번 실행하는 스크립트다.
# │  앞: db.py 의 engine (접속). .env 와 SQL Server 가 켜져 있어야 한다. 표에 행이 0개여도 빈 엑셀이 나온다.
# │  뒤: 없다. 파일을 만들고 끝난다. 시연 때는 WPF 로 검사 몇 번 → 이 스크립트 → 엑셀을 열어 보여 준다.
# │
# │  실행 (반드시 ai-server 폴더 안에서. db.py 가 같은 폴더의 check_db 를 import 하므로 다른 폴더에서는 못 찾는다):
# │      .venv/Scripts/python export_excel.py
# │
# │  실행 순서 (맨 아래 if __name__ == "__main__" 블록):
# │      load_inspections()  SQL 로 표 전체 읽기 → DataFrame
# │        → tidy()          머리글 한국어로, 시각을 초 단위 글자로
# │        → OUTPUT_DIR.mkdir 폴더 준비
# │        → save_excel()    .xlsx 로 쓰고 열 너비 맞추기
# │
# ├ 1. 이름은 세 종류 (C# 파일과 같은 구분) ────────────────────────────────────────────────────
# │
# │  ① 키워드 (Python 언어가 정한 것)  : from import def return with for if else in any as
# │  ② 라이브러리가 정한 이름 (import 로 가져온 것. 한 글자도 못 바꾼다)
# │       클래스·함수 : datetime Path DataFrame ExcelWriter get_column_letter read_sql to_excel rename strftime
# │                     astype map max mkdir resolve relative_to now enumerate len max any str int
# │       속성·접근자 : .dt .columns .sheets .column_dimensions .width .parent
# │  ③ 내가 지은 이름 : PROJECT_ROOT OUTPUT_DIR SHEET_NAME COLUMN_NAMES_KO load_inspections tidy save_excel
# │                     df sql writer sheet col_index col_name longest_value width path
# │
# │  Python 은 C# 과 달리 타입을 안 써도 되지만, 이 파일은 함수 머리에 -> pd.DataFrame 처럼 "타입 힌트" 를 적어 뒀다.
# │  강제는 아니고 읽는 사람과 편집기를 위한 표시다. C# 의  int n = 3  과 Python 의  n: int = 3  이 같은 뜻.
# │
# ├ 2. import 사전 — 어디서 무엇을 가져왔나 ──────────────────────────────────────────────────
# │
# │  from datetime import datetime        (Python 기본)  → datetime.now(), f"{…:%Y%m%d}"
# │  from pathlib import Path             (Python 기본)  → Path(__file__), / 로 경로 잇기, .mkdir()
# │  import pandas as pd                  (pip 설치)     → pd.read_sql, pd.ExcelWriter, DataFrame 의 .dt .rename .to_excel .astype .map
# │  from openpyxl.utils import get_column_letter (pip 설치) → 열 번호 → 열 글자
# │  from db import engine                (내 파일 db.py) → SQLAlchemy 접속 엔진
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────────
# │
# │  DataFrame   : pandas 의 표. 행·열이 있고 엑셀 시트와 1:1 로 대응한다. SQL 의 SELECT 결과를 그대로 담을 수 있다.
# │  read_sql    : SQL 을 보내고 결과를 DataFrame 으로 받는 pandas 함수. 접속은 SQLAlchemy 엔진에 맡긴다.
# │  to_excel    : DataFrame 을 .xlsx 로 쓰는 pandas 함수. 실제 파일 쓰기는 openpyxl 이 한다 (그래서 둘 다 설치돼 있다).
# │  ExcelWriter : 한 파일에 시트를 여러 장 쓰거나, 쓴 뒤 열 너비 같은 서식을 만질 때 쓰는 "열린 파일" 객체. with 로 열고 닫는다.
# │  .dt / .str  : DataFrame 의 한 열(Series)이 날짜 타입이면 .dt 로, 글자 타입이면 .str 로 그 타입 전용 함수를 쓴다.
# │
# │  자료 모양
# │    load_inspections() 결과 : 컬럼 10개(영어) × 행 N개. created_at 은 datetime64.
# │    tidy() 결과             : 컬럼 10개(한국어) × 행 N개. 검사 시각은 "2026-09-22 10:31:05" 문자열.
# │    엑셀                    : 시트 "검사 이력" 한 장. 1행 = 머리글, 2행부터 데이터.
# └────────────────────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import — 사전 열기 (C# 의 using)
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: from(①) datetime(② 모듈 이름) import(①) datetime(② 그 안의 클래스. 모듈과 이름이 같아 헷갈리기 쉽다)
# ▸ 왜: 파일 이름에 "지금 시각" 을 붙인다. 같은 날 여러 번 뽑아도 파일이 덮어써지지 않게.
from datetime import datetime

# ▸ 단어 분해: from pathlib(② 경로 모듈) import Path(② 경로 클래스)
# ▸ 왜: 경로를 문자열이 아니라 객체로 다룬다. / 로 이어 붙이고 .mkdir() 로 폴더를 만들 수 있다. 윈도우 \ 와 리눅스 / 를 알아서 처리한다.
# ▸ 다른 선택: os.path.join("a", "b") 같은 옛 방식도 있다. Path 가 읽기 쉽다.
from pathlib import Path

# ▸ 단어 분해: import pandas(② 패키지) as(①) pd(③ 짧은 별명. 관례라 거의 모두가 pd 로 쓴다)
# ▸ C# 의  using Window = System.Windows.Window;  와 같은 "별명 붙이기".
import pandas as pd

# ▸ 단어 분해: from openpyxl.utils(② openpyxl 패키지 안의 utils 모듈) import get_column_letter(② 함수)
# ▸ 왜: 열 번호(1, 2, 3 …) → 엑셀 열 글자(A, B, C …). 열 너비를 정할 때 글자가 필요하다.
from openpyxl.utils import get_column_letter

# ▸ 단어 분해: from db(③ 같은 폴더의 내 파일 db.py) import engine(③ db.py 가 만든 변수)
# ▸ 왜: main.py·Alembic 과 같은 접속 엔진을 쓴다. .env 를 여기서 또 읽지 않는다. 접속 정보가 바뀌면 db.py 한 곳만 고친다.
# ▸ 주의: 이 줄 때문에 ai-server 폴더에서 실행해야 한다. db.py 가 다시 check_db 를 import 하는데 Python 은 "지금 폴더" 에서 찾는다.
from db import engine


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  모듈 수준 상수 — 파일이 import 되는 순간 한 번 정해지고 모든 함수가 같이 쓴다 (C# 의 static readonly 필드 역할)
#  대문자 이름은 "바꾸지 않는 값" 이라는 Python 관습. 문법으로 막지는 않는다.
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: Path(② 클래스)(__file__(① 이 파일의 경로 문자열)).resolve(② 절대 경로로)().parent(② 폴더).parent(② 그 위 폴더)
# ▸ 뜻: ai-server/export_excel.py → ai-server → 프로젝트 최상위. 어디서 실행하든 같은 곳을 가리키게 절대 경로로 만든다.
# ▸ 왜 resolve: __file__ 이 상대 경로("export_excel.py")로 올 때가 있어 .parent 가 빈 경로가 된다. resolve 로 먼저 절대 경로로 만든다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ▸ 단어 분해: PROJECT_ROOT(③) /(② Path 가 정의한 "경로 잇기" 연산자) "storage"(글자)
# ▸ 뜻: 프로젝트최상위/storage. Path 객체는 / 로 이어 붙이면 새 Path 가 된다 (나누기가 아니다).
# ▸ 왜 storage: .gitignore 대상이라 결과 파일이 git 에 올라가지 않는다. CLAUDE.md 폴더 구조에서 "산출물" 자리.
OUTPUT_DIR = PROJECT_ROOT / "storage"

# ▸ 엑셀 아래쪽 시트 탭에 보일 이름. 두 군데(쓸 때, 서식 만질 때)서 같은 글자를 쓰므로 변수로 뺐다.
SHEET_NAME = "검사 이력"

# ▸ 단어 분해: COLUMN_NAMES_KO(③) = {(딕셔너리 시작) "영어"(키) :(→) "한국어"(값) , … }
# ▸ 뜻: DB 컬럼 이름(영어) → 엑셀 머리글(한국어) 대응표. 순서는 상관없다. 여기 없는 컬럼은 영어 그대로 남는다.
# ▸ 키는 models.py 의 Inspection 클래스 속성 이름과 글자까지 같아야 한다. 하나라도 다르면 그 열만 영어로 남는다(오류는 안 난다).
# ▸ "검출" 과 "기대" 로 나눈 이유: NG 가 "어느 부품이 몇 개 달라서" 났는지 엑셀에서 두 열을 나란히 보고 알 수 있게.
COLUMN_NAMES_KO = {
    "id": "번호",
    "created_at": "검사 시각",
    "result": "판정",
    "bolt_count": "볼트(검출)",
    "nut_count": "너트(검출)",
    "washer_count": "와셔(검출)",
    "bolt_expected": "볼트(기대)",
    "nut_expected": "너트(기대)",
    "washer_expected": "와셔(기대)",
    "model_name": "모델",
}


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  함수 셋 — 읽기 / 다듬기 / 쓰기. 맨 아래 __main__ 블록이 순서대로 부른다.
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: def(① 함수 정의) load_inspections(③)()(인자 없음) ->(타입 힌트: 돌려주는 것은) pd.DataFrame(②) :
def load_inspections() -> pd.DataFrame:
    """inspection 표 전체를 DataFrame 으로 읽는다.

    입력: 없음 (db.engine 으로 접속)
    출력: pd.DataFrame. 컬럼 = 표의 컬럼 10개 그대로(영어). 행 = 검사 횟수. 예: 행 2개면 shape (2, 10).
          created_at 은 pandas 가 datetime64 타입으로 읽어 온다.
    실패 시: SQL Server 가 꺼져 있거나 .env 가 틀리면 sqlalchemy.exc.OperationalError.
             표가 없으면(마이그레이션 전) ProgrammingError "개체 이름 'inspection'이(가) 잘못되었습니다".
    """
    # ▸ 단어 분해: sql(③) = "SELECT *(모든 컬럼) FROM inspection(표 이름) ORDER BY id(id 순 정렬)"
    # ▸ 뜻: SQLD 에서 본 그 SELECT. 정렬을 안 하면 DB 가 편한 순서로 주므로 "검사한 순서" 를 명시한다.
    # ▸ 왜 ORM(Inspection 클래스)이 아니라 SQL 글자인가: 저장은 ORM 으로, 집계·추출은 SQL 로 — 둘 다 쓸 수 있다는 걸 보여 주려고(9/22 메모).
    # ▸ 나중에 "NG 만" 이나 "오늘 것만" 이 필요해지면 WHERE 절을 여기에 붙인다. 지금은 전부.
    sql = "SELECT * FROM inspection ORDER BY id"

    # ▸ 단어 분해: return(①) pd.read_sql(② pandas 함수)(sql(보낼 SQL), engine(접속 수단))
    # ▸ 뜻: SQL 을 보내고 결과 표를 DataFrame 으로 받아 그대로 돌려준다.
    # ▸ 이 줄에서 실제로 DB 에 붙는다. db.py 의 ECHO_SQL 이 True 라 보낸 SQL 이 터미널에 같이 찍힌다.
    # ▸ 접속 자리에 SQLAlchemy 엔진을 그대로 넣을 수 있다. pandas 가 엔진에서 연결을 빌려 쓰고 돌려준다.
    return pd.read_sql(sql, engine)


# ▸ 단어 분해: def tidy(③)(df(③ 인자 이름): pd.DataFrame(타입 힌트)) -> pd.DataFrame :
def tidy(df: pd.DataFrame) -> pd.DataFrame:
    """엑셀에서 읽기 좋게 다듬는다. 시각을 초 단위 글자로, 머리글을 한국어로.

    입력: df — load_inspections() 가 돌려준 DataFrame (영어 컬럼, created_at 은 datetime64)
    출력: DataFrame. 컬럼 이름이 COLUMN_NAMES_KO 대로 바뀌고, 검사 시각이 "2026-09-22 10:31:05" 꼴 문자열.
          주의: 첫 줄이 넘겨받은 df 의 created_at 열을 제자리에서 바꾼다. 호출하는 쪽은 어차피 df = tidy(df) 로 다시 받으므로 문제없다.
    실패 시: created_at 이 이미 문자열이면(두 번 부르면) .dt 에서 AttributeError.
             COLUMN_NAMES_KO 에 표에 없는 컬럼 이름을 적어도 오류는 나지 않는다 (rename 은 없는 이름을 무시한다).
    """
    # ▸ 단어 분해: df["created_at"](② 그 열 하나 = Series) =(넣는다) df["created_at"].dt(② 날짜 전용 접근자).strftime(② 날짜→글자)("%Y-%m-%d %H:%M:%S"(형식))
    # ▸ 뜻: created_at 열의 모든 값을 "2026-09-22 10:31:05" 꼴 문자열로 바꿔 같은 열에 다시 넣는다.
    # ▸ 왜: DATETIME2 는 소수점 아래 7자리(0.0000001초)까지 있어 엑셀에서 "10:31:05.1234567" 로 보인다. 초까지면 충분하다.
    # ▸ .dt: 열이 datetime64 타입일 때만 쓸 수 있는 접근자. 글자 열이면 .str, 그 외엔 없다. 한 번 strftime 하면 글자 열이 되므로 두 번 부르면 죽는다.
    # ▸ 형식 글자: %Y 4자리 연도, %m 월, %d 일, %H 시(24), %M 분, %S 초. 파일 이름에 쓴 %Y%m%d_%H%M%S 와 같은 규칙.
    df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # ▸ 단어 분해: df(③) = df.rename(② DataFrame 의 함수: 이름 바꾸기)(columns(열 이름을)=COLUMN_NAMES_KO(이 대응표대로))
    # ▸ 뜻: 열 이름을 한국어로 바꾼 "새" DataFrame 을 만들어 df 에 다시 받는다.
    # ▸ 왜 다시 받나: rename 은 원본을 두고 새 표를 돌려준다. df.rename(…) 만 쓰고 안 받으면 결과가 버려져 아무것도 안 바뀐다.
    #   (pandas 함수 대부분이 이렇다. 위 strftime 줄이 = 로 다시 넣은 것도 같은 이유)
    # ▸ 다른 선택: columns= 대신 index= 를 주면 행 이름을 바꾼다.
    df = df.rename(columns=COLUMN_NAMES_KO)

    return df


# ▸ 단어 분해: def save_excel(③)(df: pd.DataFrame, path: Path) -> None(② 돌려주는 것 없음. C# 의 void) :
def save_excel(df: pd.DataFrame, path: Path) -> None:
    """DataFrame 을 .xlsx 로 저장하고, 열 너비를 내용에 맞춘다.

    입력: df — tidy() 가 돌려준 DataFrame.  path — 저장할 파일 경로. 예: storage/inspection_20260928_143000.xlsx
    출력: 없음. path 에 파일이 생긴다. 이미 있으면 덮어쓴다.
    실패 시: 같은 이름의 파일이 엑셀에서 열려 있으면 PermissionError (윈도우가 열린 파일을 잠근다).
             path 의 폴더가 없으면 FileNotFoundError — 그래서 호출하는 쪽에서 폴더를 먼저 만든다.
    """
    # ▸ 단어 분해: with(① 블록 끝나면 정리) pd.ExcelWriter(② 클래스)(path(어디에), engine(어떤 라이브러리로)="openpyxl") as(①) writer(③) :
    # ▸ 뜻: 파일을 "열어 둔" 객체 writer 를 만든다. with 블록이 끝날 때 실제로 디스크에 쓰고 닫는다.
    # ▸ C# 의  using var form = …  와 같은 것. 안 닫으면 파일이 0바이트로 남거나 잠긴다.
    # ▸ engine="openpyxl": .xlsx 면 pandas 가 알아서 openpyxl 을 고르지만 명시해 둔다. (여기서 engine 은 db.engine 과 이름만 같고 무관하다)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # ▸ 단어 분해: df.to_excel(② 함수)(writer(열린 파일에), sheet_name(시트 이름)=SHEET_NAME, index(행 번호를 쓸까)=False)
        # ▸ 뜻: 이 시트에 표를 쓴다. 1행 = 머리글, 2행부터 데이터.
        # ▸ 왜 index=False: DataFrame 은 행마다 번호(0, 1, 2 …)를 갖는데 그걸 첫 열로 쓰면 id 컬럼과 겹쳐 열이 하나 늘어난다.
        df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

        # ▸ 단어 분해: sheet(③) = writer.sheets(② 딕셔너리: 이름→시트)[SHEET_NAME]
        # ▸ 뜻: 방금 쓴 시트를 openpyxl 의 워크시트 객체로 꺼낸다. 여기서부터는 pandas 가 아니라 openpyxl 의 세계.
        # ▸ 왜: 열 너비 같은 서식은 pandas 에 없다. openpyxl 이 만든 시트 객체를 직접 만져야 한다.
        sheet = writer.sheets[SHEET_NAME]

        # ▸ 단어 분해: for(①) col_index(③), col_name(③) in(①) enumerate(② 번호 붙여 돌기)(df.columns(② 열 이름 목록), start(시작 번호)=1) :
        # ▸ 뜻: 열 이름과 1부터 시작하는 번호를 짝지어 한 열씩 돈다. 엑셀 열은 1(A)부터라 start=1.
        # ▸ 왜 이 반복이 필요한가: 안 하면 모든 열이 8.43(엑셀 기본 너비)이라 "볼트(검출)" 이나 긴 시각이 잘려 보인다.
        for col_index, col_name in enumerate(df.columns, start=1):
            # ▸ 단어 분해: longest_value(③) = ( df[col_name](이 열).astype(② 타입 바꾸기)(str).map(② 값마다 함수 적용)(len).max(② 최댓값)()  if(①) len(df) > 0  else(①) 0 )
            # ▸ 뜻: 그 열의 모든 값을 글자로 바꿔 길이를 재고 그중 최댓값. 단 행이 0개면 0.
            # ▸ 왜 astype(str): 숫자 열은 len 을 못 잰다. 글자로 바꿔야 "123" → 3 이 된다.
            # ▸ 왜 if…else: 행이 0개면 .max() 가 NaN(숫자 아님)을 돌려주고, 아래 max(…) 에서 비교가 이상해진다. 미리 0 으로.
            # ▸ 괄호 ( … ) 로 감싼 건 줄이 길어서 두 줄로 나누려고. Python 은 괄호 안에서만 줄바꿈이 자유롭다.
            longest_value = (
                df[col_name].astype(str).map(len).max() if len(df) > 0 else 0
            )
            # ▸ 단어 분해: width(③) = max(② 큰 쪽)(len(str(col_name))(머리글 길이), longest_value(값 길이)) + 2(여유)
            # ▸ 뜻: 머리글과 가장 긴 값 중 긴 쪽 + 2 를 너비로.
            width = max(len(str(col_name)), longest_value) + 2
            # ▸ 단어 분해: if any(② 하나라도 참이면)( "가" <= ch <= "힣"(한글 범위 안인가) for ch in str(col_name)(머리글 글자 하나씩) ) :
            # ▸ 뜻: 머리글에 한글이 한 글자라도 있으면 너비를 1.7배로.
            # ▸ 왜: 엑셀 너비 단위는 "영문 한 글자" 기준이라 한글은 실제보다 좁게 잡힌다. 1.7 은 눈으로 맞춘 값이지 정확한 상수가 아니다.
            # ▸ "가" ~ "힣": 유니코드에서 완성형 한글이 이 사이에 연속으로 있다. 글자 비교는 유니코드 번호 비교다.
            if any("가" <= ch <= "힣" for ch in str(col_name)):
                width = int(width * 1.7)
            # ▸ 단어 분해: sheet.column_dimensions(② 열 설정 딕셔너리)[get_column_letter(② 번호→글자)(col_index)].width(② 속성) = width
            # ▸ 뜻: 그 열(A, B, C …)의 너비를 정한다.
            # ▸ 왜 글자로: openpyxl 은 열을 번호가 아니라 "A", "B" 글자로 찾는다. 그래서 get_column_letter 가 필요하다.
            sheet.column_dimensions[get_column_letter(col_index)].width = width


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  시작점 — 이 파일을 직접 실행했을 때만 도는 부분. 다른 파일이 import 하면 돌지 않는다.
#  __name__ 은 Python 이 정한 변수. 직접 실행하면 "__main__", import 되면 파일 이름("export_excel")이 들어 있다.
#  (C# 의 Main() 에 해당. WPF 는 App.g.cs 가 대신 만들어 줬지만 Python 은 이 관용구로 직접 표시한다)
# ═══════════════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 1. 읽기 — DB → DataFrame (영어 컬럼)
    df = load_inspections()

    # 2. 다듬기 — 시각 글자로, 머리글 한국어로. 새 표를 df 에 다시 받는다.
    df = tidy(df)

    # ▸ 단어 분해: OUTPUT_DIR.mkdir(② 폴더 만들기)(exist_ok(이미 있어도 되나)=True)
    # ▸ 3. 폴더 준비. exist_ok=True 가 없으면 두 번째 실행부터 "이미 있음" 오류(FileExistsError).
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ▸ 단어 분해: path(③) = OUTPUT_DIR / f"inspection_{datetime.now()(② 지금 시각):%Y%m%d_%H%M%S(형식)}.xlsx"
    # ▸ 4. 파일 이름. f-string 안의  {값:형식}  은 "이 값을 이 형식으로". 20260928_143000 꼴이 된다.
    # ▸ 왜 콜론(:)을 안 넣나: 윈도우 파일 이름에 : 는 금지 글자다. 그래서 시:분:초 대신 붙여 쓴다.
    path = OUTPUT_DIR / f"inspection_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

    # 5. 쓰기 — DataFrame → .xlsx
    save_excel(df, path)

    # ▸ 단어 분해: print(f"[완료] {len(df)(행 수)}행 → {path.relative_to(② 이 기준으로 상대 경로)(PROJECT_ROOT)}")
    # ▸ 뜻: "[완료] 5행 → storage\inspection_20260928_143000.xlsx" 처럼 찍는다. 절대 경로는 길어서 프로젝트 기준으로 줄였다.
    print(f"[완료] {len(df)}행 → {path.relative_to(PROJECT_ROOT)}")
