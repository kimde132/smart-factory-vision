# 환경 구축 로그

> C등급 작업 기록. 항목당 5줄 이내: 실행한 명령 / 왜 필요했나 / 막힌 것 / 해결 방법
> 목적은 재현성(다른 PC에서 다시 세팅할 때)과 면접 재료다.

## 작업 시작 시점의 환경 (2026-08-07)

| 항목 | 상태 |
|---|---|
| OS | Windows 11 Pro 26200 |
| git | 2.54.0.windows.1 (설치돼 있음, user.name/email 설정 완료) |
| Python | 3.13.14 (py 런처 등록) |
| winget | 1.29.280 |
| .NET SDK | 없음 |
| SQL Server / SSMS / ODBC 18 | 없음 |
| GPU | Intel Arc 130V — CUDA 불가, 학습은 Colab |
| C: 여유 공간 | 601 GB |

---

## 1. git 저장소 + .gitignore

```powershell
git init -b main
git config core.autocrlf true
git config core.quotepath false   # 한글 파일명이 \354\212... 로 깨져 보여서
```

- **왜:** 첫 커밋 전에 `.gitignore`를 넣어야 이미지·모델·`.env`가 히스토리에 한 번도 들어가지 않는다.
- **막힌 것:** `git check-ignore -v`가 부정 규칙(`!.env.example`)도 "매칭됨"으로 출력해 무시 여부를 판단할 수 없었다.
- **해결:** 실제 테스트 파일을 만들고 `git status --untracked-files=all --ignored=matching`으로 확정 검증. `.env`는 무시, `.env.example`은 추적됨을 확인 후 테스트 파일 삭제.
- **부가:** `.gitattributes`에 `* text=auto`를 넣어 Windows CRLF 경고를 처리. `docs/images/`는 이미지 무시 규칙의 예외로 지정(README 스크린샷용).

## 2. 폴더 구조 스캐폴딩

```powershell
foreach ($d in 'ai-server','wpf-client','dataset','models','storage') { New-Item -ItemType Directory -Force $d }
New-Item -ItemType File ai-server\.gitkeep, wpf-client\.gitkeep
```

- **왜:** 이후 산출물(가상환경, `.env`, 연결 테스트 스크립트, WPF 프로젝트)이 놓일 자리를 먼저 만든다.
- **막힌 것:** 없음.
- **참고:** git이 빈 폴더를 추적하지 않아 `.gitkeep`이 필요하지만, `dataset`·`models`·`storage`는 `.gitignore` 대상이라 넣지 않았다(넣어도 무시되어 혼란만 준다).
- CLAUDE.md의 폴더 구조에는 `smart-factory-vision-inspection`으로 적혀 있으나 실제 폴더명은 `smart-factory-vision`. 폴더명을 유지하고 문서 표기를 맞추기로 함.

## 3. SQL Server 2022 Developer + ODBC 18 + SSMS 21

```powershell
# 부트스트래퍼 내려받기 (SHA256이 winget 매니페스트 값과 일치하는지 확인)
Invoke-WebRequest -Uri "https://download.microsoft.com/download/c/c/9/.../SQL2022-SSEI-Dev.exe" -OutFile $out
# 관리자 권한으로 무인 설치 스크립트 실행
Start-Process powershell -Verb RunAs -ArgumentList '-File', 'install-sql.ps1'
```

- **왜:** 5주차에 SQL Server를 처음 만지면 며칠이 사라진다. 부품 배송 대기 중인 지금 뚫어둔다.
- **막힌 것:** `winget install Microsoft.SQLServer.2022.Developer`는 `SQL2022-SSEI-Dev.exe`(설치 마법사를 띄우는 부트스트래퍼)를 실행할 뿐이다. 마법사의 "기본 설치"를 고르면 **Windows 인증 전용**으로 깔려서, 혼합 모드 전환과 TCP/IP 활성화를 나중에 손으로 해야 한다.
- **해결:** 마법사를 쓰지 않고 `/ACTION=Download`로 설치 매체를 받아 압축을 푼 뒤, `SETUP.EXE`에 옵션을 직접 넣어 무인 설치했다. 핵심 옵션 두 개:
  - `/SECURITYMODE=SQL` + `/SAPWD=...` → 혼합 모드 인증을 **설치 시점에** 켠다
  - `/TCPENABLED=1` → TCP/IP를 **설치 시점에** 켠다 (pyodbc 접속의 전제 조건)
- 그 외: `/FEATURES=SQLENGINE`(엔진만), `/INSTANCENAME=MSSQLSERVER`(기본 인스턴스 → `localhost`로 접속), `/NPENABLED=0`, `/IACCEPTSQLSERVERLICENSETERMS`.
- 관리자 권한이 필요해 UAC 승인 창을 사용자가 직접 눌렀다.

### 3-1. 여기서 4번 연속으로 막혔다 (실패 기록)

오늘 가장 오래 걸린 구간이다. 실패마다 증상이 달라서 원인을 하나씩 분리해야 했다.

