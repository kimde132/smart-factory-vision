/*
  ╔══════════════════════════════════════════════════════════════════════════════════════════╗
  ║  MainWindow.xaml.cs — 검사 화면의 "동작"                                                   ║
  ║  (화면에 뭐가 어디 있는지는 짝 파일 MainWindow.xaml 이 담당한다)                             ║
  ╚══════════════════════════════════════════════════════════════════════════════════════════╝

  ┌ 0. 이 파일은 무엇이고 언제 불리나 ─────────────────────────────────────────────────────────
  │
  │  App.xaml(StartupUri) 이 이 창을 연다
  │    → 생성자 MainWindow()        : 창이 만들어질 때 한 번. 타이머 준비
  │    → OpenCameraButton_Click()   : "카메라 열기" 클릭. 웹캠 열고 타이머 시작
  │    → Timer_Tick()               : 33ms 마다. 프레임 한 장 읽어 화면에 표시   ← 영상처럼 보이는 이유
  │    → InspectButton_Click()      : "검사" 클릭. 프레임 + 기대 개수 → FastAPI /inspect → 결과 표시
  │    → OnClosed()                 : 창 닫을 때. 카메라 놓아주기
  │
  │  자료 모양
  │    _frame (Mat)      : 높이×너비×3(BGR) 픽셀 배열. cv2 의 numpy 프레임과 같다.
  │    jpeg (byte[])     : 그 프레임을 JPEG 로 압축한 바이트. 파일로 저장하면 그대로 .jpg.
  │    서버 응답 (JSON)  : {"result": "OK"|"NG", "counts": {"bolt": 3, "nut": 3, "washer": 3}, "expected": {...}}
  │
  ├ 1. 이름은 세 종류다 — 이것만 구분해도 절반은 읽힌다 ───────────────────────────────────────
  │
  │  ① 키워드 (C# 언어가 정한 예약어)
  │     using namespace class public private protected static readonly new if return
  │     async await try catch finally override void int string byte bool object null true false out base
  │     → 편집기에서 파란색/보라색. 내 마음대로 못 바꾸고, 변수 이름으로도 못 쓴다.
  │
  │  ② 라이브러리가 정한 이름 (남이 만들어 둔 것. using 으로 사전을 열어야 보인다)
  │     클래스(타입)      : Window VideoCapture Mat DispatcherTimer HttpClient Uri TimeSpan Brushes
  │                          JsonDocument JsonElement HttpResponseMessage MultipartFormDataContent
  │                          ByteArrayContent StringContent HttpRequestException RoutedEventArgs EventArgs
  │     그 클래스의 함수  : Read() Release() IsOpened() Empty() ImEncode() ToBitmapSource() PostAsync()
  │        (= 메서드)       ReadAsStringAsync() Parse() GetProperty() GetString() GetInt32() Add() ToString()
  │                          TryParse() FromMilliseconds() Start() Stop()
  │     그 클래스의 속성  : Interval Tick BaseAddress Text Source Foreground IsEnabled SelectedIndex
  │                          Content StatusCode IsSuccessStatusCode RootElement Message
  │     → 이름을 한 글자라도 틀리면(대소문자 포함) "찾을 수 없습니다" 빌드 오류. 어느 using 에서 왔는지는 2 절.
  │     → 클래스 이름 뒤에 () 가 붙으면 함수, 안 붙으면 속성. 앞에 new 가 있으면 "그 클래스의 객체 만들기".
  │
  │  ③ 내가 지은 이름 (마음대로 바꿔도 되지만, 쓰는 곳을 전부 같이 바꿔야 한다)
  │     필드      : _capture _frame _timer _http
  │     지역 변수 : index bolt nut washer jpeg form response body doc root counts bolt_count nut_count washer_count ex
  │     함수      : OpenCameraButton_Click Timer_Tick InspectButton_Click   (XAML 의 Click="…" 과 글자까지 맞춰야 함)
  │     XAML 요소 : CameraImage CameraIndexBox StatusText BoltExpectedBox … (MainWindow.xaml 의 x:Name 으로 내가 지은 것)
  │     클래스    : MainWindow (템플릿이 지었지만 내 것. 바꾸려면 x:Class·App.xaml·이 파일 세 곳)
  │
  │  구분법: 편집기에서 단어 위에 마우스를 올리면 툴팁에 class / method / property / field / local variable 이 뜬다.
  │          키워드는 툴팁이 없다. ③은 Ctrl+클릭하면 내 파일 안으로 이동하고, ②는 라이브러리 정의로 이동한다.
  │
  ├ 2. using 사전 — 어느 사전에서 어떤 이름을 가져왔나 ─────────────────────────────────────────
  │
  │  using 은 Python 의 import. "이 사전(네임스페이스)의 이름을 짧게 쓰겠다".
  │  사전 자체는 두 곳에서 온다: (a) .NET 에 기본 포함 (System.*)  (b) NuGet 패키지로 설치 (OpenCvSharp.*, .csproj 참고)
  │
  │  using System.Windows            (a) WPF 기본   → Window RoutedEventArgs
  │  using System.Windows.Threading  (a) WPF 기본   → DispatcherTimer
  │  using System.Windows.Media      (a) WPF 기본   → Brushes
  │  using System.Net.Http           (a) .NET 기본  → HttpClient HttpResponseMessage MultipartFormDataContent ByteArrayContent StringContent HttpRequestException
  │  using System.Text.Json          (a) .NET 기본  → JsonDocument JsonElement
  │  using OpenCvSharp               (b) 패키지     → VideoCapture Mat
  │  using OpenCvSharp.WpfExtensions (b) 패키지     → ToBitmapSource()
  │  (using 없이 쓰는 것)             (a) System     → TimeSpan Uri EventArgs int string byte bool object
  │                                    → .csproj 의 ImplicitUsings 가 System 등 몇 개를 자동으로 열어 둔다
  │
  │  "그 사전엔 또 뭐가 있나": 편집기에서 using 줄의 이름을 Ctrl+클릭하거나, 코드에서 `System.Windows.` 까지 치면 목록이 뜬다.
  │
  ├ 3. 키워드 계열표 — 한 자리에 올 수 있는 다른 선택지 ──────────────────────────────────────
  │
  │  [접근 제한자] "누가 볼 수 있나". 필드·함수·클래스 선언의 맨 앞.
  │     public    : 누구나                       → 다른 파일·다른 프로젝트에서도 쓸 수 있다
  │     private   : 이 클래스 안에서만            → 우리 필드·이벤트 함수 전부. 밖에서 만질 이유가 없다
  │     protected : 이 클래스 + 상속받은 자식만   → OnClosed. 부모 Window 가 그렇게 정해 둬서 맞춘 것
  │     internal  : 같은 프로젝트(.csproj) 안에서만 → g.cs 의 x:Name 변수들이 이것
  │     (생략)    : 클래스 안의 것은 private 로 취급
  │
  │  [수정자] "어떤 성질인가". 접근 제한자 뒤에 여러 개 겹칠 수 있다(축이 다르다).
  │     static    : 객체(창)마다가 아니라 클래스에 하나        → _http
  │     readonly  : 처음 넣은 뒤 다른 객체로 못 바꿈(자물쇠)   → _frame _timer _http
  │     const     : 컴파일 때 정해지는 상수(숫자·글자만)        → 여기 없음. 예: const int FPS = 30;
  │     async     : 함수 안에서 await 를 쓰겠다                → InspectButton_Click
  │     override  : 부모의 같은 이름 함수를 덮어쓴다           → OnClosed
  │     partial   : 이 클래스가 다른 파일에 이어져 있다        → MainWindow (g.cs 와 반반)
  │     virtual   : 자식이 override 해도 된다 (부모 쪽에 씀)   → Window.OnClosed 가 이것
  │     ※ public 과 private 는 같은 자리(접근 제한자)라 둘 중 하나만.
  │       static 과 readonly 는 다른 자리(수정자)라 같이 쓸 수 있다: private static readonly.
  │
  │  [타입] "무엇을 담나". 변수 이름 앞, 함수 이름 앞(반환형).
  │     int / string / bool / byte / double : 정수 / 글자 / 참거짓 / 0~255 / 소수
  │     byte[]                : byte 의 배열. [] 는 "여러 개"
  │     void                  : 함수가 돌려주는 값이 없다 (반환형 자리에만)
  │     object                : 아무 타입이나 (WPF 가 sender 를 이걸로 준다)
  │     var                   : 오른쪽을 보고 타입을 알아서 정해라 → using var form = … 에서 씀
  │     타입?                 : null 을 담아도 된다
  │     클래스 이름           : 그 클래스의 객체를 담는다 (VideoCapture, Mat, HttpClient …)
  │
  │  [흐름] if / else / return / try / catch / finally   (for, foreach, while 은 이 파일에 없다)
  │
  │  [연산자]
  │     =  대입          ==  같다        !=  다르다       !  not         ||  or        &&  and
  │     ?. null 아니면    ??  null 대체    ? : 조건 선택    += 이벤트 등록(숫자면 더하기)
  │     (int)x 형 변환    $"…{x}…" 문자열 안에 값 끼워 넣기    new 객체 만들기    . 소속(그것의)
  │
  ├ 4. 읽는 법 ──────────────────────────────────────────────────────────────────────────────
  │
  │  각 코드 줄 위에 ▸ 로 시작하는 주석이 있다.
  │    ▸ 단어 분해 : 왼쪽부터 한 단어씩. 괄호 안이 그 단어의 뜻. ①②③ 은 1 절의 이름 종류.
  │    ▸ 뜻       : 그 줄을 한국어 한 문장으로.
  │    ▸ 왜       : 이 줄이 없으면 무슨 일이 나나.
  │    ▸ 다른 선택: 그 자리에 다른 걸 쓰면 어떻게 되나. (없는 줄도 있다)
  └──────────────────────────────────────────────────────────────────────────────────────────
*/

