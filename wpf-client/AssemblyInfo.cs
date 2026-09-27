/*
  ╔════════════════════════════════════════════════════════════════════════════════════════╗
  ║  AssemblyInfo.cs — 빌드 결과물(어셈블리) 전체에 붙는 메타 정보                              ║
  ╚════════════════════════════════════════════════════════════════════════════════════════╝

  ┌ 이 파일은 무엇인가 ───────────────────────────────────────────────────────────────────
  │  어셈블리(assembly) = 빌드가 만든 .dll/.exe 한 덩어리. 이 파일은 그 덩어리에 "이름표" 를 붙인다.
  │  dotnet new wpf 템플릿이 만들어 둔 것이고, 이 프로젝트에서 손댈 일은 없다. 지워도 WPF 기본 테마로 동작한다.
  │
  │  여기 적힌 것: "테마별 스타일 파일이 어디 있나" → 우리는 별도 테마를 안 만드니 둘 다 "없음/기본" 이다.
  │  읽는 이유는 딱 하나 — [ … ] 문법(특성)을 한 번 봐 두기 위해서.
  └────────────────────────────────────────────────────────────────────────────────────────
*/

// ▸ ThemeInfo, ResourceDictionaryLocation 이 여기 있다.
using System.Windows;

// ▸ 단어 분해: [(특성 시작) assembly:(이 특성은 어셈블리 전체에 붙는다) ThemeInfo(② WPF 가 정한 특성 클래스)( 인자 두 개 ) ](특성 끝)
// ▸ 특성(attribute) = 코드에 붙이는 이름표. 실행되는 문장이 아니라 "이것은 이런 성질" 이라는 표시. Python 의 데코레이터(@…)와 비슷한 자리.
//   MainWindow.g.cs 에서 본 [System.Diagnostics.DebuggerNonUserCodeAttribute()] 도 같은 문법이다.
// ▸ ThemeInfo 의 두 인자: 첫째 = 테마별(Aero, Classic …) 스타일 사전이 어디 있나, 둘째 = 공통(generic) 스타일 사전이 어디 있나.
// ▸ None = 없음. SourceAssembly = 이 어셈블리 안(있다면). 우리는 스타일 사전을 안 만들었으니 사실상 둘 다 "기본 테마 써라".
[assembly:ThemeInfo(
    ResourceDictionaryLocation.None,            //where theme specific resource dictionaries are located
                                                //(used if a resource is not found in the page,
                                                // or application resource dictionaries)
    ResourceDictionaryLocation.SourceAssembly   //where the generic resource dictionary is located
                                                //(used if a resource is not found in the page,
                                                // app, or any theme specific resource dictionaries)
)]