| # | 증상 | 원인 | 해결 |
|---|---|---|---|
| 1 | `SETUP.EXE`가 **1초 만에** 종료 코드 `-2067529714`(0x84C4000E). 설치 로그 폴더조차 안 생김 | 매체 경로가 **151자**. SQL Server 매체 안의 깊은 하위 경로와 합쳐져 Windows 260자 한계를 넘김 | 매체를 `C:\Users\kimde\sqlmedia`(22자)로 옮겨 설치. 경로 길이 35자로 축소 |
| 2 | 관리자 권한 스크립트가 UAC 승인 후에도 아무 일 없이 종료. 로그 파일조차 안 생김 | **Windows PowerShell 5.1은 BOM 없는 `.ps1`을 UTF-8이 아니라 CP949로 읽는다.** 한글 주석 바이트가 깨지면서 그중 하나가 따옴표로 해석돼 문법 오류 5건 발생 | 임시 스크립트를 **ASCII 전용**으로 재작성. 이후 실행 전에 `[Parser]::ParseFile`로 문법 검사를 먼저 통과시키는 절차를 추가 |
| 3 | 설치가 3분간 진행되다 로그가 **문장 중간에서 끊김**. 오류 메시지 없음 | 설치를 감싼 **관리자 권한 PowerShell 콘솔 창이 닫히면서** 그 안의 `setup.exe`가 함께 강제 종료됨 | PowerShell로 감싸지 않고 `SETUP.EXE`를 `-Verb RunAs`로 **직접** 실행. 콘솔 창이 없으니 닫힐 일도 없음 |
| 4 | 재시도 시 24초 만에 실패. `Exit message: 시스템 데이터베이스 파일 master.mdf이(가) 이미 ...DATA에 있습니다` | 3번에서 강제 종료된 반쪽 설치가 시스템 DB 파일을 남겨둠. SQL Server는 그 위에 덮어쓰지 않는다 | `SETUP.EXE /ACTION=Uninstall /FEATURES=SQLENGINE /INSTANCENAME=MSSQLSERVER`로 제거(종료 코드 0, 서비스·폴더 모두 정리됨) 후 재설치 |

**여기서 얻은 것:** 설치 프로그램이 로그를 **아예 안 남기면** 인자 파싱 이전 단계에서 죽은 것이고(경로·권한 문제), **문장 중간에서 끊기면** 외부에서 강제 종료된 것이다. 오류 메시지 없이 끝나는 두 경우를 구분하는 기준이 된다.

### 3-2. 최종 설치 결과

```
Final result: 통과 / Exit code: 0
MSSQLSERVER 서비스: Running (자동 시작)
TCP 1433 포트: 수신 중
```

- SQL Server 2022 (RTM) 16.0.1000.6 (X64), Developer 에디션, 기본 인스턴스.
- **ODBC Driver 18 은 winget 으로 따로 깔 필요가 없었다.** SQL Server 설치 시 필수 구성 요소로 함께 설치된다(설치 로그에 `msodbcsql_Cpu64_1.log`).
- SSMS 21, ODBC 18(최신 버전으로 갱신), .NET SDK 10 은 winget 으로 설치했다.

## 7. DB 초기 설정 + pyodbc 접속 검증

```python
# Windows 인증(현재 계정 = sysadmin)으로 접속해 실행
CREATE DATABASE [smart_factory_vision]
CREATE LOGIN [sfv_app] WITH PASSWORD = N'...', DEFAULT_DATABASE = [smart_factory_vision], CHECK_POLICY = ON
CREATE USER [sfv_app] FOR LOGIN [sfv_app]
ALTER ROLE db_owner ADD MEMBER [sfv_app]   -- 이 DB 안에서만 유효한 권한
ALTER LOGIN [sa] DISABLE
```

- **왜 sa 를 안 쓰는가:** `sa` 는 서버 전체 최고 권한이라 공격 표적이 된다. 애플리케이션에는 **자기 DB 안에서만** 권한을 갖는 전용 로그인을 준다. `db_owner` 를 준 이유는 Alembic 이 마이그레이션으로 테이블을 만들어야 하기 때문이다.
- **왜 sa 를 꺼도 안전한가:** 설치 시 `/SQLSYSADMINACCOUNTS` 로 Windows 계정을 sysadmin 에 넣었으므로, 문제가 생겨도 Windows 인증으로 들어갈 수 있다.
- **막힌 것:** 없음. 계획서에서 예상했던 3대 실패(ODBC 18 암호화 기본값 / 인증 모드 / TCP 미활성)가 모두 발생하지 않았다. 혼합 모드와 TCP 를 설치 명령에 넣었고, `TrustServerCertificate=yes` 를 `.env` 에 미리 넣어 예방했기 때문이다.

**검증 결과** (`ai-server/check_db.py`):

```
[성공] 접속됐습니다.
  서버 버전  : Microsoft SQL Server 2022 (RTM) - 16.0.1000.6 (X64)
  현재 DB    : smart_factory_vision
  현재 로그인 : sfv_app
```

