# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   Alembic 명령(alembic revision, alembic upgrade ...)이 돌 때마다 맨 먼저 실행되는 설정 코드.
#   Alembic 에게 두 가지를 알려 준다.
#     ① 어느 DB 에 붙을 것인가      → db.py 의 build_url() (.env 에서 읽는다. 여기에도 alembic.ini 에도 비밀번호를 적지 않는다)
#     ② 표의 설계가 어디에 있는가    → db.py 의 Base.metadata (models.py 의 Inspection 이 여기에 등록돼 있다)
#   autogenerate 는 ②(코드의 설계)와 ①(실제 DB)을 비교해서 차이만큼 마이그레이션 파일을 써 준다.
#
#   원본은 `alembic init migrations` 가 만들어 준 파일이고, 위 두 가지를 연결하도록 고쳤다.
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   터미널에서 alembic 명령 ──▶ alembic.ini (폴더 위치·로그 설정) ──▶ [현재 파일] ──▶ migrations/versions/*.py 의 upgrade()/downgrade() 실행
#   앞: ai-server 폴더에서 실행해야 한다. alembic.ini 의 prepend_sys_path = . 덕에 같은 폴더의 db.py, models.py 를 import 할 수 있다.
#   뒤: 서버(main.py)가 돌 때는 이 파일이 실행되지 않는다. 표 구조를 바꿀 때만 쓴다.
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   마이그레이션   : DB 구조 변경 하나. versions/ 폴더의 파일 하나. upgrade()=적용, downgrade()=되돌리기.
#   alembic_version: Alembic 이 DB 안에 만드는 작은 표. "어느 마이그레이션까지 적용됐나" 한 줄을 기억한다.
#   online 모드    : 실제 DB 에 붙어서 SQL 을 실행한다. 평소에 쓰는 방식.
#   offline 모드   : DB 에 붙지 않고 실행될 SQL 을 글자로만 찍는다. `alembic upgrade head --sql`. 적용 전에 미리 볼 때 쓴다.
# ─────────────────────────────────────────────────────────────────────────────

# fileConfig : alembic.ini 의 [loggers] 설정을 읽어 로그 출력을 맞춘다. "Running upgrade ..." 줄이 이것으로 찍힌다.
from logging.config import fileConfig

# context : Alembic 이 지금 실행 중인 명령의 정보를 담아 넘겨 주는 객체. 설정을 읽고 마이그레이션을 돌리는 통로.
from alembic import context

# create_engine : 접속 URL 로 엔진을 만든다.  pool : 연결을 재사용할지 정하는 모듈.
from sqlalchemy import create_engine, pool

# 접속 URL 과 설계 목록(Base)은 서버와 똑같은 것을 쓴다. 두 군데서 따로 만들면 서버와 Alembic 이 다른 DB 를 볼 수 있다.
from db import Base, build_url

# ★ 이 import 가 없으면 autogenerate 가 "바꿀 것이 없다" 고 나온다.
# Base.metadata 에는 "import 된" 모델만 등록된다. models 를 읽어 들여야 Inspection 이 목록에 들어간다.
# 이름을 직접 쓰지는 않아서 편집기가 "안 쓰는 import" 라고 표시할 수 있다. 지우면 안 된다.
import models  # noqa: F401

# alembic.ini 의 내용을 담은 객체.
config = context.config

# alembic.ini 의 로그 설정을 적용한다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 가 실제 DB 와 비교할 "코드 쪽 설계". 표가 늘면 models.py 에 클래스를 추가하기만 하면 여기에 자동으로 들어온다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 에 붙지 않고, 실행될 SQL 을 글자로만 찍는다 (`alembic upgrade head --sql`).

    입력: 없음
    출력: 없음. SQL 이 터미널에 찍힌다.
    실패 시: .env 가 없으면 build_url 안의 load_config 가 안내문을 찍고 끝낸다.
    """
    context.configure(
        # 접속은 안 하지만 "SQL Server 문법으로 찍어라" 를 알려면 URL 의 앞부분(mssql+pyodbc)이 필요하다.
        url=build_url(),
        target_metadata=target_metadata,
        # 값을 ? 자리표시가 아니라 SQL 글자 안에 직접 적어 찍는다. 눈으로 읽기 위한 출력이라서.
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    # 트랜잭션으로 묶는다. 중간에 실패하면 앞의 변경도 취소된다.
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """실제 DB 에 붙어서 마이그레이션을 실행한다. 평소의 `alembic upgrade head` 가 이쪽이다.

    입력: 없음
    출력: 없음. DB 구조가 바뀌고 alembic_version 표가 갱신된다.
    실패 시: 접속 정보가 틀렸거나 SQL Server 가 꺼져 있으면 sqlalchemy.exc.OperationalError / InterfaceError.
    """
    # db.py 의 engine 을 그대로 쓰지 않고 새로 만드는 이유 두 가지:
    #   ① db.py 는 ECHO_SQL=True 라 Alembic 이 DB 를 조사하는 수십 줄의 SQL 이 쏟아진다. 여기서는 끈다.
    #   ② NullPool : 연결을 재사용하지 않고 쓰고 바로 닫는다. 명령 한 번 돌고 끝나는 프로그램이라 풀이 필요 없다.
    connectable = create_engine(build_url(), poolclass=pool.NullPool)

    # with : 블록을 나가면 연결을 닫는다.
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        # 마이그레이션 전체를 트랜잭션 하나로 묶는다. 중간에 실패하면 표가 반쯤 만들어진 상태로 남지 않는다.
        with context.begin_transaction():
            context.run_migrations()


# `--sql` 을 붙였으면 offline, 아니면 online.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
