"""
check_db.py — SQL Server 접속 확인 스크립트 (+ db.py 가 빌려 쓰는 .env 읽기·연결 문자열 조립 함수)

┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
│
│  .env 에 적힌 접속 정보로 SQL Server 에 실제로 붙어보고, 성공하면 서버 버전을 출력한다. 실패하면 원인을 한국어로 알려준다.
│
│  두 가지 역할
│    (1) 사람이 손으로 실행하는 점검 도구 — 환경을 새로 구축했을 때 "DB 가 붙는가" 를 가장 먼저 확인.
│        실행: ai-server 폴더에서  .venv/Scripts/python check_db.py
│    (2) db.py 가 load_config() 와 build_connection_string() 을 import 해서 쓴다. 그래서 이 파일은 지워도 되는 도구가 아니라 서버의 일부다.
│
│  실행 순서 (직접 실행할 때): main() → 드라이버 목록 출력 → load_config() → build_connection_string() → pyodbc.connect() → 버전 조회 → 출력
│
├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
│
│  ① Python 키워드      : import from def return if not for in with try except as
│  ② 라이브러리가 정한 이름
│       os.environ.get                         ← os (Python 기본)
│       sys.exit                               ← sys (Python 기본)
│       Path                                   ← pathlib (Python 기본)
│       pyodbc.connect pyodbc.drivers pyodbc.Error  ← pyodbc (pip)
│       load_dotenv                            ← dotenv (pip: python-dotenv)
│       .cursor() .execute() .fetchone()       ← pyodbc 연결·커서 객체의 메서드
│       .exists() .parent                      ← Path 의 메서드·속성
│  ③ 내가 지은 이름
│       ENV_PATH load_config build_connection_string explain_error main
│       config missing message connection cursor version current_db current_user connection_string driver_name error
│       .env 항목 이름: MSSQL_SERVER MSSQL_PORT MSSQL_DATABASE MSSQL_USER MSSQL_PASSWORD MSSQL_DRIVER MSSQL_ENCRYPT MSSQL_TRUST_SERVER_CERTIFICATE
│
├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
│
│  import os                        (Python 기본) → 환경변수 읽기
│  import sys                       (Python 기본) → 실패 종료
│  from pathlib import Path         (Python 기본) → .env 경로
│  import pyodbc                    (pip)         → ODBC 로 DB 접속
│  from dotenv import load_dotenv   (pip)         → .env → 환경변수
│
├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
│
│  ODBC          : 프로그램이 여러 종류의 DB 에 같은 방식으로 접속하게 해주는 표준 규격.
│                  파이썬(pyodbc) 과 SQL Server 사이에 "ODBC Driver 18" 이라는 번역기가 낀다.
│  연결 문자열   : 어디에, 누구로, 어떻게 붙을지를 "키=값;키=값;" 형태로 이어 붙인 한 줄짜리 문자열.
│  환경변수      : 운영체제가 프로그램에 넘겨주는 이름=값 쌍. .env 파일은 그것을 파일에 적어 둔 것이고, load_dotenv 가 읽어 환경변수로 올린다.
│                  비밀번호를 코드에 안 적고 .env 에 두는 이유 = .env 는 .gitignore 대상이라 git 에 안 올라간다.
│  종료 코드     : 프로그램이 끝나며 남기는 숫자. 0 = 성공, 그 외 = 실패. sys.exit(1) 이 그것.
│
│  자료 모양
│    config (dict[str, str]) : {"server": "localhost", "port": "1433", "database": "smart_factory_vision", "user": "…", "password": "…", "driver": "ODBC Driver 18 for SQL Server", "encrypt": "yes", "trust": "yes"}
│    연결 문자열 (str)       : "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=…;UID=…;PWD=…;Encrypt=yes;TrustServerCertificate=yes;"
└────────────────────────────────────────────────────────────────────────────────────────
"""

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  import
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ os(② 운영체제 모듈): 환경변수(os.environ)를 읽기 위해.
import os

# ▸ sys(② 인터프리터 모듈): 스크립트를 실패 상태로 끝낼 때 sys.exit(1).
import sys

