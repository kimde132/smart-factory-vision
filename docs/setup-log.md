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
