/*
  ╔════════════════════════════════════════════════════════════════════════════════════════╗
  ║  App.xaml.cs — 프로그램 전체(App) 의 "동작". 짝 파일 App.xaml 의 C# 절반.                    ║
  ╚════════════════════════════════════════════════════════════════════════════════════════╝

  ┌ 이 파일은 무엇이고 언제 불리나 ────────────────────────────────────────────────────────
  │  exe 시작 → .NET 이 App 객체를 만든다 → App.xaml 의 StartupUri 대로 MainWindow 를 연다.
  │  MainWindow.xaml.cs 와 구조가 같다(partial class + 부모 상속). 다만 지금은 안이 텅 비어 있다.
  │  텅 빈 이유: 프로그램 시작·종료 때 특별히 할 일이 없기 때문. App.xaml 의 StartupUri 한 줄이 다 한다.
  │
  │  나중에 여기에 코드가 생길 수 있는 경우:
  │    - 시작할 때 설정 파일(.env 같은)을 읽어 서버 주소를 정한다  → OnStartup 을 override
  │    - 어디서든 안 잡힌 예외가 나면 프로그램이 죽는 대신 안내를 띄운다 → DispatcherUnhandledException 이벤트
  │  둘 다 이 프로젝트 범위 밖이다.
  └────────────────────────────────────────────────────────────────────────────────────────
*/

// ▸ 아래 세 줄은 dotnet new wpf 템플릿이 넣어 둔 것. 이 파일은 지금 아무 이름도 안 쓰므로 셋 다 없어도 빌드된다.
// ▸ System.Configuration : 옛날식 설정 파일(App.config) 읽기. 안 쓴다.
// ▸ System.Data          : DataSet 등 옛날식 DB 표. 안 쓴다(우리 DB 는 서버 쪽 Python 이 다룬다).
// ▸ System.Windows       : Application 클래스가 여기 있다. 아래 : Application 때문에 이것만은 실제로 필요하다.
using System.Configuration;
using System.Data;
using System.Windows;

// ▸ MainWindow.xaml.cs 와 같은 소속. App.xaml 의 x:Class="SmartFactoryVision.Client.App" 와 맞춘다.
namespace SmartFactoryVision.Client;

/// <summary>
/// 프로그램 전체를 뜻하는 객체. 창이 아니다. 창(MainWindow)은 이 객체가 App.xaml 의 StartupUri 대로 연다.
/// </summary>
// ▸ 단어 분해: public partial class App(③ 클래스 이름) :(상속) Application(② WPF 의 "프로그램" 클래스)
// ▸ MainWindow 가 Window 를 상속하듯, App 은 Application 을 상속한다. 시작·종료·전역 자원 관리 기능을 물려받는다.
// ▸ partial : 나머지 절반은 빌드가 App.xaml 에서 만든 obj/…/App.g.cs 에 있다. 거기에 InitializeComponent() 와 실제 시작점(Main 함수)이 있다.
//   C# 프로그램은 어딘가에 Main() 이 있어야 시작되는데, WPF 는 그걸 App.g.cs 에 자동으로 만들어 주므로 우리는 안 쓴다.
public partial class App : Application
{
    // ▸ 비어 있다. 생성자도 안 썼다 = 아무것도 안 하는 기본 생성자가 자동으로 생긴다.
}