- 접속 정보는 `ai-server/.env` 에만 있고, git 이 무시하는 것을 `git status --ignored` 로 확인했다.

## 8. .NET SDK + WPF 빈 프로젝트

```powershell
winget install --id Microsoft.DotNet.SDK.10 --silent
dotnet new wpf -o wpf-client -n SmartFactoryVision.Client
dotnet build wpf-client\SmartFactoryVision.Client.csproj
```

- **왜:** 3주차에 WPF 를 시작할 때 환경 문제로 며칠 날리지 않으려고 **빌드가 되는지만** 지금 확인해 둔다. 화면 구현은 하지 않았다.
- **막힌 것:** 없음.
- 결과: `net10.0-windows`, 빌드 **경고 0개 / 오류 0개**.
- `bin/`, `obj/` 가 `.gitignore` 로 제외되는 것을 `git status --ignored` 로 확인했다.
- 실제 소스 파일이 생겼으므로 `ai-server/.gitkeep`, `wpf-client/.gitkeep` 은 제거했다.

## 9. GitHub 원격 저장소

```powershell
winget install --id GitHub.cli --silent      # gh 2.97.0
gh auth login                                 # 대화형 — 사용자가 직접 실행
gh repo create smart-factory-vision --private --source=. --push
```

- **왜:** 백업과 이력 보존. 포트폴리오로 공개하는 것은 프로젝트가 모양을 갖춘 뒤로 미룬다.
- **막힌 것:** `gh auth login` 은 브라우저 인증이라 자동화할 수 없다. 사용자가 직접 실행해야 한다.
- **비공개로 시작한 이유:** 공개로 한 번 올린 내용은 포크·캐시로 남아 되돌리기 어렵다. 비공개 → 공개는 언제든 단추 하나다.
- push 직전에 `.env` 가 추적 목록에 없는 것을 다시 확인한다.

---

## 남아 있는 임시 파일

설치에 쓴 매체가 `C:\Users\kimde\sqlmedia` 에 약 **1.2GB** 남아 있다.
SQL Server 가 정상 동작하는 것을 확인했으므로 지워도 되고,
재설치가 필요하면 `SQL2022-SSEI-Dev.exe` 를 다시 받으면 된다.

## 4. Python 가상환경 + 패키지

```powershell
py -3.13 -m venv ai-server\.venv
ai-server\.venv\Scripts\python.exe -m pip install -r ai-server\requirements.txt
ai-server\.venv\Scripts\python.exe -m pip freeze > ai-server\requirements.lock.txt
```

- **왜:** 프로젝트 전용 패키지 공간. 시스템 파이썬을 오염시키지 않고, 다른 PC에서 같은 환경을 재현하기 위해서다.
- **막힌 것:** 없음. Python 3.13에 torch·ultralytics 휠이 없을 것을 우려했으나 기우였다.
- 설치된 주요 버전: `ultralytics 8.4.115`, `torch 2.13.0`(CPU), `pyodbc 5.3.0`, `fastapi 0.141.1`, `sqlalchemy 2.0.51`, `pandas 3.0.5`. 총 62개.
- 3.12 강등은 불필요했다.

## 5. Label Studio (라벨링 도구)

```powershell
py -3.13 -m venv .venv-labelstudio
.venv-labelstudio\Scripts\python.exe -m pip install label-studio
```

- **왜:** `ai-server/.venv`와 **분리했다.** 라벨링 도구와 학습 코드는 같이 실행할 일이 없고, 의존성이 충돌할 수 있다.
- **막힌 것:** 없음. `label-studio 1.23.0` 설치 성공.
- **분리가 옳았던 근거:** Label Studio가 의존성으로 `psycopg`(PostgreSQL 드라이버)를 끌고 왔다. 이 프로젝트는 MSSQL을 쓰므로 같은 환경에 섞였으면 혼란스러웠을 것이다.
- 프로젝트 생성과 라벨링 규칙 설정은 하지 않았다. **A등급(11·12번)이라 사용자가 직접 한다.**

## 6. Colab GPU + Drive 마운트

```python
!nvidia-smi
from google.colab import drive; drive.mount('/content/drive')
import torch; torch.cuda.is_available()
```

- **왜:** 이 노트북 GPU는 Intel Arc라 CUDA가 안 된다. 학습은 전부 Colab에서 한다.
- **막힌 것:** 없음.
- 배정된 GPU: **Tesla T4, 15360 MiB**, `CUDA 사용 가능: True`.
- Colab 쪽 버전: `ultralytics 8.4.115`(노트북과 동일), `torch 2.11.0+cu128`(노트북은 2.13.0 CPU — GPU 빌드라 다른 것이 정상).
- 데이터 저장 위치: `MyDrive/smart-factory-vision`. 런타임은 유휴 시 끊기고 그 안의 파일은 사라지므로 Drive에 둔다.
- 학습 스크립트는 만들지 않았다. **A등급(17번)이라 사용자가 직접 작성한다.**
