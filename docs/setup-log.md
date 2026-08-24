# 환경 구축 로그

> **C등급 작업 기록.** 항목당: 실행한 명령 / 왜 필요했나 / 막힌 것 / 해결 방법
> 목적은 두 가지다.
> 1. **재현성** — 교육장 PC나 새 노트북에서 다시 세팅할 때 이 로그가 전부다.
> 2. **면접 재료** — "환경 구축에서 뭐가 어려웠나요"는 실제로 나오는 질문이다.
>
> 항목 번호는 `work-grades.md` §4 의 번호를 따른다(실행 순서가 아니다).
>
> **개념 해설은 이 문서에 넣지 않는다.** C등급 규칙이다.
> 여기 나오는 것들이 각각 무엇이고 어떻게 연결되는지는 **[`foundations.md`](foundations.md)** 를 볼 것.

**작업일:** 2026-08-07 (프로젝트 1일차, 부품 배송 대기 중)

---

## 작업 시작 시점의 환경

| 항목 | 상태 |
|---|---|
| OS | Windows 11 Pro 26200 |
| git | 2.54.0.windows.1 (설치돼 있음, user.name/email 설정 완료) |
| Python | 3.13.14 (py 런처 등록) |
| winget | 1.29.280 |
| .NET SDK | 없음 |
| SQL Server / SSMS / ODBC 18 | 없음 |
| GPU | Intel Arc 130V — **CUDA 불가**, 학습은 Colab |
| C: 여유 공간 | 601 GB |

## 실제 실행 순서와 그 이유

문서의 번호 순서와 실제로 한 순서는 다르다.

```
1(git) → 7(폴더) → 3 설치 시작(백그라운드) → 2(가상환경) → 5(Label Studio)
       → 3 설정·검증 → 6(.NET/WPF) → 4(Colab, 사용자 병행) → 추가(GitHub)
```

- **1번을 무조건 맨 앞에** — 첫 커밋 전에 `.gitignore`가 있어야 한다. 이미지·모델이 히스토리에 한 번 들어가면 제거 비용이 크다.
- **3번(SQL Server)을 최대한 앞으로** — 다운로드가 오늘 가장 긴 단일 대기다. 먼저 걸어두고 그 시간에 2번을 진행했다. 그리고 실패 확률이 높은 작업은 **재시도할 시간이 남아 있을 때** 해야 한다. 실제로 4번 실패했으므로 이 판단이 맞았다.
- **3번의 검증만 2번 뒤로** — pyodbc가 설치돼 있어야 접속을 확인할 수 있다.
- **4번(Colab)은 사용자가 브라우저에서 병행** — 설치 대기 시간과 겹쳐 처리했다.

---

## 1. git 저장소 + `.gitignore`

```powershell
git init -b main
git config core.autocrlf true
git config core.quotepath false   # 한글 파일명이 \354\212... 로 깨져 보여서
```

- **왜:** 첫 커밋 전에 `.gitignore`를 넣어야 이미지·모델·`.env`가 히스토리에 한 번도 들어가지 않는다.
- **막힌 것:** `git check-ignore -v`가 부정 규칙(`!.env.example`)도 "매칭됨"으로 출력해서, 무시되는지 아닌지 판단할 수 없었다.
- **해결:** 실제 테스트 파일을 만들어 `git status --untracked-files=all --ignored=matching`으로 확정 검증. `.env`는 무시되고 `.env.example`은 추적되는 것을 확인한 뒤 테스트 파일을 지웠다.
- **부가:** `.gitattributes`에 `* text=auto`를 넣어 Windows CRLF 경고를 처리. `docs/images/`는 이미지 무시 규칙의 예외로 지정했다(README 스크린샷용).

## 2. Python 가상환경 + 패키지

```powershell
py -3.13 -m venv ai-server\.venv
ai-server\.venv\Scripts\python.exe -m pip install -r ai-server\requirements.txt
ai-server\.venv\Scripts\python.exe -m pip freeze > ai-server\requirements.lock.txt
```