# ▸ Path(② 경로 클래스): 파일 경로를 객체로. 운영체제마다 다른 구분자(\ 와 /)를 알아서 처리한다.
from pathlib import Path

# ▸ pyodbc(② 패키지): 파이썬에서 ODBC 드라이버를 통해 DB 에 접속하는 라이브러리. 이것이 있어야 SQL Server 에 붙을 수 있다.
import pyodbc

# ▸ 단어 분해: from dotenv(② 패키지 이름은 python-dotenv, import 이름은 dotenv) import load_dotenv(② 함수)
# ▸ 뜻: .env 파일을 읽어서 os.environ 에 올려준다. 접속 정보를 코드에 하드코딩하지 않기 위한 것.
from dotenv import load_dotenv


# ▸ 단어 분해: ENV_PATH(③) = Path(__file__(① 이 파일 경로)).parent(② 들어 있는 폴더 = ai-server) / ".env"
# ▸ 뜻: ai-server/.env 의 경로. 어느 위치에서 실행하든 항상 같은 .env 를 찾는다.
# ▸ 다른 선택: Path(".env") 라고 쓰면 "지금 터미널이 있는 폴더" 의 .env 라서 최상위에서 실행하면 못 찾는다.
ENV_PATH = Path(__file__).parent / ".env"


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  함수 넷 — 설정 읽기 / 문자열 조립 / 오류 해설 / 전체 흐름
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: def load_config(③)() -> dict[str, str](타입 힌트: 키도 값도 글자인 딕셔너리):
def load_config() -> dict[str, str]:
    """
    .env 파일을 읽어 접속에 필요한 값들을 꺼내온다.

    입력: 없음 (ENV_PATH 위치의 .env 파일을 읽는다)
    출력: dict. 예) {"server": "localhost", "port": "1433", "database": "smart_factory", ...}
    실패 시: .env 파일이 없거나 필수 항목이 비어 있으면 SystemExit 로 종료한다.
    """
    # ▸ 단어 분해: if not(① 아니면) ENV_PATH.exists(② 파일이 있나)():
    # ▸ 왜 먼저 확인: 없는 채로 진행하면 "접속 실패" 라는 엉뚱한 메시지가 나와서 원인을 찾기 어려워진다.
    if not ENV_PATH.exists():
        print(f"[실패] .env 파일이 없습니다: {ENV_PATH}")
        print("       .env.example 을 같은 폴더에 .env 로 복사하고 값을 채우세요.")
        # ▸ sys.exit(1): 종료 코드 1(실패)로 프로그램을 끝낸다. 예외 SystemExit 를 던지는 것이라 db.py 가 import 했을 때도 거기서 멈춘다.
        sys.exit(1)

    # ▸ 단어 분해: load_dotenv(②)(ENV_PATH(어느 파일), override=True(② 이미 있는 환경변수도 덮어써라))
    # ▸ 뜻: .env 의 내용을 os.environ 에 넣는다.
    # ▸ 왜 override: 안 그러면 예전에 설정해둔 시스템 환경변수 때문에 헷갈리는 일이 생긴다. .env 가 항상 이긴다.
    load_dotenv(ENV_PATH, override=True)

    # ▸ 단어 분해: config(③) = { "server"(③ 우리 키): os.environ.get(② 환경변수 꺼내기)("MSSQL_SERVER"(③ .env 항목 이름), ""(없을 때 기본값)), … }
    # ▸ 뜻: .env 항목 8개를 우리가 정한 짧은 키로 옮겨 담는다. 두 번째 인자는 값이 없을 때 쓸 기본값.
    # ▸ 기본값이 있는 것(port 1433, driver, encrypt yes, trust yes)은 .env 에 안 적어도 된다. 없는 것(server, database, user, password)은 아래에서 걸러낸다.
    # ▸ 다른 선택: os.environ["MSSQL_SERVER"] 로 꺼내면 없을 때 KeyError 로 죽는다. .get 은 기본값을 준다.
    config = {
        "server": os.environ.get("MSSQL_SERVER", ""),
        "port": os.environ.get("MSSQL_PORT", "1433"),
        "database": os.environ.get("MSSQL_DATABASE", ""),
        "user": os.environ.get("MSSQL_USER", ""),
        "password": os.environ.get("MSSQL_PASSWORD", ""),
        "driver": os.environ.get("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server"),
        "encrypt": os.environ.get("MSSQL_ENCRYPT", "yes"),
        "trust": os.environ.get("MSSQL_TRUST_SERVER_CERTIFICATE", "yes"),
    }

    # ▸ 단어 분해: missing(③) = [ k(③) for(①) k in(①) ("server", "database", "user", "password")(튜플) if(①) not config[k](값이 비었으면) ]
    # ▸ 뜻: 리스트 컴프리헨션 — [식 for 변수 in 반복대상 if 조건]. 반복문을 한 줄로 써서 새 리스트를 만드는 문법.
    #   "네 키 중에서 config 값이 빈 것들의 이름 목록". 예: ["password"].
    # ▸ 왜: 비어 있으면 접속이 불가능한 항목들을 미리 걸러낸다.
    missing = [k for k in ("server", "database", "user", "password") if not config[k]]
    # ▸ if missing: 빈 리스트는 False, 하나라도 있으면 True (Python 의 진릿값 규칙).
    if missing:
        # ▸ ", ".join(missing)(② 리스트를 ", " 로 이어 한 글자로): ["server", "user"] → "server, user"
        print(f"[실패] .env 에서 다음 항목이 비어 있습니다: {', '.join(missing)}")
        sys.exit(1)

    return config