// ═══════════════════════════════════════════════════════════════════════════════════════════
//  using — 사전 열기
// ═══════════════════════════════════════════════════════════════════════════════════════════

// ▸ 단어 분해: using(① 사전을 연다) System.Windows(② 사전 이름. System 안의 Windows) ;(문장 끝)
// ▸ 뜻: 이 파일에서 System.Windows 안의 이름(Window, RoutedEventArgs …)을 앞부분 없이 쓰겠다.
// ▸ 왜: 없으면 아래에서 Window 대신 System.Windows.Window 라고 매번 길게 써야 한다.
using System.Windows;
// ▸ DispatcherTimer 가 여기 있다. Threading = "실행 줄(스레드)" 관련. WPF 화면과 같은 줄에서 도는 타이머라 이 사전에 있다.
using System.Windows.Threading;
// ▸ VideoCapture, Mat 이 여기 있다. NuGet 패키지 OpenCvSharp4 를 설치했기 때문에 열 수 있는 사전(.csproj 참고).
using OpenCvSharp;
// ▸ ToBitmapSource() 가 여기 있다. 패키지 OpenCvSharp4.WpfExtensions. Mat 을 WPF 그림 형식으로 바꾸는 변환기.
using OpenCvSharp.WpfExtensions;
// ▸ JsonDocument, JsonElement 가 여기 있다. .NET 기본. Python 의 json 모듈에 해당.
using System.Text.Json;
// ▸ Brushes 가 여기 있다. Media = 색·그림·글꼴 등 "보이는 것" 관련.
using System.Windows.Media;
// ▸ HttpClient, MultipartFormDataContent, HttpResponseMessage, HttpRequestException 이 여기 있다. .NET 기본.
// ▸ 주의: 콘솔 프로젝트라면 ImplicitUsings 가 자동으로 열어 주지만, WPF 프로젝트는 빠져 있어 직접 써야 한다(안 쓰면 CS0246).
using System.Net.Http;

// ▸ 단어 분해: using(①) Window(③ 내가 정한 짧은 이름) =(이것은) System.Windows.Window(② 전체 이름) ;
// ▸ 뜻: 이 파일에서 Window 라고 쓰면 System.Windows.Window 를 말한다. Python 의 import numpy as np.
// ▸ 왜: OpenCvSharp 사전에도 Window 라는 클래스가 있어서(cv2.imshow 용 창) 둘 중 어느 것인지 컴파일러가 못 정한다(CS0104 "모호한 참조").
// ▸ 다른 선택: 이 줄을 빼고 아래에서 : System.Windows.Window 라고 전체 이름을 써도 된다.
using Window = System.Windows.Window;

