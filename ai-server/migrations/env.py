# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  migrations/env.py — Alembic 명령이 돌 때마다 맨 먼저 실행되는 설정 코드                         ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 읽히나 ─────────────────────────────────────────────────────────
# │
# │  Alembic 에게 두 가지를 알려 준다.
# │    ① 어느 DB 에 붙을 것인가      → db.py 의 build_url() (.env 에서 읽는다. 여기에도 alembic.ini 에도 비밀번호를 적지 않는다)
# │    ② 표의 설계가 어디에 있는가    → db.py 의 Base.metadata (models.py 의 Inspection 이 여기에 등록돼 있다)
# │  autogenerate 는 ②(코드의 설계)와 ①(실제 DB)을 비교해서 차이만큼 마이그레이션 파일을 써 준다.
# │
# │  ★ 원본은 `alembic init migrations` 가 만들어 준 템플릿이다. 우리가 고친 곳은 세 군데:
# │     (a) from db import Base, build_url + import models       ← 서버와 같은 접속·설계를 쓰도록
# │     (b) target_metadata = Base.metadata                     ← 템플릿은 None
# │     (c) url=build_url() / create_engine(build_url(), …)      ← 템플릿은 alembic.ini 의 sqlalchemy.url 을 읽는다
# │     나머지(fileConfig, offline/online 두 함수, 맨 아래 if)는 템플릿 그대로다.
# │
# │  터미널에서 alembic 명령 ──▶ alembic.ini (폴더 위치·로그 설정) ──▶ [현재 파일] ──▶ migrations/versions/*.py 의 upgrade()/downgrade() 실행
# │  앞: ai-server 폴더에서 실행해야 한다. alembic.ini 의 prepend_sys_path = . 덕에 같은 폴더의 db.py, models.py 를 import 할 수 있다.
# │  뒤: 서버(main.py)가 돌 때는 이 파일이 실행되지 않는다. 표 구조를 바꿀 때만 쓴다.
# │
# │  실행 순서: import → config 읽기 → 로그 설정 → target_metadata → (맨 아래 if) offline 또는 online 함수 → 그 안에서 context.run_migrations() 가 versions/ 파일을 실행
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : from import def with if else is not None
# │  ② 라이브러리가 정한 이름
# │       fileConfig                                     ← logging.config (Python 기본)
# │       context .config .configure .begin_transaction .run_migrations .is_offline_mode  ← alembic
# │       create_engine pool.NullPool                    ← sqlalchemy
# │       config.config_file_name                        ← alembic Config 객체의 속성
# │       target_metadata                                ← 이름은 우리가 짓지만 Alembic 이 이 이름으로 찾지는 않는다. configure(target_metadata=…) 로 넘겨 준다
# │       run_migrations_offline / run_migrations_online ← 템플릿이 지은 함수 이름. 바꿔도 되지만 관례
# │  ③ 내가 지은(또는 내 다른 파일의) 이름
# │       Base build_url (db.py)   models (models.py)   connectable connection
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  from logging.config import fileConfig       (Python 기본) → alembic.ini 의 로그 설정 적용
# │  from alembic import context                 (pip: alembic) → 지금 실행 중인 명령의 정보·설정 통로
# │  from sqlalchemy import create_engine, pool  (pip)          → 엔진, 연결 풀 종류
# │  from db import Base, build_url              (내 파일)
# │  import models                               (내 파일)      → Inspection 을 Base.metadata 에 등록시키려고
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  마이그레이션    : DB 구조 변경 하나. versions/ 폴더의 파일 하나. upgrade()=적용, downgrade()=되돌리기.
# │  alembic_version : Alembic 이 DB 안에 만드는 작은 표. "어느 마이그레이션까지 적용됐나" 한 줄을 기억한다. 지금 값 d5097882b38e.
# │  online 모드     : 실제 DB 에 붙어서 SQL 을 실행한다. 평소에 쓰는 방식 (alembic upgrade head).
# │  offline 모드    : DB 에 붙지 않고 실행될 SQL 을 글자로만 찍는다 (alembic upgrade head --sql). 적용 전에 미리 볼 때.
# │  트랜잭션        : SQL 여러 개를 한 묶음으로. 중간에 실패하면 앞의 것도 취소(ROLLBACK). SQLD 의 그 트랜잭션.
# └────────────────────────────────────────────────────────────────────────────────────────

# ▸ fileConfig(② 함수): alembic.ini 의 [loggers] 설정을 읽어 로그 출력을 맞춘다. "Running upgrade …" 줄이 이것으로 찍힌다. (템플릿 그대로)
from logging.config import fileConfig

# ▸ context(② alembic 이 주는 객체): 지금 실행 중인 명령의 정보를 담아 넘겨 주는 통로. 설정을 읽고 마이그레이션을 돌린다. (템플릿 그대로)
from alembic import context

# ▸ create_engine(② 엔진 만들기), pool(② 연결 풀 모듈. 아래 pool.NullPool 로 쓴다). (템플릿 그대로. 템플릿은 engine_from_config 를 쓰기도 한다)
from sqlalchemy import create_engine, pool

# ▸ (a) 우리가 고친 줄. Base(설계 목록)·build_url(접속 URL)을 서버와 똑같은 것으로 쓴다. 두 군데서 따로 만들면 서버와 Alembic 이 다른 DB 를 볼 수 있다.
from db import Base, build_url

