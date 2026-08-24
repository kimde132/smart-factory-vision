# ============================================================
# start_labelstudio.ps1 - 라벨링 도구(Label Studio) 서버를 켜는 스크립트
#
# [이 파일은 무엇을 하는가]
#   Label Studio 서버를 항상 똑같은 설정으로 켠다.
#   설정 세 가지를 환경 변수로 넘긴 뒤 label-studio.exe 를 실행한다.
#
# [실행 흐름에서 어느 위치인가]
#   누가 호출하나   : 사람. 라벨링 작업(work-grades #12)을 시작할 때마다 직접 실행한다.
#   무엇을 호출하나 : .venv-labelstudio\Scripts\label-studio.exe
#   이 서버가 뜬 뒤 브라우저로 http://localhost:8080 에 접속해서 라벨링한다.
#
# [이 파일을 이해하기 전에 알아야 할 개념]
#   - 환경 변수 : 프로그램 밖에서 설정을 넘기는 방법. 남의 프로그램은 소스를 고칠 수 없으므로
#     이렇게 밖에서 스위치를 켠다. 문제는 넘긴 값이 "그 프로세스에만" 붙는다는 것이다.
#     창을 닫으면 사라지므로 매번 다시 넘겨야 하고, 그래서 이 스크립트가 존재한다.
#   - Label Studio 는 라이브러리가 아니라 완성된 웹 애플리케이션이다. import 하지 않고 실행만 한다.
#
# [사용법]
#   켜기 : PowerShell 에서  .\scripts\start_labelstudio.ps1
#   끄기 : 그 창에서 Ctrl + C
# ============================================================

# $PSScriptRoot : 이 .ps1 파일이 놓인 폴더의 절대 경로. PowerShell 이 자동으로 채워주는 변수다.
# Split-Path -Parent : 경로에서 한 단계 위를 구한다. scripts\ 의 위 = 프로젝트 루트.
# 어느 폴더에서 실행하든 경로가 어긋나지 않게 하려고 이렇게 구한다.
$projectRoot = Split-Path -Parent $PSScriptRoot

# --- 1. 로컬 파일 서빙 스위치 ---
# 브라우저가 내 PC 안의 이미지 파일을 직접 읽는 것을 허용한다. 기본값은 꺼짐이다(보안상 위험한 동작이므로).
# 이것이 꺼져 있으면 사진 목록은 들어오지만 라벨링 화면에서 이미지가 전부 깨져 보인다.
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"

# --- 2. 읽어도 되는 폴더의 울타리 ---
# 위 스위치를 켜면 무엇이든 읽을 수 있게 되므로, 읽을 수 있는 범위를 이 폴더 아래로 제한한다.
# 주의 : Label Studio 는 이 울타리와 "똑같은" 경로를 스토리지로 등록하는 것을 거부한다(울타리 역할을 못 하므로).
# 반드시 하위 폴더여야 한다. 그래서 울타리는 dataset, 실제 스토리지 경로는 dataset\rename 으로 한 칸 차이를 뒀다.
# Join-Path : 경로 두 조각을 구분자(\)를 알아서 넣어 이어붙인다. 문자열 + 로 이으면 \ 를 빠뜨리기 쉽다.
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = Join-Path $projectRoot "dataset"

# --- 3. 서버 실행 ---
#
# 참고 : 세션 암호 열쇠(SECRET_KEY)는 여기서 건드리지 않는다.
#   SECRET_KEY 는 Django(Label Studio 의 토대가 되는 웹 프레임워크)가
#   "이 브라우저는 로그인한 사람이 맞다"는 표에 서명할 때 쓰는 비밀 값이다.
#   값이 바뀌면 이전에 발행한 표가 전부 무효가 되어 다시 로그인해야 한다.
#   Label Studio 는 첫 실행 때 이 값을 스스로 만들어
#   %LOCALAPPDATA%\label-studio\label-studio\.env 에 저장해두고 이후 계속 재사용한다.
#   여기서 따로 넘기면 열쇠가 두 개가 되어 어느 쪽이 이기는지 애매해지므로 넘기지 않는다.
$labelStudio = Join-Path $projectRoot ".venv-labelstudio\Scripts\label-studio.exe"

if (-not (Test-Path $labelStudio)) {
    # exit 1 까지 하는 이유 : 종료 코드 1 을 남겨야 나중에 다른 스크립트가 이것을 호출했을 때
    # 실패했다는 것을 알아챌 수 있다. 0 은 성공, 0 이 아니면 실패라는 것이 공통 약속이다.
    Write-Error "label-studio.exe 를 찾을 수 없습니다 : $labelStudio"
    Write-Error "가상환경이 없다면 docs/setup-log.md 5번을 보고 다시 만드세요."
    exit 1
}

Write-Host ""
Write-Host "Label Studio 를 시작합니다."
Write-Host "  읽기 허용 폴더 : $env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT"
Write-Host "  주소           : http://localhost:8080"
Write-Host "  끄기           : 이 창에서 Ctrl + C"
Write-Host ""

# & : 호출 연산자(call operator). 경로가 담긴 변수를 실행 파일로 돌릴 때 필요하다.
# & 없이 $labelStudio 만 쓰면 PowerShell 은 그것을 "문자열"로 보고 화면에 출력만 한다.
& $labelStudio start --port 8080