// ▸ 단어 분해: namespace(① 소속을 정한다) SmartFactoryVision.Client(③ 프로젝트 이름. dotnet new 때 -n 으로 지음) ;
// ▸ 뜻: 이 파일의 클래스는 SmartFactoryVision.Client 소속이다. 다른 프로젝트의 MainWindow 와 구분하는 "성(姓)".
// ▸ 왜: XAML 의 x:Class="SmartFactoryVision.Client.MainWindow" 와 맞아야 짝이 맺어진다.
// ▸ 다른 선택: namespace X { … } 처럼 중괄호로 감싸는 옛 문법도 있다. 끝에 ; 만 쓰면 "이 파일 전체" 라는 뜻.
namespace SmartFactoryVision.Client;

/// <summary>
/// 검사 화면 창. 웹캠 미리보기와 검사 요청(/inspect)을 담당한다.
/// </summary>
// ▸ 단어 분해: public(① 누구나 볼 수 있음) partial(① 이 클래스의 나머지가 다른 파일에 있음) class(① 클래스 선언)
//              MainWindow(③ 클래스 이름) :(상속한다) Window(② 부모 클래스 = WPF 창)
// ▸ 뜻: Window 를 물려받은 MainWindow 클래스를 만든다. 나머지 절반은 빌드가 XAML 에서 자동 생성한 MainWindow.g.cs 에 있다.
// ▸ 왜 partial: XAML 의 x:Name 변수들과 InitializeComponent() 는 g.cs 에 있고, 동작은 여기에 있다. 두 파일이 합쳐져 한 클래스.
// ▸ 왜 : Window: 창을 띄우고·닫고·크기를 조절하는 기능을 부모에게서 물려받는다. Python 의  class MainWindow(Window):
// ▸ 다른 선택: partial 을 빼면 "MainWindow 가 두 번 정의됐다" 오류. : Window 를 빼면 창이 아니라 그냥 클래스라 InitializeComponent 도 못 쓴다.
public partial class MainWindow : Window
{
    // ═══════════════════════════════════════════════════════════════════════════════════════
    //  필드 — 클래스 안·함수 밖의 변수. 여러 함수가 같이 쓰고, 함수가 끝나도 값이 남는다.
    //  (필드인 이유는 "위치" 다. 앞의 _ 는 필드라는 걸 표시하는 관습일 뿐, 빼도 필드다)
    // ═══════════════════════════════════════════════════════════════════════════════════════

    // ▸ 단어 분해: private(① 이 클래스 안에서만) VideoCapture(② 타입. OpenCvSharp 의 웹캠 클래스) ?(null 허용) _capture(③ 이름) ;
    // ▸ 뜻: 이 클래스 안에서만 쓰는, VideoCapture 를 담을 빈 칸 _capture. 아직 비어 있어도(null) 된다.
    // ▸ 주의: 이 줄은 객체를 만들지 않는다. 칸만 만든다. 객체는 OpenCameraButton_Click 에서 new 로 만든다.
    // ▸ 왜 ?: "카메라 열기" 를 누르기 전에는 카메라가 없다. ? 가 없으면 컴파일러가 "null 이 들어갈 수 있는데 표시가 없다" 고 경고(CS8618).
    // ▸ 다른 선택: readonly 를 붙이면 카메라 번호를 바꿀 때 다시 넣을 수 없어 오류. public 으로 하면 밖에서 카메라를 건드릴 수 있어 위험.
    private VideoCapture? _capture;

    // ▸ 단어 분해: private(①) readonly(① 다른 객체로 못 바꿈) Mat(② 타입. OpenCvSharp 의 이미지 클래스) _frame(③) =(넣는다) new(① 객체 만들기) Mat(②)()(인자 없음) ;
    // ▸ 뜻: 빈 Mat 객체를 하나 만들어 _frame 칸에 넣고, 이후 다른 Mat 으로 바꾸지 않는다.
    // ▸ 왜 하나만: 33ms 마다 새 Mat 을 만들면 메모리를 계속 쓴다. 하나를 두고 Read() 가 그 안에 픽셀을 덮어쓰게 한다.
    // ▸ readonly 의 범위: 칸에 든 "객체" 를 못 바꾸는 것이지, 객체 "안의 내용(픽셀)" 은 바뀌어도 된다.
    // ▸ 다른 선택: = new Mat() 을 빼면 _capture 처럼 빈 칸(null)이 되고, Read(_frame) 에서 죽는다.
    private readonly Mat _frame = new Mat();

    // ▸ 단어 분해: private readonly DispatcherTimer(② WPF 타이머 클래스) _timer(③) = new DispatcherTimer() ;
    // ▸ 뜻: 타이머 객체를 하나 만들어 둔다. 간격과 할 일은 아래 생성자에서 정한다.
    // ▸ 왜 DispatcherTimer: .NET 에 타이머가 여럿인데(System.Timers.Timer 등), 이것만 WPF 화면과 같은 줄에서 울린다.
    //   다른 타이머는 울릴 때 화면 요소(CameraImage)를 만지면 "다른 스레드가 소유" 오류가 난다.
    private readonly DispatcherTimer _timer = new DispatcherTimer();

    // ▸ 단어 분해: private static(① 클래스에 하나) readonly(①) HttpClient(② 타입) _http(③) = new HttpClient(② 객체 만들기)
    //              {(객체 초기화 시작) BaseAddress(② HttpClient 의 속성) = new Uri(② 주소 타입 객체)("…"(글자)) }(끝) ;
    // ▸ 뜻: 프로그램에 하나뿐이고 다시 바꾸지 않을 _http 칸에, 기본 주소를 localhost:8000 으로 채운 HttpClient 를 만들어 넣는다.
    // ▸ 왜 static: 창을 몇 개 만들든 HttpClient 는 하나만. 매번 만들면 네트워크 연결이 쌓여 느려진다(.NET 공식 권고).
    // ▸ 왜 () 가 없나: new HttpClient { … } 는 "만들자마자 { } 안의 속성을 채워라" 는 객체 초기화 문법. 인자가 없으면 () 를 생략해도 된다.
    //   new HttpClient() { … } 라고 써도 똑같다. XAML 의 <Button Content="검사" /> 가 C# 으로는 정확히 이 모양이다.
    // ▸ 왜 Uri: BaseAddress 는 글자(string)가 아니라 주소 타입(Uri)만 받는다. "…" 글자를 new Uri(…) 로 감싸 주소 객체로 바꾼다. int("3") 같은 것.
    // ▸ localhost:8000 = 같은 PC 의 8000 번 포트 = uvicorn 기본값. 서버가 다른 PC 로 가면 이 글자만 바꾼다.
    private static readonly HttpClient _http = new HttpClient
    {
        BaseAddress = new Uri("http://localhost:8000/")
    };