# ▸ 단어 분해: def build_connection_string(③)(config(③): dict[str, str]) -> str:
def build_connection_string(config: dict[str, str]) -> str:
    """
    접속 정보를 ODBC 연결 문자열 한 줄로 조립한다.

    입력: load_config() 가 돌려준 dict
    출력: str. 예) "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;..."
    실패 시: 예외를 던지지 않는다. 값이 틀렸는지는 실제 접속 시점에 드러난다.
    """
    # ▸ 단어 분해: return ( f"…" f"…" … )  — 괄호 안에 f-string 을 여러 줄 나란히 두면 Python 이 하나로 이어 붙인다(암묵적 문자열 결합).
    # ▸ f"DRIVER={{{config['driver']}}};" : f-string 안에서 중괄호 자체를 쓰려면 {{ }} 로 두 번. 그래서 {{ + {config['driver']} + }} = "{ODBC Driver 18 …}".
    # ▸ 왜 DRIVER 를 중괄호로 감싸나: 드라이버 이름에 공백이 들어 있어서, 감싸지 않으면 ODBC 가 이름을 잘라 읽는다.
    # ▸ SERVER=서버,포트 : 서버와 포트를 쉼표로 붙이는 것은 ODBC 의 표기 규칙이다(콜론이 아니다). SSMS 연결 창의 "localhost,1433" 과 같다.
    # ▸ Encrypt / TrustServerCertificate : ODBC Driver 18 부터 Encrypt 기본값이 yes 로 바뀌었다.
    #   로컬 SQL Server 는 자체 서명 인증서를 쓰므로 신뢰할 수 없다고 판단되어 거부된다.
    #   그래서 개발 환경에서는 TrustServerCertificate=yes 로 "이 인증서는 믿는다" 고 알려준다. 운영 서버라면 제대로 된 인증서를 쓰고 이 값을 no 로.
    return (
        f"DRIVER={{{config['driver']}}};"
        f"SERVER={config['server']},{config['port']};"
        f"DATABASE={config['database']};"
        f"UID={config['user']};"
        f"PWD={config['password']};"
        f"Encrypt={config['encrypt']};"
        f"TrustServerCertificate={config['trust']};"
    )


