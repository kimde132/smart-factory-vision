# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  start_labelstudio.ps1 — 라벨링 도구(Label Studio) 서버를 항상 똑같은 설정으로 켜는 PowerShell 스크립트   ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  설정 두 가지를 환경 변수로 넘긴 뒤, 가상환경의 python.exe 로 Label Studio 를 실행한다.
# │  (2026-09-10 까지는 label-studio.exe 를 썼다. 바꾼 이유는 아래 3번)
# │
# │  누가 호출하나   : 사람. 라벨링 작업(work-grades #12)을 시작할 때마다 직접 실행한다.
# │  무엇을 호출하나 : .venv-labelstudio\Scripts\python.exe (label_studio.server 의 main 함수)
# │  이 서버가 뜬 뒤 브라우저로 http://localhost:8080 에 접속해서 라벨링한다.
# │
# │  켜기 : PowerShell 에서  .\scripts\start_labelstudio.ps1        끄기 : 그 창에서 Ctrl + C
# │  ★ label-studio start 로 그냥 켜지 말 것. 환경 변수가 없으면 로컬 파일 서빙이 꺼져 사진이 전부 깨져 보인다(상태판 2절).
# │
# │  실행 순서: 위에서 아래로 한 번. 경로 계산 → 환경 변수 2개 → python.exe 확인 → 안내 출력 → 서버 실행(이 줄에서 멈춰 있다가 Ctrl+C 로 끝)
# │
# ├ 1. 이름은 세 종류 (PowerShell 판) ─────────────────────────────────────────────────────
# │
# │  ① PowerShell 문법     : $변수  $env:이름  if (…) { … }  -not  &(호출 연산자)  "…"(문자열, $ 가 안에서 풀린다)
# │  ② 남이 정한 이름
# │       Split-Path -Parent  Join-Path  Test-Path  Write-Host  Write-Error  exit   ← PowerShell 내장 명령(cmdlet). 동사-명사 꼴
# │       $PSScriptRoot                                                        ← PowerShell 자동 변수
# │       LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED  LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT  ← Label Studio 가 정한 환경 변수 이름
# │       label_studio.server  main  start  --port                             ← Label Studio 패키지가 정한 것
# │  ③ 내가 지은 이름       : $projectRoot  $python  .venv-labelstudio(가상환경 폴더 이름)  8080(포트)
# │
# ├ 2. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  환경 변수  : 프로그램 밖에서 설정을 넘기는 방법. 남의 프로그램은 소스를 고칠 수 없으므로 이렇게 밖에서 스위치를 켠다.
# │              문제는 넘긴 값이 "그 프로세스에만" 붙는다는 것. 창을 닫으면 사라지므로 매번 다시 넘겨야 하고, 그래서 이 스크립트가 존재한다.
# │              Python 의 os.environ / .env 와 같은 개념. PowerShell 에서는 $env:이름 = "값".
# │  cmdlet     : PowerShell 의 내장 명령. 동사-명사(Split-Path, Join-Path) 꼴. Python 의 내장 함수에 해당.
# │  Label Studio 는 라이브러리가 아니라 완성된 웹 애플리케이션이다. import 하지 않고 실행만 한다. 서버(Django)가 뜨고 브라우저로 쓴다.
# └────────────────────────────────────────────────────────────────────────────────────────

# ▸ 단어 분해: $projectRoot(③ 변수. PowerShell 변수는 $ 로 시작) =(대입) Split-Path(② cmdlet: 경로 자르기) -Parent(② 옵션: 한 단계 위) $PSScriptRoot(② 자동 변수: 이 .ps1 이 놓인 폴더)
# ▸ 뜻: scripts\ 의 위 = 프로젝트 루트. 어느 폴더에서 실행하든 경로가 어긋나지 않게. Python 의 Path(__file__).parent.parent 와 같은 일.
$projectRoot = Split-Path -Parent $PSScriptRoot

# ── 1. 로컬 파일 서빙 스위치 ──────────────────────────────────────────────────────────
# ▸ 단어 분해: $env:(① 환경 변수 접두어)LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED(② Label Studio 가 정한 이름) = "true"(문자열. 환경 변수는 항상 글자)
# ▸ 뜻: 브라우저가 내 PC 안의 이미지 파일을 직접 읽는 것을 허용한다.
# ▸ 왜: 기본값은 꺼짐(보안상 위험한 동작이므로). 꺼져 있으면 사진 목록은 들어오지만 라벨링 화면에서 이미지가 전부 깨져 보인다. 증상만 보고는 원인을 찾기 어렵다.
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"

# ── 2. 읽어도 되는 폴더의 울타리 ──────────────────────────────────────────────────────
# ▸ 단어 분해: $env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = Join-Path(② cmdlet: 경로 두 조각 잇기) $projectRoot "dataset"
# ▸ 뜻: 읽을 수 있는 범위를 <프로젝트>\dataset 아래로 제한한다. 위 스위치를 켜면 무엇이든 읽을 수 있게 되므로 울타리가 필요하다.
# ▸ 주의: Label Studio 는 이 울타리와 "똑같은" 경로를 스토리지로 등록하는 것을 거부한다(울타리 역할을 못 하므로). 반드시 하위 폴더여야 한다.
#   그래서 울타리는 dataset, 실제 스토리지 경로는 dataset\rename · dataset\crop 으로 한 칸 차이를 뒀다.
# ▸ 왜 Join-Path: 문자열 + 로 이으면 \ 를 빠뜨리기 쉽다. Join-Path 가 구분자를 알아서 넣는다. Python 의 Path / 와 같다.
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = Join-Path $projectRoot "dataset"