- **왜:** 프로젝트 전용 패키지 공간. 시스템 파이썬을 오염시키지 않고, 다른 PC에서 같은 환경을 재현하기 위해서다.
- **막힌 것:** 없음. Python 3.13에 torch·ultralytics 휠이 없을 것을 우려했으나 기우였다. 3.12 강등은 불필요했다.
- 설치된 주요 버전: `ultralytics 8.4.115`, `torch 2.13.0`(CPU), `pyodbc 5.3.0`, `fastapi 0.141.1`, `sqlalchemy 2.0.51`, `pandas 3.0.5`. 총 62개.
- `requirements.txt`에는 **직접 import 하는 것만** 적고, `requirements.lock.txt`에 전체 버전을 고정했다.

## 3. SQL Server 2022 Developer + ODBC 18 + SSMS 21 + pyodbc 연결

> work-grades에서 "최우선으로 뚫는다"고 지정한 항목. 오늘 가장 오래 걸렸다.

### 3-1. 설치 방식 결정

```powershell
# 부트스트래퍼 내려받기 (SHA256이 winget 매니페스트 값과 일치하는지 확인)
Invoke-WebRequest -Uri "https://download.microsoft.com/download/c/c/9/.../SQL2022-SSEI-Dev.exe" -OutFile $out
# 매체를 받아 압축 해제 후, SETUP.EXE 에 옵션을 직접 넣어 무인 설치
SETUP.EXE /Q /ACTION=Install /FEATURES=SQLENGINE /INSTANCENAME=MSSQLSERVER `
  /SQLSYSADMINACCOUNTS="<컴퓨터명>\<계정>" /SECURITYMODE=SQL /SAPWD="..." `
  /TCPENABLED=1 /NPENABLED=0 /UPDATEENABLED=0 /IACCEPTSQLSERVERLICENSETERMS
```

- **왜:** 5주차에 SQL Server를 처음 만지면 며칠이 사라진다. 부품 배송 대기 중인 지금 뚫어둔다.
- **막힌 것:** `winget install Microsoft.SQLServer.2022.Developer`는 `SQL2022-SSEI-Dev.exe`(설치 마법사를 띄우는 부트스트래퍼)를 실행할 뿐이다. 마법사의 "기본 설치"를 고르면 **Windows 인증 전용**으로 깔려서, 혼합 모드 전환과 TCP/IP 활성화를 나중에 손으로 해야 한다.
- **해결:** 마법사를 쓰지 않고 `/ACTION=Download`로 매체를 받아 `SETUP.EXE`에 옵션을 직접 넣었다. 핵심은 두 개다.
  - `/SECURITYMODE=SQL` + `/SAPWD=...` → 혼합 모드 인증을 **설치 시점에** 켠다
  - `/TCPENABLED=1` → TCP/IP를 **설치 시점에** 켠다 (pyodbc 접속의 전제 조건)
- 그 외: `/FEATURES=SQLENGINE`(엔진만), `/INSTANCENAME=MSSQLSERVER`(기본 인스턴스 → `localhost`로 접속), `/NPENABLED=0`, `/IACCEPTSQLSERVERLICENSETERMS`.
- 관리자 권한이 필요해 UAC 승인 창을 사용자가 직접 눌렀다.

**이 결정의 효과:** work-grades와 계획서가 예상했던 최대 난관 세 가지(혼합 모드 인증 / TCP/IP 활성화 / ODBC 암호화)가 **한 건도 발생하지 않았다.** 설치 후에 손으로 고치는 대신 설치 명령에 넣었기 때문이다.

### 3-2. 여기서 4번 연속으로 막혔다 (실패 기록)

실패마다 증상이 달라서 원인을 하나씩 분리해야 했다.