# ▸ 단어 분해: def explain_error(③)(error(③): pyodbc.Error(② 타입)) -> str:
def explain_error(error: pyodbc.Error) -> str:
    """
    pyodbc 가 던진 오류를 보고 원인을 한국어로 설명한다.

    입력: pyodbc.Error 예외 객체
    출력: str. 사람이 읽을 수 있는 원인 설명과 다음에 할 일
    실패 시: 아는 패턴이 없으면 "원인 미상" 안내를 돌려준다.
    """
    # ▸ str(error): 예외 객체를 문자열로 바꾸면 드라이버가 준 원본 메시지가 들어 있다. 예: "('08001', '[08001] [Microsoft][ODBC Driver 18 …')"
    message = str(error)

    # ▸ 자주 나오는 실패 유형을 순서대로 확인한다. "IM002" in message : 부분 문자열이 들어 있나 (in 연산자).
    # ▸ 순서가 중요하다: 위쪽일수록 실제로 자주 먼저 터지는 것이다. 8월 환경 구축 때 4번 연속 막힌 순서(setup-log.md 3-2).
    # ▸ 코드 뜻: IM002 = 드라이버 없음 / SSL Provider·certificate = 인증서 / 18456 = 로그인 거부 / 4060 = DB 없음 / 08001 = 서버에 못 닿음
    if "IM002" in message:
        # ▸ 괄호 안 문자열 여러 줄 = 암묵적 결합. \n 은 줄바꿈.
        return (
            "ODBC 드라이버를 찾지 못했습니다.\n"
            "  → .env 의 MSSQL_DRIVER 이름이 실제 설치된 이름과 글자까지 같은지 확인하세요.\n"
            "  → 설치된 드라이버 목록은 이 스크립트가 위에 출력해 줍니다."
        )
    # ▸ message.lower()(② 소문자로): "Certificate" 든 "certificate" 든 잡으려고.
    if "SSL Provider" in message or "certificate" in message.lower():
        return (
            "인증서 신뢰 오류입니다.\n"
            "  → .env 의 MSSQL_TRUST_SERVER_CERTIFICATE 를 yes 로 두세요.\n"
            "     ODBC Driver 18 은 암호화가 기본이라 자체 서명 인증서를 거부합니다."
        )
    if "18456" in message:
        return (
            "로그인 실패입니다(오류 18456). 서버에는 닿았지만 계정이 거부됐습니다.\n"
            "  → 아이디/비밀번호 오타이거나,\n"
            "  → SQL Server 가 혼합 모드 인증이 아닌 Windows 인증 전용일 수 있습니다."
        )
    if "4060" in message:
        return (
            "데이터베이스를 열 수 없습니다(오류 4060).\n"
            "  → .env 의 MSSQL_DATABASE 이름이 맞는지,\n"
            "  → 그 계정에 해당 DB 접근 권한이 있는지 확인하세요."
        )
    if "08001" in message or "provider" in message.lower():
        return (
            "서버에 접속하지 못했습니다.\n"
            "  → SQL Server 서비스가 실행 중인지,\n"
            "  → TCP/IP 프로토콜이 켜져 있고 1433 포트인지,\n"
            "  → 설정을 바꾼 뒤 서비스를 재시작했는지 확인하세요."
        )
    return "알려진 패턴이 아닙니다. 위의 원본 오류 메시지를 그대로 확인하세요."