    // ═══════════════════════════════════════════════════════════════════════════════════════
    //  생성자 — 창 객체가 만들어질 때 딱 한 번 실행. Python 의 __init__.
    //  클래스와 이름이 같고, 반환형(void 등)을 쓰지 않는 것이 생성자의 표시.
    // ═══════════════════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// 창이 만들어질 때 한 번 실행된다. XAML 을 읽어 화면을 만들고, 타이머의 간격과 할 일을 정해 둔다.
    /// 입력: 없음. 출력: 없음. 실패 시: XAML 이 깨져 있으면 여기서 예외가 나며 창이 안 뜬다.
    /// </summary>
    // ▸ 단어 분해: public(① App 이 이 창을 만들 수 있게) MainWindow(③ 클래스와 같은 이름 = 생성자) ()(인자 없음)
    // ▸ 다른 선택: private 로 하면 App 이 창을 못 만들어 프로그램이 안 뜬다.
    public MainWindow()
    {
        // ▸ 단어 분해: InitializeComponent(② g.cs 에 자동 생성된 함수) ()(호출) ;
        // ▸ 뜻: XAML 대로 Grid·Button·TextBox… 객체를 실제로 만들고 x:Name 변수(CameraImage 등)에 연결한다.
        // ▸ 왜: 이 줄이 없으면 창은 뜨지만 텅 비고, CameraImage 는 null 이라 만지는 순간 죽는다.
        // ▸ 이 함수는 내가 쓴 게 아니다. 빌드가 obj/…/MainWindow.g.cs 에 만든다. 그래서 partial.
        InitializeComponent();

        // ▸ 단어 분해: _timer(③).Interval(② 속성: 간격) =(넣는다) TimeSpan(② 시간 길이 타입).FromMilliseconds(② 그 클래스의 함수)(33) ;
        // ▸ 뜻: 타이머 간격을 33 밀리초로.
        // ▸ 왜 33: 1000ms ÷ 30 ≈ 33. 웹캠이 보통 초당 30장(30fps)이라 그보다 자주 읽어도 같은 프레임만 나온다.
        // ▸ 다른 선택: TimeSpan.FromSeconds(1) 이면 1초에 한 장, 뚝뚝 끊긴다. 10ms 로 하면 CPU 만 더 쓴다.
        _timer.Interval = TimeSpan.FromMilliseconds(33);

        // ▸ 단어 분해: _timer.Tick(② 이벤트: 울림) +=(등록한다) Timer_Tick(③ 아래에 있는 내 함수) ;
        // ▸ 뜻: 타이머가 울릴 때마다 Timer_Tick 을 불러라.
        // ▸ 주의: Timer_Tick 뒤에 () 가 없다. () 를 붙이면 "지금 실행" 이고, 안 붙이면 "이 함수를 건네준다(나중에 부르라고)".
        // ▸ 왜 +=: 이벤트에는 함수를 여러 개 등록할 수 있어서 = 가 아니라 += (추가). -= 로 뺄 수도 있다.
        // ▸ XAML 의 Click="OpenCameraButton_Click" 을 C# 코드로 쓰면 이 모양이다. 같은 일이다.
        _timer.Tick += Timer_Tick;
    }

