"""
SQL Server 접속 확인 스크립트

이 파일은 무엇을 하는가:
    .env 에 적힌 접속 정보로 SQL Server 에 실제로 붙어보고,
    성공하면 서버 버전을 출력한다. 실패하면 원인을 한국어로 알려준다.

프로젝트 실행 흐름에서 어느 위치인가:
    ai-server 본체가 호출하는 파일이 아니다. 사람이 손으로 실행하는 점검 도구다.
    환경을 새로 구축했을 때 "DB 가 붙는가"를 가장 먼저 확인하는 용도다.
    실행: ai-server 폴더에서  .venv\\Scripts\\python.exe check_db.py

이 파일을 이해하기 전에 알아야 할 개념:
    - ODBC : 프로그램이 여러 종류의 DB 에 같은 방식으로 접속하게 해주는 표준 규격.
             파이썬(pyodbc) 과 SQL Server 사이에 "ODBC Driver 18" 이라는 번역기가 낀다.
    - 연결 문자열(connection string) : 어디에, 누구로, 어떻게 붙을지를
             "키=값;키=값;" 형태로 이어 붙인 한 줄짜리 문자열.
"""

# os : 환경변수(os.environ)를 읽기 위해 쓰는 파이썬 표준 라이브러리
import os

# sys : 스크립트를 실패 상태로 끝낼 때(sys.exit(1)) 쓴다.
#       종료 코드 0 은 성공, 0 이 아니면 실패라는 것이 프로그램의 관례다.
import sys

# pathlib.Path : 파일 경로를 문자열이 아니라 객체로 다루는 표준 라이브러리.
#                운영체제마다 다른 경로 구분자(\ 와 /)를 알아서 처리해준다.
from pathlib import Path

# pyodbc : 파이썬에서 ODBC 드라이버를 통해 DB 에 접속하는 라이브러리.
#          이것이 있어야 SQL Server 에 붙을 수 있다.
import pyodbc

# python-dotenv 의 load_dotenv : .env 파일을 읽어서 os.environ 에 올려준다.
#                                접속 정보를 코드에 하드코딩하지 않기 위한 것이다.
from dotenv import load_dotenv


# __file__ 은 "지금 실행 중인 이 파일의 경로".
# .parent 는 그 파일이 들어있는 폴더 → 즉 ai-server 폴더.
# 어느 위치에서 실행하든 항상 ai-server/.env 를 찾도록 하기 위해 이렇게 쓴다.
ENV_PATH = Path(__file__).parent / ".env"


def load_config() -> dict[str, str]:
    """
    .env 파일을 읽어 접속에 필요한 값들을 꺼내온다.

    입력: 없음 (ENV_PATH 위치의 .env 파일을 읽는다)
    출력: dict. 예) {"server": "localhost", "port": "1433", "database": "smart_factory", ...}
    실패 시: .env 파일이 없거나 필수 항목이 비어 있으면 SystemExit 로 종료한다.
    """
    # .env 파일이 아예 없으면 여기서 멈춘다. 없는 채로 진행하면
    # "접속 실패" 라는 엉뚱한 메시지가 나와서 원인을 찾기 어려워진다.
    if not ENV_PATH.exists():
        print(f"[실패] .env 파일이 없습니다: {ENV_PATH}")
        print("       .env.example 을 같은 폴더에 .env 로 복사하고 값을 채우세요.")
        sys.exit(1)

    # load_dotenv 는 .env 의 내용을 os.environ 에 넣어준다.
    # override=True 는 이미 같은 이름의 환경변수가 있어도 .env 값으로 덮어쓰라는 뜻.
    # 안 그러면 예전에 설정해둔 시스템 환경변수 때문에 헷갈리는 일이 생긴다.
    load_dotenv(ENV_PATH, override=True)

    # 필요한 값을 이름으로 꺼낸다. 두 번째 인자는 값이 없을 때 쓸 기본값이다.
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

    # 비어 있으면 접속이 불가능한 항목들을 미리 걸러낸다.
    # 리스트 컴프리헨션: [식 for 변수 in 반복대상 if 조건] 형태로
    # 반복문을 한 줄로 써서 새 리스트를 만드는 파이썬 문법이다.
    missing = [k for k in ("server", "database", "user", "password") if not config[k]]
    if missing:
        print(f"[실패] .env 에서 다음 항목이 비어 있습니다: {', '.join(missing)}")
        sys.exit(1)

    return config


def build_connection_string(config: dict[str, str]) -> str:
    """
    접속 정보를 ODBC 연결 문자열 한 줄로 조립한다.

    입력: load_config() 가 돌려준 dict
    출력: str. 예) "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;..."
    실패 시: 예외를 던지지 않는다. 값이 틀렸는지는 실제 접속 시점에 드러난다.
    """
    # DRIVER 값을 중괄호로 감싸는 이유:
    #   드라이버 이름에 공백이 들어 있어서, 감싸지 않으면 ODBC 가 이름을 잘라 읽는다.
    # SERVER 에 서버와 포트를 쉼표로 붙이는 것은 ODBC 의 표기 규칙이다(콜론이 아니다).
    # Encrypt / TrustServerCertificate:
    #   ODBC Driver 18 부터 Encrypt 기본값이 yes 로 바뀌었다.
    #   로컬 SQL Server 는 자체 서명 인증서를 쓰므로 신뢰할 수 없다고 판단되어 거부된다.
    #   그래서 개발 환경에서는 TrustServerCertificate=yes 로 "이 인증서는 믿는다"고 알려준다.
    return (
        f"DRIVER={{{config['driver']}}};"
        f"SERVER={config['server']},{config['port']};"
        f"DATABASE={config['database']};"
        f"UID={config['user']};"
        f"PWD={config['password']};"
        f"Encrypt={config['encrypt']};"
        f"TrustServerCertificate={config['trust']};"
    )