| # | 증상 | 원인 | 해결 |
|---|---|---|---|
| 1 | `SETUP.EXE`가 **1초 만에** 종료 코드 `-2067529714`(0x84C4000E). 설치 로그 폴더조차 안 생김 | 매체 경로가 **151자**. SQL Server 매체 안의 깊은 하위 경로와 합쳐져 Windows 260자 한계를 넘김 | 매체를 `C:\Users\kimde\sqlmedia`(22자)로 옮겨 설치. 경로 길이 35자로 축소 |
| 2 | 관리자 권한 스크립트가 UAC 승인 후에도 아무 일 없이 종료. 로그 파일조차 안 생김 | **Windows PowerShell 5.1은 BOM 없는 `.ps1`을 UTF-8이 아니라 CP949로 읽는다.** 한글 주석 바이트가 깨지면서 그중 하나가 따옴표로 해석돼 문법 오류 5건 발생 | 임시 스크립트를 **ASCII 전용**으로 재작성. 이후 실행 전에 `[Parser]::ParseFile`로 문법 검사를 먼저 통과시키는 절차를 추가 |
| 3 | 설치가 3분간 진행되다 로그가 **문장 중간에서 끊김**. 오류 메시지 없음 | 설치를 감싼 **관리자 권한 PowerShell 콘솔 창이 닫히면서** 그 안의 `setup.exe`가 함께 강제 종료됨 | PowerShell로 감싸지 않고 `SETUP.EXE`를 `-Verb RunAs`로 **직접** 실행. 콘솔 창이 없으니 닫힐 일도 없음 |
| 4 | 재시도 시 24초 만에 실패. `Exit message: 시스템 데이터베이스 파일 master.mdf이(가) 이미 ...DATA에 있습니다` | 3번에서 강제 종료된 반쪽 설치가 시스템 DB 파일을 남겨둠. SQL Server는 그 위에 덮어쓰지 않는다 | `SETUP.EXE /ACTION=Uninstall /FEATURES=SQLENGINE /INSTANCENAME=MSSQLSERVER`로 제거(종료 코드 0, 서비스·폴더 모두 정리됨) 후 재설치 |

**여기서 얻은 것:** 설치 프로그램이 로그를 **아예 안 남기면** 인자 파싱 이전 단계에서 죽은 것이고(경로·권한 문제), **문장 중간에서 끊기면** 외부에서 강제 종료된 것이다. 오류 메시지 없이 끝나는 두 경우를 구분하는 기준이 된다.

### 3-3. 최종 설치 결과

```
Final result: 통과 / Exit code: 0
MSSQLSERVER 서비스: Running (자동 시작)
TCP 1433 포트: 수신 중
```

- SQL Server 2022 (RTM) 16.0.1000.6 (X64), Developer 에디션, 기본 인스턴스.
- **ODBC Driver 18은 winget으로 따로 깔 필요가 없었다.** SQL Server 설치 시 필수 구성 요소로 함께 설치된다(설치 로그에 `msodbcsql_Cpu64_1.log`).
- SSMS 21, ODBC 18(최신 버전으로 갱신), .NET SDK 10은 winget으로 설치했다.
- **에디션 선택:** Developer는 무료이면서 기능 제한이 없다. Express는 DB 10GB 제한이 있고, LocalDB는 TCP/IP 설정 실습이 아예 불가능해 이 프로젝트의 학습 포인트가 사라진다.

### 3-4. DB 초기 설정 + pyodbc 접속 검증

```sql
-- Windows 인증(현재 계정 = sysadmin)으로 접속해 실행
CREATE DATABASE [smart_factory_vision]
CREATE LOGIN [sfv_app] WITH PASSWORD = N'...', DEFAULT_DATABASE = [smart_factory_vision], CHECK_POLICY = ON
CREATE USER [sfv_app] FOR LOGIN [sfv_app]
ALTER ROLE db_owner ADD MEMBER [sfv_app]   -- 이 DB 안에서만 유효한 권한
ALTER LOGIN [sa] DISABLE
```

- **왜 sa를 안 쓰는가:** `sa`는 서버 전체 최고 권한이라 공격 표적이 된다. 애플리케이션에는 **자기 DB 안에서만** 권한을 갖는 전용 로그인을 준다. `db_owner`를 준 이유는 Alembic이 마이그레이션으로 테이블을 만들어야 하기 때문이다.
- **왜 sa를 꺼도 안전한가:** 설치 시 `/SQLSYSADMINACCOUNTS`로 Windows 계정을 sysadmin에 넣었으므로, 문제가 생겨도 Windows 인증으로 들어갈 수 있다.
- **막힌 것:** 없음. ODBC 18의 암호화 기본값 문제는 `.env`에 `TrustServerCertificate=yes`를 미리 넣어 예방했다.

**검증 결과** (`ai-server/check_db.py`):

```
[성공] 접속됐습니다.
  서버 버전  : Microsoft SQL Server 2022 (RTM) - 16.0.1000.6 (X64)
  현재 DB    : smart_factory_vision
  현재 로그인 : sfv_app
```