    // ═══════════════════════════════════════════════════════════════════════════════════════
    //  이벤트 함수들 — 사용자가 뭔가 하면(클릭) 또는 타이머가 울리면 WPF 가 대신 불러 준다.
    //  (object sender, RoutedEventArgs e) 는 WPF 가 정한 모양. sender = 이벤트를 일으킨 것(버튼), e = 부가 정보.
    //  둘 다 안 써도 모양은 맞춰야 한다 — 안 맞으면 XAML 의 Click="…" 에서 빌드 오류.
    // ═══════════════════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// "카메라 열기" 버튼. 콤보박스에서 고른 번호의 웹캠을 열고 타이머를 시작한다.
    /// 입력: sender = 눌린 버튼, e = 클릭 정보 (둘 다 안 쓴다)
    /// 출력: 없음(void). 화면의 StatusText 에 결과를 쓴다.
    /// 실패 시: 카메라를 못 열면 StatusText 에 안내를 쓰고 그대로 끝낸다. 예외를 밖으로 던지지 않는다.
    /// </summary>
    // ▸ 단어 분해: private(①) void(① 돌려주는 값 없음) OpenCameraButton_Click(③ 함수 이름. XAML Click 과 동일)
    //              ((인자 시작) object(② 아무 타입) sender(③ 인자 이름) ,(구분) RoutedEventArgs(② WPF 클릭 정보 타입) e(③) )(인자 끝)
    // ▸ 뜻: 클릭 정보 두 개를 받고 아무것도 돌려주지 않는 함수. 이름은 XAML 에서 Click="OpenCameraButton_Click" 으로 연결된다.
    // ▸ 이름 규칙: "요소이름_이벤트이름" 은 관습이지 문법이 아니다. 아무 이름이나 되지만 XAML 과 글자까지 같아야 한다.
    // ▸ 다른 선택: void 를 int 로 바꾸면 "이벤트 함수는 값을 돌려줄 수 없다" 오류. 인자를 하나로 줄여도 오류.
    private void OpenCameraButton_Click(object sender, RoutedEventArgs e)
    {
        // ▸ 단어 분해: _timer.Stop(② 함수)() ;
        // ▸ 뜻: 타이머를 멈춘다.
        // ▸ 왜: 두 번째 누름(번호 바꿔 다시 열기)을 대비해 먼저 정리한다. 안 멈추면 아래에서 카메라를 놓는 사이에 Timer_Tick 이 빈 카메라를 읽으려 한다.
        _timer.Stop();

        // ▸ 단어 분해: _capture(③) ?.(null 이 아니면) Release(② 함수: 웹캠 놓아주기)() ;
        // ▸ 뜻: _capture 가 비어 있지 않으면 카메라를 놓아준다. 비어 있으면(처음 누름) 아무 일도 안 한다.
        // ▸ 왜 ?.: 처음 누를 때 _capture 는 null 이다. 그냥 _capture.Release() 라고 쓰면 null 을 건드려 죽는다(NullReferenceException).
        // ▸ 다른 선택: if (_capture != null) { _capture.Release(); } 와 완전히 같다. ?. 는 그 줄임.
        // ▸ Release() = cv2 의 cap.release(). 안 놓아주고 새로 열면 "이미 사용 중" 으로 실패한다.
        _capture?.Release();

        // ▸ 단어 분해: int(① 정수 타입) index(③ 지역 변수. 이 함수 안에서만 산다) = CameraIndexBox(③ XAML x:Name).SelectedIndex(② ComboBox 의 속성) ;
        // ▸ 뜻: 콤보박스에서 몇 번째 항목이 선택됐는지(0부터)를 index 에 담는다.
        // ▸ 왜 그게 카메라 번호인가: XAML 에서 항목을 "0","1","2" 순으로 넣었기 때문에 순번 = 번호. 항목 순서를 바꾸면 이 가정이 깨진다.
        // ▸ 지역 변수 vs 필드: index 는 이 함수가 끝나면 사라진다. _capture 는 남는다. 다른 함수에서도 써야 하면 필드로 올린다.
        int index = CameraIndexBox.SelectedIndex;

        // ▸ 단어 분해: _capture(③ 필드) =(넣는다) new(①) VideoCapture(②)(index)(인자: 카메라 번호) ;
        // ▸ 뜻: index 번 카메라를 잡는 VideoCapture 객체를 만들어 _capture 칸에 넣는다. 위에서 만든 "빈 칸" 이 여기서 채워진다.
        // ▸ = cv2.VideoCapture(index). 내장 카메라가 보통 0, USB 웹캠은 PC 마다 0 또는 1 이라 화면에서 고르게 했다.
        _capture = new VideoCapture(index);

        // ▸ 단어 분해: if(①) ((조건 시작) !(not) _capture.IsOpened(② 함수: 열렸나)() )(조건 끝)
        // ▸ 뜻: 열리지 않았으면 아래 { } 를 실행한다.
        // ▸ 왜: 번호가 틀리거나 다른 프로그램이 카메라를 쓰는 중이면 IsOpened() 가 false 다. 그대로 Read() 하면 계속 실패만 한다.
        if (!_capture.IsOpened())
        {
            // ▸ 단어 분해: StatusText(③ XAML x:Name).Text(② TextBlock 의 속성) = $(문자열 보간 시작)"카메라 {index}번…"(중괄호 안은 변수 값) ;
            // ▸ 뜻: 상태 칸에 안내 글자를 쓴다. {index} 자리에 실제 숫자가 들어간다. Python 의 f"…{index}…".
            // ▸ 다른 선택: "카메라 " + index + "번…" 처럼 + 로 이어 붙여도 된다. $"" 가 읽기 쉽다.
            StatusText.Text = $"카메라 {index}번을 열 수 없습니다. 번호를 바꿔 보세요";
            // ▸ 단어 분해: return(① 함수 끝) ;
            // ▸ 뜻: 여기서 함수를 끝낸다. 아래 Start() 로 내려가지 않는다.
            // ▸ 왜: 카메라가 없는데 타이머를 켜면 Timer_Tick 이 33ms 마다 실패만 반복한다.
            return;
        }

        // ▸ 단어 분해: _timer.Start(② 함수)() ;
        // ▸ 뜻: 타이머를 켠다. 33ms 뒤부터 Timer_Tick 이 반복해서 불린다.
        _timer.Start();
        StatusText.Text = $"카메라 {index}번 열림";
    }

    /// <summary>
    /// 타이머가 울릴 때마다(33ms) 실행. 프레임 한 장을 읽어 화면의 Image 에 넣는다. 이것을 반복하면 영상처럼 보인다.
    /// 입력: sender = 타이머, e = 빈 정보 (안 쓴다)
    /// 출력: 없음. CameraImage.Source 를 바꾼다.
    /// 실패 시: 읽기에 실패하면 이번 틱만 건너뛴다. 예외를 던지지 않는다.
    /// </summary>
    // ▸ 단어 분해: private void Timer_Tick(③) (object?(② 아무 타입, null 허용) sender, EventArgs(② 기본 이벤트 정보) e)
    // ▸ 왜 모양이 위와 다른가: 이건 XAML 의 Click 이 아니라 DispatcherTimer.Tick 이 정한 모양이다. 이벤트마다 요구하는 인자 타입이 다르다.
    //   (Click → RoutedEventArgs, Tick → EventArgs). += 로 등록할 때 모양이 안 맞으면 빌드 오류로 알려 준다.
    private void Timer_Tick(object? sender, EventArgs e)
    {
        // ▸ 단어 분해: if ( _capture == null(비었나) ||(or) !_capture.Read(② 함수)(_frame)(인자: 여기에 채워라) ||(or) _frame.Empty(② 함수)() )
        // ▸ 뜻: 셋 중 하나라도 참이면 이번 틱은 건너뛴다.
        //     _capture == null       : 카메라가 안 열림 (타이머는 카메라 열린 뒤에만 켜지지만 방어적으로 한 번 더)
        //     !_capture.Read(_frame) : 읽기 실패. Read() 는 cv2 의 cap.read() — 성공하면 true 를 돌려주고 _frame 안에 픽셀을 채운다
        //     _frame.Empty()         : 읽었다는데 내용이 없음 (카메라가 빠진 직후 등)
        // ▸ || 의 성질: 왼쪽이 참이면 오른쪽은 보지도 않는다. 그래서 _capture == null 을 맨 앞에 둬야 뒤의 _capture.Read 가 null 을 건드리지 않는다.
        if (_capture == null || !_capture.Read(_frame) || _frame.Empty())
        {
            return;
        }

        // ▸ 단어 분해: CameraImage(③ XAML x:Name).Source(② Image 의 속성: 보여줄 그림) = _frame.ToBitmapSource(② WpfExtensions 가 Mat 에 붙여 준 함수)() ;
        // ▸ 뜻: Mat(OpenCV 형식)을 BitmapSource(WPF 형식)로 바꿔 Image 에 넣는다. 넣는 순간 화면이 다시 그려진다.
        // ▸ 왜 변환: XAML 의 <Image> 는 BitmapSource 만 그릴 수 있다. Mat 을 직접 넣으면 타입 오류.
        // ▸ 연습 4 의 MessageText.Text = "…" 와 같은 원리. 대상이 글자가 아니라 그림일 뿐.
        CameraImage.Source = _frame.ToBitmapSource();
    }