def explain_error(error: pyodbc.Error) -> str:
    """
    pyodbc 가 던진 오류를 보고 원인을 한국어로 설명한다.

    입력: pyodbc.Error 예외 객체
    출력: str. 사람이 읽을 수 있는 원인 설명과 다음에 할 일
    실패 시: 아는 패턴이 없으면 "원인 미상" 안내를 돌려준다.
    """
    # 예외 객체를 문자열로 바꾸면 드라이버가 준 원본 메시지가 들어 있다.
    message = str(error)

    # 자주 나오는 실패 유형을 순서대로 확인한다.
    # 순서가 중요하다: 위쪽일수록 실제로 자주 먼저 터지는 것이다.
    if "IM002" in message:
        return (
            "ODBC 드라이버를 찾지 못했습니다.\n"
            "  → .env 의 MSSQL_DRIVER 이름이 실제 설치된 이름과 글자까지 같은지 확인하세요.\n"
            "  → 설치된 드라이버 목록은 이 스크립트가 위에 출력해 줍니다."
        )
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


def main() -> None:
    """
    전체 흐름을 순서대로 실행한다.

    입력: 없음
    출력: 없음. 결과는 화면에 출력하고, 실패하면 종료 코드 1 로 끝낸다.
    실패 시: 접속 실패면 원인 설명을 출력하고 sys.exit(1)
    """
    print("=" * 60)
    print("SQL Server 접속 확인")
    print("=" * 60)

    # 설치된 ODBC 드라이버 목록을 먼저 보여준다.
    # 드라이버 이름 오타가 흔한 실패 원인이라, 대조할 수 있게 먼저 출력한다.
    print("\n[설치된 ODBC 드라이버]")
    for driver_name in pyodbc.drivers():
        print(f"  - {driver_name}")

    config = load_config()

    # 접속 정보를 보여주되 비밀번호는 절대 출력하지 않는다.
    # 로그나 화면 캡처를 통해 비밀번호가 새는 것을 막기 위해서다.
    print("\n[접속 정보]")
    print(f"  서버      : {config['server']},{config['port']}")
    print(f"  데이터베이스: {config['database']}")
    print(f"  계정      : {config['user']}")
    print(f"  드라이버   : {config['driver']}")

    connection_string = build_connection_string(config)

    print("\n[접속 시도]")
    try:
        # with 문(컨텍스트 매니저): 블록을 벗어날 때 연결을 자동으로 닫아준다.
        # 직접 close() 를 부르지 않아도 되고, 중간에 오류가 나도 반드시 닫힌다.
        # timeout=5 는 5초 안에 못 붙으면 포기하라는 뜻. 기본값은 무한정 기다린다.
        with pyodbc.connect(connection_string, timeout=5) as connection:
            # cursor : SQL 을 실행하고 결과를 한 줄씩 받아오는 객체
            cursor = connection.cursor()

            # @@VERSION 은 SQL Server 가 자기 버전을 알려주는 내장 값이다.
            # 접속이 됐는지 확인하는 가장 가벼운 질의라 점검용으로 쓴다.
            cursor.execute("SELECT @@VERSION")

            # fetchone() 은 결과의 첫 줄을 가져온다.
            # 결과는 튜플 형태라 [0] 으로 첫 번째 칸을 꺼낸다.
            version = cursor.fetchone()[0]

            # DB_NAME() 은 지금 붙어 있는 데이터베이스 이름,
            # SUSER_NAME() 은 지금 로그인한 계정 이름을 돌려준다.
            # .env 에 적은 것과 실제로 붙은 곳이 같은지 교차 확인하는 용도다.
            cursor.execute("SELECT DB_NAME(), SUSER_NAME()")
            current_db, current_user = cursor.fetchone()

        print("  [성공] 접속됐습니다.\n")
        print(f"  서버 버전    : {version.splitlines()[0]}")
        print(f"  현재 DB      : {current_db}")
        print(f"  현재 로그인   : {current_user}")

    except pyodbc.Error as error:
        # pyodbc.Error 는 pyodbc 가 내는 모든 오류의 부모 클래스다.
        # 이것 하나만 잡으면 접속 관련 오류 전부를 걸러낼 수 있다.
        print("  [실패] 접속하지 못했습니다.\n")
        print("  --- 원본 오류 메시지 ---")
        print(f"  {error}\n")
        print("  --- 원인 추정 ---")
        print(f"  {explain_error(error)}")
        sys.exit(1)


# 이 파일을 직접 실행했을 때만 main() 을 부른다는 뜻의 관용구.
# 다른 파일이 이 파일을 import 할 때는 실행되지 않는다.
if __name__ == "__main__":
    main()