# ▸ (a) 우리가 추가한 줄. ★ 이 import 가 없으면 autogenerate 가 "바꿀 것이 없다" 고 나온다.
# ▸ 왜: Base.metadata 에는 "import 된" 모델만 등록된다. models 를 읽어 들여야 Inspection 이 목록에 들어간다.
# ▸ 이름을 직접 쓰지는 않아서 편집기가 "안 쓰는 import" 라고 표시할 수 있다. # noqa: F401 은 검사 도구(ruff/flake8)에게 "이 줄은 일부러 그런 것" 이라는 표시. 지우면 안 된다.
import models  # noqa: F401

# ▸ config(②) = context.config(② alembic.ini 의 내용을 담은 객체). (템플릿 그대로)
config = context.config

# ▸ 단어 분해: if config.config_file_name(② ini 파일 경로) is not None: fileConfig(config.config_file_name)
# ▸ 뜻: alembic.ini 가 있으면 그 로그 설정을 적용한다. (템플릿 그대로)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ▸ (b) 우리가 고친 줄. 템플릿은 target_metadata = None.
# ▸ target_metadata(②) = Base.metadata(② Base 를 상속한 클래스들의 표 정의 목록)
# ▸ 뜻: autogenerate 가 실제 DB 와 비교할 "코드 쪽 설계". 표가 늘면 models.py 에 클래스를 추가하기만 하면 여기에 자동으로 들어온다.
target_metadata = Base.metadata


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  두 모드 — 아래 두 함수는 템플릿이 만든 것. 안의 인자 몇 개만 우리가 바꿨다.
# ═══════════════════════════════════════════════════════════════════════════════════════════

def run_migrations_offline() -> None:
    """DB 에 붙지 않고, 실행될 SQL 을 글자로만 찍는다 (`alembic upgrade head --sql`).

    입력: 없음
    출력: 없음. SQL 이 터미널에 찍힌다.
    실패 시: .env 가 없으면 build_url 안의 load_config 가 안내문을 찍고 끝낸다.
    """
    # ▸ 단어 분해: context.configure(② 설정 넣기)( url=…, target_metadata=…, literal_binds=True, dialect_opts={…} )
    context.configure(
        # ▸ (c) url=build_url(): 접속은 안 하지만 "SQL Server 문법으로 찍어라" 를 알려면 URL 의 앞부분(mssql+pyodbc)이 필요하다. 템플릿은 config.get_main_option("sqlalchemy.url").
        url=build_url(),
        target_metadata=target_metadata,
        # ▸ literal_binds=True: 값을 ? 자리표시가 아니라 SQL 글자 안에 직접 적어 찍는다. 눈으로 읽기 위한 출력이라서. (템플릿 그대로)
        literal_binds=True,
        # ▸ dialect_opts={"paramstyle": "named"}: 자리표시 형식. 템플릿 그대로. 우리는 literal_binds 라 사실상 안 쓰인다.
        dialect_opts={"paramstyle": "named"},
    )

    # ▸ with context.begin_transaction(② 트랜잭션 시작)(): context.run_migrations(② versions/ 파일들 실행)()
    # ▸ 트랜잭션으로 묶는다. 중간에 실패하면 앞의 변경도 취소된다. (offline 에서는 BEGIN/COMMIT 글자가 찍힐 뿐)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """실제 DB 에 붙어서 마이그레이션을 실행한다. 평소의 `alembic upgrade head` 가 이쪽이다.

    입력: 없음
    출력: 없음. DB 구조가 바뀌고 alembic_version 표가 갱신된다.
    실패 시: 접속 정보가 틀렸거나 SQL Server 가 꺼져 있으면 sqlalchemy.exc.OperationalError / InterfaceError.
    """
    # ▸ (c) 단어 분해: connectable(③) = create_engine(build_url()(접속 URL), poolclass=pool.NullPool(② 풀 없음))
    # ▸ 왜 db.py 의 engine 을 그대로 쓰지 않고 새로 만드나 — 두 가지:
    #   ① db.py 는 ECHO_SQL=True 라 Alembic 이 DB 를 조사하는 수십 줄의 SQL 이 쏟아진다. 여기서는 끈다(echo 기본값 False).
    #   ② NullPool : 연결을 재사용하지 않고 쓰고 바로 닫는다. 명령 한 번 돌고 끝나는 프로그램이라 풀이 필요 없다.
    # ▸ 템플릿은 engine_from_config(config.get_section(…), prefix="sqlalchemy.", poolclass=pool.NullPool) — alembic.ini 의 sqlalchemy.url 을 읽는다. 우리는 ini 에 비밀번호를 안 두려고 build_url() 로 바꿨다.
    connectable = create_engine(build_url(), poolclass=pool.NullPool)

    # ▸ with connectable.connect(② 실제 접속)() as connection(③): 블록을 나가면 연결을 닫는다. (템플릿 그대로)
    with connectable.connect() as connection:
        # ▸ context.configure(connection=connection(이 연결로), target_metadata=target_metadata(이 설계와 비교))
        context.configure(connection=connection, target_metadata=target_metadata)

        # ▸ 마이그레이션 전체를 트랜잭션 하나로 묶는다. 중간에 실패하면 표가 반쯤 만들어진 상태로 남지 않는다. (템플릿 그대로)
        with context.begin_transaction():
            context.run_migrations()


# ▸ 단어 분해: if context.is_offline_mode(② --sql 을 붙였나)(): offline 함수 else: online 함수   (템플릿 그대로)
# ▸ 이 if 가 이 파일의 진입점이다. if __name__ == "__main__" 이 없는 이유: Alembic 이 이 파일을 "실행" 하지 import 하지 않기 때문.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