- 접속 정보는 `ai-server/.env`에만 있고, git이 무시하는 것을 `git status --ignored`로 확인했다.
- `check_db.py`는 실패 시 오류 코드를 보고 원인을 한국어로 알려준다(IM002 드라이버 없음 / SSL 인증서 / 18456 로그인 실패 / 4060 DB 없음 / 08001 접속 불가).

## 4. Colab GPU 확인 + Drive 마운트

```python
!nvidia-smi
from google.colab import drive; drive.mount('/content/drive')
import torch; torch.cuda.is_available()
```

- **왜:** 이 노트북 GPU는 Intel Arc라 CUDA가 안 된다. 학습은 전부 Colab에서 한다. 5주차에 처음 열어보고 GPU 배정이 안 되는 것을 발견하면 늦다.
- **막힌 것:** 없음.
- 배정된 GPU: **Tesla T4, 15360 MiB**, `CUDA 사용 가능: True`.
- Colab 쪽 버전: `ultralytics 8.4.115`(노트북과 동일), `torch 2.11.0+cu128`(노트북은 2.13.0 CPU — GPU 빌드라 다른 것이 정상).
- 데이터 저장 위치: `MyDrive/smart-factory-vision`. 런타임은 유휴 시 끊기고 그 안의 파일은 사라지므로 반드시 Drive에 둔다.
- 학습 스크립트는 만들지 않았다. **A등급(17번)이라 사용자가 직접 작성한다.**

## 5. 라벨링 도구 (Label Studio)

```powershell
py -3.13 -m venv .venv-labelstudio
.venv-labelstudio\Scripts\python.exe -m pip install label-studio
```