    /// <summary>
    /// "검사" 버튼. 현재 프레임과 기대 개수를 /inspect 로 보내고, 응답의 result·counts 를 화면에 쓴다.
    /// /docs 화면에서 파일 고르고 숫자 3개 넣고 Execute 누르던 것을 코드로 재현한 것.
    /// 입력: sender = 눌린 버튼, e = 클릭 정보 (안 쓴다)
    /// 출력: 없음. ResultText(OK/NG), CountText(개수), StatusText(안내)를 바꾼다.
    /// 실패 시: 카메라 미개방·숫자 아님·서버 꺼짐·서버 오류(400 등) 모두 StatusText 에 안내하고 끝낸다. 예외를 밖으로 던지지 않는다.
    /// </summary>
    // ▸ 단어 분해: private async(① 안에서 await 를 쓴다) void InspectButton_Click(③) (object sender, RoutedEventArgs e)
    // ▸ 왜 async: 서버 응답을 기다리는 줄에 await 를 쓰려면 함수에 async 표시가 있어야 한다. 없으면 "await 는 async 함수에서만" 오류.
    // ▸ async void 는 특별: 보통 async 함수는 Task 를 돌려주지만, 이벤트 함수는 void 여야 하므로 async void 가 허용된다. 이벤트 함수 말고는 쓰지 않는 게 관례.
    private async void InspectButton_Click(object sender, RoutedEventArgs e)
    {
        // ── 1. 보낼 재료가 있는지 확인 ─────────────────────────────────────────────────────
        // ▸ 카메라가 안 열렸으면 _frame 이 비어 있어 보낼 게 없다. Timer_Tick 의 첫 줄과 같은 검사.
        if (_capture == null || _frame.Empty())
        {
            StatusText.Text = "먼저 카메라를 열어 주세요";
            return;
        }

        // ── 2. 입력칸 글자 → 정수 ─────────────────────────────────────────────────────────
        // ▸ 단어 분해: !(not) int.TryParse(② int 타입의 함수: 글자→정수 시도)( BoltExpectedBox.Text(② TextBox 의 속성: 입력된 글자) ,
        //              out(① 결과를 여기에 써넣어라) int bolt(③ 새 변수를 이 자리에서 선언) )
        // ▸ 뜻: "3" 을 3 으로 바꿔 본다. 성공하면 true 를 돌려주고 bolt 에 3 을 써넣는다. 실패하면 false.
        // ▸ 왜 out: TryParse 는 결과가 둘이다(성공 여부 + 숫자). C# 함수는 값을 하나만 돌려주므로, 두 번째는 out 변수에 써넣는 방식을 쓴다.
        //   Python 이라면  ok, bolt = try_parse(text)  로 쓸 것을 C# 은 이렇게 쓴다.
        // ▸ 다른 선택: int.Parse(text) 는 실패하면 예외를 던진다. try/catch 가 필요해져서 TryParse 가 낫다.
        // ▸ 왜 여기서 막나: 글자·빈칸을 그대로 보내면 서버가 422 를 돌려준다. 보내기 전에 잡는 게 빠르고 친절하다.
        // ▸ || 세 개: 하나라도 실패하면(true) 안으로 들어간다. 성공한 것들의 bolt/nut/washer 는 아래에서 그대로 쓴다.
        if (!int.TryParse(BoltExpectedBox.Text, out int bolt) ||
            !int.TryParse(NutExpectedBox.Text, out int nut) ||
            !int.TryParse(WasherExpectedBox.Text, out int washer))
        {
            StatusText.Text = "기대 개수는 숫자로 입력해 주세요";
            return;
        }

        // ── 3. 프레임 → JPEG 바이트 ───────────────────────────────────────────────────────
        // ▸ 단어 분해: byte[](① 바이트 배열 타입) jpeg(③) = _frame.ImEncode(② Mat 의 함수: 이미지 압축)(".jpg"(어떤 형식으로)) ;
        // ▸ 뜻: 프레임을 JPEG 로 압축한 바이트 뭉치를 jpeg 에 담는다. 파일로 저장하면 그대로 .jpg 가 된다.
        // ▸ = cv2.imencode(".jpg", frame). ".png" 로 바꾸면 무손실이지만 커서 전송이 느려진다.
        // ▸ 16:9 원본을 그대로 보낸다. 가운데 1:1 크롭은 서버(main.py)가 한다 — 크롭 규칙이 한 곳에만 있어야 스크립트 채점과 운영이 같은 그림을 본다.
        // ▸ 안전한가: Timer_Tick 과 이 함수는 같은 줄(UI 스레드)에서 번갈아 실행되므로, 인코딩 도중에 _frame 이 덮어써질 걱정은 없다.
        byte[] jpeg = _frame.ImEncode(".jpg");

        // ── 4. multipart/form-data 요청 조립 ──────────────────────────────────────────────
        // ▸ 단어 분해: using(① 함수 끝나면 정리해라) var(① 타입은 오른쪽 보고 정해라) form(③) = new MultipartFormDataContent(②)() ;
        // ▸ 뜻: "파일 + 글자 칸 여러 개" 를 한 요청에 담는 상자를 만든다. 함수가 끝나면 자동으로 정리(Dispose)된다.
        // ▸ 주의: 파일 맨 위의 using(사전 열기)과 글자만 같고 다른 문법이다. 함수 안에서 변수 앞에 붙으면 "다 쓰면 정리" = Python 의 with.
        // ▸ 왜 정리가 필요한가: 네트워크·파일 같은 바깥 자원을 잡는 객체는 다 쓰고 놓아줘야 한다. 안 놓으면 조금씩 샌다.
        // ▸ var: 오른쪽이 new MultipartFormDataContent() 이므로 form 의 타입도 그것. 길어서 var 로 줄인 것뿐, 타입이 없는 게 아니다.
        using var form = new MultipartFormDataContent();

        // ▸ 단어 분해: form.Add(② 함수)( new ByteArrayContent(② 바이트를 담는 포장지)(jpeg) ,(칸 이름) "image" ,(파일 이름) "frame.jpg" ) ;
        // ▸ 뜻: jpeg 바이트를 "image" 라는 칸에, 파일 이름 frame.jpg 로 담는다.
        // ▸ 왜 "image": main.py 의 인자 이름  image: UploadFile = File(...)  과 글자까지 같아야 서버가 찾는다. 틀리면 422.
        // ▸ 파일 이름은 서버가 안 쓰므로 아무거나. 단 확장자가 있어야 브라우저·서버가 종류를 짐작하기 좋다.
        form.Add(new ByteArrayContent(jpeg), "image", "frame.jpg");

        // ▸ 단어 분해: form.Add( new StringContent(② 글자를 담는 포장지)( bolt.ToString(② 모든 타입이 가진 함수: 글자로)() ) , "bolt" ) ;
        // ▸ 뜻: 정수 bolt 를 글자 "3" 으로 바꿔 "bolt" 칸에 담는다.
        // ▸ 왜 ToString: HTTP 는 글자만 나른다. 서버가 int 로 선언했어도 글자 "3" 으로 받아서 자기가 3 으로 바꾼다.
        // ▸ 칸 이름 bolt/nut/washer 도 main.py 인자 이름과 같다.
        form.Add(new StringContent(bolt.ToString()), "bolt");
        form.Add(new StringContent(nut.ToString()), "nut");
        form.Add(new StringContent(washer.ToString()), "washer");

        // ── 5. 보내고 기다리기 ────────────────────────────────────────────────────────────
        // ▸ 단어 분해: InspectButton(③ XAML x:Name).IsEnabled(② Button 의 속성: 눌리나) = false(① 거짓) ;
        // ▸ 뜻: 버튼을 회색으로 잠근다.
        // ▸ 왜: 응답이 오기 전에 또 누르면 요청이 겹친다. 아래 finally 에서 반드시 푼다.
        InspectButton.IsEnabled = false;
        StatusText.Text = "검사 중...";

        // ▸ try(① 여기서 예외가 나면 catch 로) — Python 의 try 와 같다.
        try
        {
            // ▸ 단어 분해: HttpResponseMessage(② 응답 타입) response(③) = await(① 끝날 때까지 기다림) _http.PostAsync(② HttpClient 의 함수: POST 보내기)("inspect"(주소 뒷부분), form(본문)) ;
            // ▸ 뜻: BaseAddress + "inspect" = http://localhost:8000/inspect 로 form 을 POST 하고, 응답이 올 때까지 기다린 뒤 response 에 담는다.
            // ▸ await 가 하는 일: 응답이 올 때까지 "이 함수만" 멈춘다. 그동안 WPF 는 다른 일(타이머, 미리보기, 창 이동)을 계속한다.
            //   await 가 없으면(동기 호출) 응답이 올 때까지 창 전체가 얼어붙는다("응답 없음"). 서버가 CPU 추론이라 0.2~1초 걸리므로 필요하다.
            //   await 뒤의 코드는 응답이 온 뒤 다시 화면 줄(UI 스레드)에서 이어지므로, 아래에서 StatusText 등을 바로 만져도 된다.
            // ▸ 이름 끝의 Async: "기다려야 하는 함수" 라는 .NET 관습. 이런 함수는 거의 항상 앞에 await 를 붙인다.
            HttpResponseMessage response = await _http.PostAsync("inspect", form);

            // ▸ 단어 분해: string(① 글자 타입) body(③) = await response.Content(② 속성: 본문).ReadAsStringAsync(② 함수: 글자로 읽기)() ;
            // ▸ 뜻: 응답 본문을 글자로 꺼낸다. 성공이면 JSON, 400/422 면 {"detail": "..."} 이 온다.
            // ▸ 왜 또 await: 본문이 클 수 있어 이것도 "기다려야 하는 함수" 다.
            string body = await response.Content.ReadAsStringAsync();

            // ▸ 단어 분해: if ( !(not) response.IsSuccessStatusCode(② 속성: 상태 코드가 200 대인가) )
            // ▸ 뜻: 200 대가 아니면(400 비사진, 422 비숫자, 500 서버 내부 오류) 본문을 그대로 보여 주고 끝낸다.
            // ▸ 왜 예외가 아닌가: 서버가 "켜져 있고 답을 했다" 면 HttpClient 는 예외를 안 던진다. 400 도 정상 응답으로 취급한다. 그래서 직접 확인한다.
            if (!response.IsSuccessStatusCode)
            {
                // ▸ 단어 분해: (int)(형 변환: int 로 바꿔라) response.StatusCode(② 속성. HttpStatusCode 라는 이름표 타입)
                // ▸ 뜻: 이름표(HttpStatusCode.BadRequest)를 숫자(400)로 바꿔 보여 준다. 안 바꾸면 "BadRequest" 라고 찍힌다.
                StatusText.Text = $"서버 오류 {(int)response.StatusCode}: {body}";
                return;   // ▸ return 해도 아래 finally 는 실행된다 → 버튼은 풀린다
            }

            // ── 6. JSON 읽기 ──────────────────────────────────────────────────────────────
            // ▸ 단어 분해: using(정리 예약) JsonDocument(② 타입) doc(③) = JsonDocument.Parse(② 함수: 글자→JSON)(body) ;
            // ▸ 뜻: 글자 body 를 JSON 구조로 읽어 doc 에 담는다. = Python 의 json.loads(body). 함수가 끝나면 정리.
            // ▸ 왜 var 가 아니고 JsonDocument 인가: 둘 다 된다. 위에서 var 를 썼으니 여기서는 타입을 써서 둘 다 보여 준 것.
            using JsonDocument doc = JsonDocument.Parse(body);

            // ▸ 단어 분해: JsonElement(② JSON 의 한 조각 타입) root(③) = doc.RootElement(② 속성: 맨 바깥 {…}) ;
            // ▸ 응답 모양: {"result": "OK", "counts": {"bolt": 3, …}, "expected": {…}} — root 는 이 전체.
            JsonElement root = doc.RootElement;

            // ▸ 단어 분해: string result(③) = root.GetProperty(② 함수: 키로 꺼내기)("result").GetString(② 함수: 값을 글자로)() ??(null 이면) "?" ;
            // ▸ 뜻: root["result"] 를 글자로 꺼낸다. 혹시 null 이면 "?" 를 쓴다.
            // ▸ GetProperty("result") = Python 의 root["result"]. 키가 없으면 예외(KeyNotFoundException).
            // ▸ 왜 ??: GetString() 은 "null 을 돌려줄 수도 있다" 고 선언돼 있어, 그대로 string 에 넣으면 컴파일러 경고(CS8600). 실제 서버는 항상 "OK"/"NG" 를 준다.
            string result = root.GetProperty("result").GetString() ?? "?";

            // ▸ counts 는 root 안의 {…}. 한 번 꺼내 두고 세 번 쓴다. 매번 root.GetProperty("counts").GetProperty("bolt") 라고 써도 되지만 길다.
            JsonElement counts = root.GetProperty("counts");

            // ▸ 단어 분해: int bolt_count(③) = counts.GetProperty("bolt").GetInt32(② 함수: 값을 32비트 정수로)() ;
            // ▸ 뜻: counts["bolt"] 를 정수로. 모델이 센 개수.
            // ▸ 이름을 bolt 가 아니라 bolt_count 로 한 이유: bolt 는 위 2 번에서 "기대 개수" 로 이미 썼다. 같은 함수 안에서 같은 이름을 두 번 선언하면 오류.
            int bolt_count = counts.GetProperty("bolt").GetInt32();
            int nut_count = counts.GetProperty("nut").GetInt32();
            int washer_count = counts.GetProperty("washer").GetInt32();

            // ── 7. 화면에 쓰기 ────────────────────────────────────────────────────────────
            ResultText.Text = result;

            // ▸ 단어 분해: ResultText.Foreground(② 속성: 글자색) = result == "OK"(조건) ?(참이면) Brushes.Green(② 초록 붓) :(거짓이면) Brushes.Red ;
            // ▸ 뜻: OK 면 초록, 아니면 빨강. = Python 의  Brushes.Green if result == "OK" else Brushes.Red
            // ▸ Brushes = 미리 만들어진 색 붓 모음(System.Windows.Media). Brushes.Blue, Brushes.Gray 등 140여 개. XAML 의 Foreground="Gray" 와 같은 것.
            ResultText.Foreground = result == "OK" ? Brushes.Green : Brushes.Red;
            CountText.Text = $"볼트 {bolt_count} / 너트 {nut_count} / 와셔 {washer_count}";
            // ▸ bolt/nut/washer 는 2 번에서 읽은 기대 개수. 결과와 나란히 보여 주면 NG 의 이유를 바로 알 수 있다.
            StatusText.Text = $"검사 완료 (기대 {bolt}/{nut}/{washer})";
        }
        // ▸ 단어 분해: catch(① 예외를 잡는다) ( HttpRequestException(② 이 종류만) ex(③ 잡은 예외를 담을 이름) )
        // ▸ 뜻: try 안에서 HttpRequestException 이 나면 여기로 온다. 다른 종류의 예외는 안 잡힌다(그대로 밖으로 나가 프로그램이 죽는다).
        // ▸ 언제 나나: 연결 자체가 안 될 때 — 서버 꺼짐, 주소 오타, 포트 다름. 서버가 켜져 있고 400 을 돌려준 경우는 예외가 아니라 위 IsSuccessStatusCode 분기.
        // ▸ 다른 선택: catch (Exception ex) 로 하면 모든 예외를 잡는다. 편하지만 "무슨 문제인지" 를 뭉개서 디버깅이 어려워진다.
        // ▸ = Python 의 except requests.ConnectionError as ex:
        catch (HttpRequestException ex)
        {
            // ▸ ex.Message(② 예외 객체의 속성: 설명 글자). 예: "대상 컴퓨터에서 연결을 거부했으므로…"
            StatusText.Text = $"서버에 연결할 수 없습니다. uvicorn 이 켜져 있나요? ({ex.Message})";
        }
        // ▸ finally(① 어느 길로 나가든 마지막에 반드시) — 성공·catch·return 전부 거쳐 간다.
        // ▸ 왜: 버튼을 안 풀면 다시 검사를 못 누른다. try 안의 return 뒤에도 실행되는 것이 finally 의 핵심.
        finally
        {
            InspectButton.IsEnabled = true;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════════════════
    //  창 닫힘 처리 — 이벤트 등록(+=)이 아니라 부모(Window)의 함수를 덮어쓰는(override) 방식.
    //  두 방식 다 가능하다. 부모가 "닫힐 때 이 함수를 부른다" 고 미리 만들어 뒀으면 override 가 더 짧다.
    // ═══════════════════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// 창을 닫을 때 실행. 타이머를 멈추고 카메라를 놓아 준다.
    /// 안 놓아 주면 프로그램이 끝난 뒤에도 웹캠이 잡혀 있어, 다음 실행이나 다른 프로그램에서 "카메라를 열 수 없음" 이 난다.
    /// 입력: e = 닫힘 정보 (안 쓴다). 출력: 없음.
    /// </summary>
    // ▸ 단어 분해: protected(① 이 클래스와 자식만) override(① 부모의 같은 함수를 덮어쓴다) void OnClosed(② 부모 Window 가 정한 이름)(EventArgs e)
    // ▸ 왜 protected: 부모 Window 가 OnClosed 를 protected virtual 로 만들어 뒀다. 덮어쓸 때는 접근 제한자·이름·인자를 부모와 똑같이 맞춰야 한다.
    // ▸ 다른 선택: private 로 바꾸면 "접근 수준이 다르다" 오류. 이름을 OnClose 로 틀리면 "덮어쓸 함수가 없다" 오류. override 를 빼면 부모 함수를 가릴 뿐 창을 닫아도 안 불린다(경고 CS0114).
    protected override void OnClosed(EventArgs e)
    {
        _timer.Stop();
        _capture?.Release();
        // ▸ 단어 분해: base(① 부모 클래스).OnClosed(② 부모의 원래 함수)(e) ;
        // ▸ 뜻: 부모(Window)가 원래 하던 닫기 처리도 마저 한다. Python 의 super().on_closed(e).
        // ▸ 왜: 덮어썼다고 부모 일을 빼먹으면 창이 제대로 정리되지 않는다. 우리 일(카메라 정리)을 먼저 하고 부모 일을 마지막에.
        base.OnClosed(e);
    }
}