# ▸ 단어 분해: def main(③)() -> None(② 돌려주는 것 없음):
def main() -> None:
    """
    전체 흐름을 순서대로 실행한다.

    입력: 없음
    출력: 없음. 결과는 화면에 출력하고, 실패하면 종료 코드 1 로 끝낸다.
    실패 시: 접속 실패면 원인 설명을 출력하고 sys.exit(1)
    """
    # ▸ "=" * 60 : 문자열 곱하기 = 같은 글자 60번. 구분선.
    print("=" * 60)
    print("SQL Server 접속 확인")
    print("=" * 60)

    # ▸ 단어 분해: for driver_name(③) in pyodbc.drivers(② 설치된 드라이버 이름 목록)():
    # ▸ 왜 먼저 보여주나: 드라이버 이름 오타가 흔한 실패 원인이라, .env 의 MSSQL_DRIVER 와 대조할 수 있게.
    print("\n[설치된 ODBC 드라이버]")
    for driver_name in pyodbc.drivers():
        print(f"  - {driver_name}")

    config = load_config()

    # ▸ 접속 정보를 보여주되 비밀번호는 절대 출력하지 않는다. 로그나 화면 캡처를 통해 비밀번호가 새는 것을 막기 위해서.
    print("\n[접속 정보]")
    print(f"  서버      : {config['server']},{config['port']}")
    print(f"  데이터베이스: {config['database']}")
    print(f"  계정      : {config['user']}")
    print(f"  드라이버   : {config['driver']}")

    connection_string = build_connection_string(config)

    print("\n[접속 시도]")
    # ▸ try(①): 이 블록에서 예외가 나면 아래 except 로.
    try:
        # ▸ 단어 분해: with pyodbc.connect(② 접속)(connection_string, timeout=5(② 5초 안에 못 붙으면 포기)) as connection(③):
        # ▸ with 문(컨텍스트 매니저): 블록을 벗어날 때 연결을 자동으로 닫아준다. 직접 close() 를 부르지 않아도 되고, 중간에 오류가 나도 반드시 닫힌다.
        # ▸ timeout 기본값은 무한정 기다린다. 서버가 꺼져 있을 때 5초 만에 실패를 알려 주려고.
        with pyodbc.connect(connection_string, timeout=5) as connection:
            # ▸ cursor(③) = connection.cursor(② 커서 만들기)()
            # ▸ 커서 : SQL 을 실행하고 결과를 한 줄씩 받아오는 객체. SSMS 의 쿼리 창 하나에 해당.
            cursor = connection.cursor()

            # ▸ cursor.execute(② SQL 실행)("SELECT @@VERSION")
            # ▸ @@VERSION 은 SQL Server 가 자기 버전을 알려주는 내장 값. 접속이 됐는지 확인하는 가장 가벼운 질의라 점검용으로 쓴다.
            cursor.execute("SELECT @@VERSION")

            # ▸ 단어 분해: version(③) = cursor.fetchone(② 결과 첫 행 가져오기)()[0](첫 칸)
            # ▸ 결과는 튜플 형태라 [0] 으로 첫 번째 칸을 꺼낸다. 행이 없으면 fetchone 이 None 이라 [0] 에서 죽지만, @@VERSION 은 항상 한 행이다.
            version = cursor.fetchone()[0]

            # ▸ DB_NAME() : 지금 붙어 있는 데이터베이스 이름 / SUSER_NAME() : 지금 로그인한 계정 이름.
            # ▸ .env 에 적은 것과 실제로 붙은 곳이 같은지 교차 확인하는 용도.
            cursor.execute("SELECT DB_NAME(), SUSER_NAME()")
            # ▸ current_db, current_user = cursor.fetchone()  — 두 칸짜리 튜플을 변수 둘에 나눠 담기(튜플 언패킹).
            current_db, current_user = cursor.fetchone()

        # ▸ with 블록을 나왔으니 연결은 닫혔다. 꺼내 둔 값(version 등)은 그대로 쓸 수 있다.
        print("  [성공] 접속됐습니다.\n")
        # ▸ version.splitlines()(② 줄 단위로 나눔)[0](첫 줄): @@VERSION 은 여러 줄이라 첫 줄("Microsoft SQL Server 2022 …")만.
        print(f"  서버 버전    : {version.splitlines()[0]}")
        print(f"  현재 DB      : {current_db}")
        print(f"  현재 로그인   : {current_user}")

    # ▸ 단어 분해: except(①) pyodbc.Error(② 이 종류의 예외를) as(①) error(③ 이 이름으로):
    # ▸ pyodbc.Error 는 pyodbc 가 내는 모든 오류의 부모 클래스. 이것 하나만 잡으면 접속 관련 오류 전부를 걸러낼 수 있다.
    # ▸ 다른 선택: except Exception 은 모든 오류를 잡지만, 그러면 코드 오타(NameError 등)까지 "접속 실패" 로 보여 원인이 숨는다.
    except pyodbc.Error as error:
        print("  [실패] 접속하지 못했습니다.\n")
        print("  --- 원본 오류 메시지 ---")
        print(f"  {error}\n")
        print("  --- 원인 추정 ---")
        print(f"  {explain_error(error)}")
        sys.exit(1)


# ▸ 이 파일을 직접 실행했을 때만 main() 을 부른다는 관용구. db.py 가 import 할 때는 실행되지 않는다(그래서 db.py 를 import 해도 접속 시험이 돌지 않는다).
if __name__ == "__main__":
    main()