- **왜 이 도구인가:** pip로 설치되고 현재도 유지보수된다. labelImg는 아카이브 상태라 Python 3.13에서 PyQt5 설치가 실패할 위험이 있었다.
- **왜 가상환경을 분리했나:** 라벨링 도구와 학습 코드는 같이 실행할 일이 없고, 의존성이 충돌할 수 있다.
- **분리가 옳았던 근거:** Label Studio가 의존성으로 `psycopg`(PostgreSQL 드라이버)를 끌고 왔다. 이 프로젝트는 MSSQL을 쓰므로 같은 환경에 섞였으면 혼란스러웠을 것이다.
- **막힌 것:** 없음. `label-studio 1.23.0` 설치 성공.
- 프로젝트 생성과 라벨링 규칙 설정은 하지 않았다. ~~**A등급(11·12번)이라 사용자가 직접 한다.**~~
- **2026-08-23에 바꿨다** — 도구 세팅(실행·프로젝트 생성·클래스 등록·이미지 불러오기)은 **C등급으로 Claude가 하고 사용자는 보면서 익힌다.** 사용자 요청이다: *"나도 뭔지도 모르고 어떻게 하는건지 몰라서 너 하는거 좀 보면서 공부도 해야할 것 같다."* **박스를 그리는 것부터(#12)는 그대로 A등급**이라 사용자가 직접 한다. 도구 조작과 라벨링 판단을 나눈 것이다.

### 5-1. 프로젝트 세팅 — 2026-08-24

```powershell
.\scripts\start_labelstudio.ps1        # 서버 실행. 앞으로 라벨링할 때마다 이것만 실행한다
# 브라우저 http://localhost:8080 → 회원가입 → Create Project → Labeling Setup 에 XML 붙여넣기
# → Settings → Cloud Storage → Add Source Storage (Local files) → Sync
```

- **왜:** #12 라벨링 실작업의 입력 준비. s01 35장을 도구에 물리고 클래스 3개를 등록했다.
- **왜 스크립트를 만들었나:** 설정을 환경 변수로 넘기는데, 환경 변수는 **그 프로세스에만** 붙는다. 다음에 그냥 `label-studio start`로 켜면 로컬 파일 서빙이 꺼져서 **사진이 전부 깨져 보이고 원인을 찾기 어렵다.** `.ps1`은 UTF-8 **BOM 포함**으로 저장했다(3-2 실패 #2와 같은 CP949 문제 방지). 저장 후 `[Parser]::ParseFile`로 구문 검사를 통과시켰다.

**설정한 값**

| 항목 | 값 | 이유 |
|---|---|---|
| 라벨링 설정 | `RectangleLabels` — `bolt` → `nut` → `washer` 순 | **XML의 라벨 순서가 그대로 클래스 번호(0/1/2)가 된다.** 클릭으로 3개를 넣는 것보다 순서를 눈으로 확인할 수 있다 |
| `hotkey="1,2,3"` | 숫자키 단축키 | 350장을 마우스로만 고를 수 없다. **번호(0,1,2)와 무관한 별개 개념** |
| `zoom`·`zoomControl` | 켬 | 너트/와셔 외곽선(육각 vs 원) 판별에 확대가 필수 |
| `rotateControl` | 끔 | 탑뷰 고정. 잘못 눌러 회전하면 박스가 틀어진다 |
| 스토리지 종류 | `Local files` | 업로드하면 사진 350장이 Label Studio 폴더에 **한 벌 더 복사된다.** 원본을 `dataset/rename/` 하나로 유지 |
| 경로 | `dataset\rename` + `Scan all sub-folders` ON | 하위를 훑으므로 s02~s10을 찍어도 **`Sync` 한 번**이면 추가된다. 세션마다 스토리지를 새로 만들 필요가 없다 |
| Import method | `Files` | `Tasks`(JSON)로 두면 JPG를 JSON으로 파싱하려다 0장이 들어온다 |
| File Filter Regex | `.*\.jpg` | 같은 폴더의 `_rename_map.csv`가 라벨링 대상으로 끌려오는 것을 막는다 |

**막힌 것과 해결**

| # | 증상 | 원인 | 해결 |
|---|---|---|---|
| 1 | 스토리지 경로 저장 시 `cannot be the same as LOCAL_FILES_DOCUMENT_ROOT ... Please add a subdirectory` | 울타리(document root)와 스토리지 경로가 **똑같으면 거부**한다. 울타리가 곧 대상이면 울타리 역할을 못 하므로 | 울타리를 한 칸 위 `dataset`로 옮기고 서버 재시작. 스토리지 경로는 `dataset\rename` 유지 → 한 칸 차이 확보 |
| 2 | 스크립트에서 `SECRET_KEY`를 직접 만들어 넘겼더니 열쇠가 두 개가 됨 | **Label Studio가 이미 스스로 처리하고 있었다.** 첫 실행 때 만들어 `%LOCALAPPDATA%\label-studio\label-studio\.env`에 저장하고 이후 재사용한다. 첫 실행 로그의 `Will generate a random key` 경고를 "매번 그런다"고 잘못 읽은 것 | 스크립트에서 해당 블록 삭제, `.secret_key` 파일 제거. **도구가 이미 하는 일인지 먼저 확인할 것** |
| 3 | 만든 `.ps1`을 사용자가 직접 실행하면 *"이 시스템에서 스크립트를 실행할 수 없으므로..."* 로 막힌다 | Windows 기본 **실행 정책이 `Restricted`**(스크립트 실행 전면 금지). Claude가 실행할 때는 도구가 `Process` 범위를 `Bypass`로 띄워서 통과했을 뿐이라 **증상이 드러나지 않았다** | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (1회). 내가 만든 로컬 스크립트는 허용, 인터넷에서 받은 것은 서명 필요. `-Scope CurrentUser`라 관리자 권한 불필요. 새 창에서 `RemoteSigned`로 나오는 것과 스크립트에 Zone.Identifier(인터넷 표식)가 없는 것을 확인했다 |

**검증** — YOLO 형식으로 내보내 파일로 확인했다. 눈대중이 아니라 증거를 남긴다.

```
classes.txt              notes.json
──────────               ─────────────────────────
bolt      ← 0번          { "id": 0, "name": "bolt"   }
nut       ← 1번          { "id": 1, "name": "nut"    }
washer    ← 2번          { "id": 2, "name": "washer" }
```

`labeling-guide.md` 1-1 표와 일치. status.md의 ⭐ 리스크는 여기서 닫혔다.

**⚠️ 이때 발견한 것 — 라벨 파일명은 규칙대로 나오지 않는다**

```
labels/9599f483__rename%5Cs01%5Cs01_001.txt      ← 기대: s01_001.txt
```

로컬 폴더 연결을 고른 이유 중 하나가 "업로드하면 파일명 앞에 해시가 붙는다"였는데, **로컬 연결도 붙는다.** `9599f483__`는 중복 방지 해시, `%5C`는 역슬래시를 URL 문자로 바꾼 것이라 폴더 경로가 이름에 통째로 들어간다. 다만 **원래 이름이 그 안에 그대로 있어** 되돌리는 것은 기계적으로 가능하다.

되돌리는 곳은 **#14 분할 스크립트**다. 어차피 라벨을 `result_data/labels/{train,val,test}/`로 옮기며 사진과 짝을 맞춰야 하므로 그때 정규화한다. 새 스크립트를 만들지 않는다. (로컬 연결 선택 자체는 유지 — 사진 중복 복사가 없고 세션 추가가 `Sync` 한 번이라는 이유는 그대로 유효하다.)

> `images/` 폴더는 비어 있다. 로컬 연결이라 Label Studio가 사진 원본을 갖고 있지 않아서이며 정상이다. 사진은 `dataset/rename/`에 있다.

## 6. .NET SDK + WPF 빈 프로젝트

```powershell
winget install --id Microsoft.DotNet.SDK.10 --silent
dotnet new wpf -o wpf-client -n SmartFactoryVision.Client
dotnet build wpf-client\SmartFactoryVision.Client.csproj
```

- **왜:** 3주차에 WPF를 시작할 때 환경 문제로 며칠 날리지 않으려고 **빌드가 되는지만** 지금 확인해 둔다. 화면 구현은 하지 않았다.
- **막힌 것:** 없음.
- 결과: `net10.0-windows`, 빌드 **경고 0개 / 오류 0개**.
- `bin/`, `obj/`가 `.gitignore`로 제외되는 것을 `git status --ignored`로 확인했다.
- 실제 소스 파일이 생겼으므로 `ai-server/.gitkeep`, `wpf-client/.gitkeep`은 제거했다.

## 7. 폴더 구조 스캐폴딩

```powershell
foreach ($d in 'ai-server','wpf-client','dataset','models','storage') { New-Item -ItemType Directory -Force $d }
New-Item -ItemType File ai-server\.gitkeep, wpf-client\.gitkeep
```

- **왜:** 이후 산출물(가상환경, `.env`, 연결 테스트 스크립트, WPF 프로젝트)이 놓일 자리를 먼저 만든다.
- **막힌 것:** 없음.
- **참고:** git이 빈 폴더를 추적하지 않아 `.gitkeep`이 필요하지만, `dataset`·`models`·`storage`는 `.gitignore` 대상이라 넣지 않았다(넣어도 무시되어 혼란만 준다).
- CLAUDE.md의 폴더 구조에는 `smart-factory-vision-inspection`으로 적혀 있으나 실제 폴더명은 `smart-factory-vision`. **폴더명을 유지하고 문서 표기를 맞추기로 했다**(rename은 되돌리기 비용만 발생).

## 추가. GitHub 원격 저장소

> work-grades §4에는 없는 항목. 백업과 이력 보존을 위해 추가했다.

```powershell
# 처음 계획: gh CLI 로 저장소 생성 → 실패, 아래 참고
winget install --id GitHub.cli --silent      # gh 2.97.0 설치 자체는 성공

# 실제로 한 방법: GitHub 웹에서 저장소를 만들고 로컬에 연결
git remote add origin https://github.com/kimde132/smart-factory-vision.git
git push -u origin main
```

- **막힌 것:** `gh` 설치는 성공했는데 **이미 열려 있던 셸에서 `gh` 명령을 찾지 못했다**(`command not found`). 설치 프로그램이 시스템 PATH를 갱신해도 **이미 실행 중인 셸은 시작할 때의 PATH를 그대로 들고 있기 때문**이다.
- **해결:** 전체 경로(`"C:\Program Files\GitHub CLI\gh.exe"`)로 실행하거나 새 터미널을 열면 되지만, `gh auth login`은 어차피 대화형 브라우저 인증이라 자동화할 수 없다. 그래서 **GitHub 웹에서 저장소를 직접 만들고** `git remote add` + `git push`로 연결했다. 인증은 Git for Windows에 포함된 Git Credential Manager가 처리했다.
- **비공개로 시작한 이유:** 공개로 한 번 올린 내용은 포크·캐시로 남아 되돌리기 어렵다. 비공개 → 공개는 언제든 단추 하나다.

**push 전 안전 점검** — `git status --ignored`는 "지금 무시되는가"만 본다. push는 **히스토리 전체**를 올리므로 히스토리 기준으로 다시 확인했다.

```powershell
git ls-files                                        # 현재 추적 중인 파일 전체
git log --all --diff-filter=A --name-only           # 과거 커밋에 추가된 적 있는 모든 파일
git grep '<실제 비밀번호>' $(git rev-list --all)     # 모든 커밋 내용에서 비밀번호 검색
```

결과: `.env`는 히스토리에 한 번도 없었고, 비밀번호 문자열도 발견되지 않았다. `.env.example`에 값이 있는 항목은 `localhost`, `1433`, 드라이버 이름 등 비밀이 아닌 기본값뿐이다.

**push 후 검증:** 로컬 `main`과 원격 `main`이 같은 커밋을 가리키고, 원격 파일 20개 중 `.env`가 없음을 `git ls-tree -r origin/main`으로 확인했다.

---

## 정리한 임시 파일

SQL Server 설치에 쓴 매체(`C:\Users\kimde\sqlmedia`, 압축본 1.2GB + 압축 해제본 포함 총 2.49GB)는
설치와 동작 확인이 끝난 뒤 삭제했다. C: 여유 공간 589.1 GB → 591.5 GB.
재설치가 필요하면 `SQL2022-SSEI-Dev.exe`를 다시 받으면 된다.

## 추가. 촬영 메타데이터 폴더 (`metadata/`) — 2026-08-18

```powershell
# 폴더와 파일 3개 생성 (헤더 한 줄씩)
metadata/sessions.csv    # session_id,camera_angle,camera_height_cm,frame_width_cm,device,lighting,tray,date
metadata/images.csv      # image_name,bolt_count,nut_count,washer_count,layout
metadata/README.md       # 두 파일의 역할·컬럼 뜻·적는 방법
```

- **왜 필요했나:** work-grades #15 촬영 메타데이터를 기록할 곳. 컬럼은 D-009 6절에서 사용자가 확정했고, 폴더·헤더 생성만 C등급으로 처리했다.
- **왜 `dataset/` 밖인가:** `.gitignore`가 `dataset/`을 통째로 제외한다. CSV는 실패 분석(#21)의 유일한 근거라 git에 남아야 한다.
- **막힌 것:** 없음.

## 추가. `dataset/` 폴더 + 이름 변경 스크립트 — 2026-08-19

```powershell
# D-009 Q17 구조 그대로 생성
dataset/{origin,rename}, dataset/result_data/{images,labels}/{train,val,test}

# 미리보기 → 실제 복사
ai-server\.venv\Scripts\python.exe scripts\rename_session.py s01
ai-server\.venv\Scripts\python.exe scripts\rename_session.py s01 --apply
```

- **왜 필요했나:** s01 35장의 카메라 파일명(`IMG_E8821.JPG`)을 규칙(`s01_001.jpg`)으로 바꿔야 라벨링에 넣을 수 있다. D-009 Q22에서 스크립트로 하기로, 등급은 C로 정했다.
- **왜 파일 시각이 아니라 EXIF인가:** 파일 수정 시각은 PC로 옮기는 순간 "옮긴 시각"으로 바뀐다. EXIF 촬영 시각은 사진 안에 있어 복사해도 그대로다.
- **막힌 것:** 첫 실행이 `UnicodeEncodeError`로 죽었다. 윈도우 콘솔 CP949가 em dash(—)를 출력하지 못했다.
- **해결:** 출력 문자를 바꾸고 `sys.stdout.reconfigure(errors="replace")` 추가. `scripts/` 폴더는 이때 새로 만들었다(계획 구조에 없던 것).

## 오늘 하지 않은 것 (의도적)

| 항목 | 이유 |
|---|---|
| 촬영 환경 설계, 파일럿 촬영 | A등급(8·9번). 부품이 있어야 하고, 사용자가 직접 판단 |
| 라벨링 규칙 정의, 라벨링 실작업 | A등급(11·12번) |
| YOLO 학습 스크립트 | A등급(17번) |
| FastAPI 엔드포인트, DB 테이블 설계, Alembic 마이그레이션 | 이후 주차 |
| WPF 화면 구현 | 3주차 |
| README 작성 | 프로젝트가 모양을 갖춘 뒤 |