# ── 3. 서버 실행 ──────────────────────────────────────────────────────────────────────
#
# ▸ 참고: 세션 암호 열쇠(SECRET_KEY)는 여기서 건드리지 않는다.
#   SECRET_KEY 는 Django(Label Studio 의 토대가 되는 웹 프레임워크)가 "이 브라우저는 로그인한 사람이 맞다" 는 표에 서명할 때 쓰는 비밀 값.
#   값이 바뀌면 이전에 발행한 표가 전부 무효가 되어 다시 로그인해야 한다.
#   Label Studio 는 첫 실행 때 이 값을 스스로 만들어 %LOCALAPPDATA%\label-studio\label-studio\.env 에 저장해두고 이후 계속 재사용한다.
#   여기서 따로 넘기면 열쇠가 두 개가 되어 어느 쪽이 이기는지 애매해지므로 넘기지 않는다.
#
# ▸ 2026-09-10 변경: label-studio.exe 대신 python.exe 로 띄운다 (setup-log.md 5-2).
#   label-studio.exe 는 pip 가 만든 "실행기" 일 뿐이고, 실제 일은 label_studio.server 의 main() 이 한다.
#   이 실행기는 서명이 없어서 Windows 11 의 Smart App Control(서명 없는 프로그램을 막는 기능)이 차단했다.
#   가상환경의 python.exe 는 Python Software Foundation 서명이 있어 통과하므로, python.exe 가 main() 을 직접 부르게 한다. 하는 일은 label-studio.exe 와 완전히 같다.
#   (9/18 에 Smart App Control 을 껐지만 이 방식도 정상이라 그대로 둔다)
# ▸ 단어 분해: $python(③) = Join-Path $projectRoot ".venv-labelstudio\Scripts\python.exe"
# ▸ .venv-labelstudio : ai-server\.venv 와 별개의 가상환경. Label Studio 의 의존성이 ultralytics 와 충돌할 수 있어 따로 뒀다.
$python = Join-Path $projectRoot ".venv-labelstudio\Scripts\python.exe"

# ▸ 단어 분해: if(①) ( -not(① 아니면) (Test-Path(② cmdlet: 경로가 있나) $python) ) {(① 블록 시작)
# ▸ 뜻: python.exe 가 없으면 안내하고 끝낸다. Python 의 if not path.exists(): 와 같다.
if (-not (Test-Path $python)) {
    # ▸ Write-Error(② cmdlet): 오류 스트림에 빨간 글자로 출력. Write-Host 와 달리 "오류" 로 분류된다.
    Write-Error "가상환경의 python.exe 를 찾을 수 없습니다 : $python"
    Write-Error "가상환경이 없다면 docs/setup-log.md 5번을 보고 다시 만드세요."
    # ▸ exit 1(① 종료 코드 1): 종료 코드를 남겨야 나중에 다른 스크립트가 이것을 호출했을 때 실패했다는 것을 알아챌 수 있다. 0 은 성공, 0 이 아니면 실패라는 것이 공통 약속. Python 의 sys.exit(1).
    exit 1
}

# ▸ Write-Host(② cmdlet): 화면에 글자 출력. Python 의 print. "…" 안의 $env:… 는 값으로 바뀐다(문자열 보간. Python 의 f-string 이 기본).
Write-Host ""
Write-Host "Label Studio 를 시작합니다."
Write-Host "  읽기 허용 폴더 : $env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT"
Write-Host "  주소           : http://localhost:8080"
Write-Host "  끄기           : 이 창에서 Ctrl + C"
Write-Host ""

# ▸ 단어 분해: &(① 호출 연산자) $python(실행 파일 경로) -c(② python 옵션: 뒤의 글자를 코드로 실행) "from label_studio.server import main; main()"(파이썬 한 줄) start(② Label Studio 명령) --port(② 옵션) 8080(③ 포트)
# ▸ 뜻: python.exe 로 "label_studio.server 의 main() 을 불러라" 를 실행하고, main() 은 뒤에 붙은 인자(start --port 8080)를 그대로 읽는다. label-studio.exe start --port 8080 과 같다.
# ▸ 왜 &: 경로가 담긴 변수를 실행 파일로 돌릴 때 필요하다. & 없이 $python 만 쓰면 PowerShell 은 그것을 "문자열" 로 보고 화면에 출력만 한다.
# ▸ 다른 선택: --port 8081 로 바꾸면 주소가 localhost:8081. 8000 은 FastAPI(uvicorn)가 쓰므로 겹치면 안 된다.
& $python -c "from label_studio.server import main; main()" start --port 8080
