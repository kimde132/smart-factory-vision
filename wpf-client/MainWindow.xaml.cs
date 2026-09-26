/*
  ┌ 이 파일은 무엇인가 ─────────────────────────────────────────────────────────────
  │ 검사 화면의 "동작"을 담당한다. 화면에 뭐가 어디 있는지는 짝 파일 MainWindow.xaml 이 담당한다.
  │ XAML 에서 x:Name="…" 을 붙인 요소(CameraImage, StatusText …)는 이 파일에서 변수처럼 쓸 수 있다.
  │
  ├ 실행 흐름에서 어느 위치인가 ────────────────────────────────────────────────────
  │ App.xaml(StartupUri) 이 이 창을 연다
  │   → 생성자 MainWindow()             : 창이 만들어질 때 한 번. 타이머 준비
  │   → OpenCameraButton_Click()        : "카메라 열기" 클릭. 웹캠 열고 타이머 시작
  │   → Timer_Tick()                    : 33ms 마다. 프레임 한 장 읽어 화면에 표시   ← 영상처럼 보이는 이유
  │   → InspectButton_Click()           : "검사" 클릭. 프레임 + 기대 개수 → FastAPI /inspect → 결과 표시
  │   → OnClosed()                      : 창 닫을 때. 카메라 놓아주기
  │ 이 파일이 부르는 바깥: OpenCvSharp(웹캠), HttpClient(서버 요청), ai-server/main.py 의 POST /inspect
  │
  ├ 읽기 전에 알아야 할 개념 ──────────────────────────────────────────────────────
  │ 이벤트   : "이 일이 생기면 이 함수를 불러라". XAML 의 Click="함수이름", 코드의 _timer.Tick += 함수이름.
  │ 필드     : 클래스 안·함수 밖에 둔 변수(_capture, _frame …). 여러 함수가 같이 쓰고 값이 유지된다.
  │ null     : "아직 없음". Python 의 None. 타입 뒤의 ? 는 "null 일 수도 있다" 는 표시.
  │ async/await : 서버 응답을 기다리는 동안 화면이 얼지 않게 하는 문법. Python 과 같은 단어, 같은 뜻.
  │
  ├ 자료 모양 ───────────────────────────────────────────────────────────────────
  │ _frame (Mat)        : 높이×너비×3(BGR) 픽셀 배열. cv2 의 numpy 프레임과 같다. 웹캠 기본 640×480 또는 1280×720.
  │ jpeg (byte[])       : 그 프레임을 JPEG 로 압축한 바이트. 파일로 저장하면 그대로 .jpg 가 된다.
  │ 서버 응답 (JSON)    : {"result": "OK"|"NG", "counts": {"bolt": 3, "nut": 3, "washer": 3}, "expected": {...}}
  └──────────────────────────────────────────────────────────────────────────────
*/

// ── using = Python 의 import. "이 사전(네임스페이스)에 있는 이름을 짧게 쓰겠다" ──────────────────
using System.Windows;              // Window(창), RoutedEventArgs(클릭 이벤트 정보) — WPF 의 기본 타입
using System.Windows.Threading;    // DispatcherTimer — WPF 화면과 같은 줄(스레드)에서 도는 타이머
using OpenCvSharp;                 // VideoCapture(웹캠), Mat(프레임) — C# 판 cv2
using OpenCvSharp.WpfExtensions;   // ToBitmapSource() — Mat 을 WPF <Image> 가 그릴 수 있는 형식으로 바꾸는 변환기
using System.Text.Json;            // JsonDocument, JsonElement — 서버 응답(JSON 글자)을 읽는 도구. Python 의 json.loads
using System.Windows.Media;        // Brushes — 글자색. OK 는 초록, NG 는 빨강
using System.Net.Http;             // HttpClient, MultipartFormDataContent, HttpResponseMessage — 서버에 HTTP 요청을 보내는 도구
// System.Net.Http 는 콘솔 프로젝트라면 ImplicitUsings 가 자동으로 넣지만, WPF 프로젝트는 빠져 있어 직접 써야 한다(CS0246).

// ── using 별칭 = Python 의 import numpy as np ──────────────────────────────────────────
// OpenCvSharp 에도 Window 라는 클래스가 있어 System.Windows.Window 와 이름이 겹친다(CS0104 "모호한 참조").
// "이 파일에서 Window 라고 쓰면 WPF 창을 말한다" 고 못 박는다.
using Window = System.Windows.Window;

// namespace = 이 파일의 클래스가 속한 "성(姓)". 다른 프로젝트의 MainWindow 와 구분한다. Python 의 패키지 경로.
namespace SmartFactoryVision.Client;

/// <summary>
/// 검사 화면 창. 웹캠 미리보기와 검사 요청(/inspect)을 담당한다.
/// partial : 이 클래스의 나머지 절반은 빌드가 XAML 에서 자동으로 만든 MainWindow.g.cs 에 있다 (x:Name 변수들, InitializeComponent).
/// : Window : Window 를 상속한다. Python 의  class MainWindow(Window):
/// </summary>
public partial class MainWindow : Window
{
    // ════════════════════════════════════════════════════════════════════════════
    //  필드 — 클래스 안·함수 밖의 변수. 여러 함수가 같이 쓰고, 함수가 끝나도 값이 남는다.
    //  private = 이 클래스 안에서만 쓴다. 앞의 _ 는 "필드" 라는 C# 관습(문법 아님).
    // ════════════════════════════════════════════════════════════════════════════

    // 열려 있는 웹캠. "카메라 열기" 를 누르기 전에는 없으므로 null 이고, 그래서 타입 뒤에 ? 를 붙였다.
    // ? 가 없으면 컴파일러가 "null 이 들어갈 수 있는데 표시가 없다" 고 경고한다.
    private VideoCapture? _capture;

    // 프레임을 담는 그릇. new Mat() = 빈 Mat 객체 만들기 (Python 의 Mat()).
    // 33ms 마다 새 Mat 을 만들면 메모리를 계속 쓰므로, 하나를 만들어 두고 Read() 가 그 안에 덮어쓰게 한다.
    // readonly = 이 변수가 가리키는 객체를 다른 객체로 바꾸지 않겠다는 표시. 내용(픽셀)은 바뀌어도 된다.
    private readonly Mat _frame = new Mat();

    // 33ms 마다 Tick 이벤트를 울리는 타이머. 울릴 때 무엇을 할지는 생성자에서 += 로 등록한다.
    private readonly DispatcherTimer _timer = new DispatcherTimer();

    // 서버에 요청을 보내는 객체. 브라우저가 /docs 에서 하던 "요청 보내기" 부분만 떼어낸 것. Python 의 requests.
    // static   = 창을 몇 개 만들든 이 변수는 하나뿐. HttpClient 는 매번 새로 만들면 연결이 쌓여 느려지므로 하나를 계속 쓰는 것이 관례.
    // new X { 속성 = 값 } = 객체 초기화 문법. new HttpClient() 를 만든 직후 BaseAddress 를 채우는 것을 한 줄로 쓴 것.
    // BaseAddress = 주소의 앞부분. 뒤에서 PostAsync("inspect") 라고만 쓰면 http://localhost:8000/inspect 가 된다.
    // localhost:8000 = 같은 PC 의 8000 번 포트 = uvicorn 기본값. 서버가 다른 PC 로 가면 여기만 바꾼다.
    private static readonly HttpClient _http = new HttpClient
    {
        BaseAddress = new Uri("http://localhost:8000/")
    };

    // ════════════════════════════════════════════════════════════════════════════
    //  생성자 — 창 객체가 만들어질 때 딱 한 번 실행. Python 의 __init__.
    //  클래스와 이름이 같고 반환형(void 등)을 쓰지 않는 것이 생성자의 표시.
    // ════════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// 창이 만들어질 때 한 번 실행된다. XAML 을 읽어 화면을 만들고, 타이머의 간격과 할 일을 정해 둔다.
    /// 입력: 없음. 출력: 없음. 실패 시: XAML 이 깨져 있으면 여기서 예외가 나며 창이 안 뜬다.
    /// </summary>
    public MainWindow()
    {
        // XAML 대로 Grid·Button·TextBox… 객체를 실제로 만들고 x:Name 변수(CameraImage 등)에 연결한다.
        // 이 함수는 내가 쓴 게 아니라 빌드가 MainWindow.g.cs 에 자동으로 만든 것. 이 줄이 없으면 화면이 텅 빈다.
        InitializeComponent();

        // TimeSpan = 시간 길이를 나타내는 타입. 33ms ≈ 초당 30장. 웹캠이 보통 30fps 라 그보다 자주 읽어도 같은 프레임만 나온다.
        _timer.Interval = TimeSpan.FromMilliseconds(33);

        // += 는 이벤트에 함수를 "등록" 하는 문법. "타이머가 울리면(Tick) Timer_Tick 을 불러라".
        // XAML 의 Click="OpenCameraButton_Click" 을 C# 코드로 쓰면 이 모양이다. 함수 이름 뒤에 () 를 붙이지 않는 것에 주의 — 지금 실행하는 게 아니라 "나중에 부를 함수" 를 건네는 것.
        _timer.Tick += Timer_Tick;
    }

    // ════════════════════════════════════════════════════════════════════════════
    //  이벤트 함수들 — 사용자가 뭔가 하면(클릭) 또는 타이머가 울리면 WPF 가 대신 불러 준다.
    //  (object sender, RoutedEventArgs e) 는 WPF 가 정한 모양. sender = 이벤트를 일으킨 것(버튼), e = 부가 정보. 둘 다 안 써도 모양은 맞춰야 한다.
    // ════════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// "카메라 열기" 버튼. 콤보박스에서 고른 번호의 웹캠을 열고 타이머를 시작한다.
    /// 입력: sender = 눌린 버튼, e = 클릭 정보 (둘 다 안 쓴다)
    /// 출력: 없음(void). 화면의 StatusText 에 결과를 쓴다.
    /// 실패 시: 카메라를 못 열면 StatusText 에 안내를 쓰고 그대로 끝낸다. 예외를 밖으로 던지지 않는다.
    /// </summary>
    private void OpenCameraButton_Click(object sender, RoutedEventArgs e)
    {
        // 두 번째 누름(번호 바꿔 다시 열기)을 대비해 먼저 정리한다.
        // 안 하면 이전 카메라를 잡은 채 새 카메라를 또 잡아, 두 번째부터 "열 수 없음" 이 난다.
        _timer.Stop();
        // ?. = "null 이 아닐 때만 뒤를 실행". 처음 누를 때는 _capture 가 null 이라 Release() 를 건너뛴다.
        // Release() = 웹캠 놓아주기. cv2 의 cap.release() 와 같다.
        _capture?.Release();

        // int index = … : C# 은 변수를 만들 때 타입(int = 정수)을 먼저 쓴다.
        // SelectedIndex = 콤보박스에서 몇 번째 항목이 선택됐나(0부터). 항목이 "0","1","2" 순이라 그 순번이 곧 카메라 번호다.
        int index = CameraIndexBox.SelectedIndex;

        // new VideoCapture(번호) = cv2.VideoCapture(번호). 그 번호의 카메라를 잡는다.
        // 내장 카메라가 보통 0, USB 웹캠은 PC 마다 0 또는 1 이라 화면에서 고르게 했다(상태판 9/22).
        _capture = new VideoCapture(index);

        // ! = not. IsOpened() 가 false 면(번호가 틀리거나 다른 프로그램이 카메라를 쓰는 중) 안내만 하고 멈춘다.
        if (!_capture.IsOpened())
        {
            // $"…{변수}…" = 문자열 보간. Python 의 f"…{변수}…".
            StatusText.Text = $"카메라 {index}번을 열 수 없습니다. 번호를 바꿔 보세요";
            // return = 함수를 여기서 끝낸다. 아래 Start() 로 내려가지 않는다.
            return;
        }

        // 여기까지 왔으면 카메라가 열린 것. 타이머를 켜면 33ms 뒤부터 Timer_Tick 이 반복해서 불린다.
        _timer.Start();
        StatusText.Text = $"카메라 {index}번 열림";
    }

    /// <summary>
    /// 타이머가 울릴 때마다(33ms) 실행. 프레임 한 장을 읽어 화면의 Image 에 넣는다. 이것을 반복하면 영상처럼 보인다.
    /// 입력: sender = 타이머, e = 빈 정보 (DispatcherTimer 가 정한 모양. object? 는 sender 가 null 일 수도 있다는 뜻)
    /// 출력: 없음. CameraImage.Source 를 바꾼다.
    /// 실패 시: 읽기에 실패하면 이번 틱만 건너뛴다. 예외를 던지지 않는다.
    /// </summary>
    private void Timer_Tick(object? sender, EventArgs e)
    {
        // || = or. 셋 중 하나라도 참이면 건너뛴다.
        //   _capture == null   : 카메라가 안 열림 (타이머는 카메라 열린 뒤에만 켜지지만 방어적으로 한 번 더 확인)
        //   !_capture.Read(_frame) : 읽기 실패. Read() 는 cv2 의 cap.read() — 성공하면 true 를 돌려주고 _frame 안에 픽셀을 채운다
        //   _frame.Empty()     : 읽었다는데 내용이 없음 (카메라가 빠진 직후 등)
        if (_capture == null || !_capture.Read(_frame) || _frame.Empty())
        {
            return;
        }

        // Mat(OpenCV 형식) → BitmapSource(WPF 형식). XAML 의 <Image> 는 BitmapSource 만 그릴 수 있어서 변환이 필요하다.
        // Source 에 새 그림을 넣는 순간 화면이 다시 그려진다. 연습 4 의 MessageText.Text = "…" 와 같은 원리, 대상이 글자가 아니라 그림일 뿐.
        CameraImage.Source = _frame.ToBitmapSource();
    }

    /// <summary>
    /// "검사" 버튼. 현재 프레임과 기대 개수를 /inspect 로 보내고, 응답의 result·counts 를 화면에 쓴다.
    /// /docs 화면에서 파일 고르고 숫자 3개 넣고 Execute 누르던 것을 코드로 재현한 것.
    /// 입력: sender = 눌린 버튼, e = 클릭 정보 (안 쓴다)
    /// 출력: 없음. ResultText(OK/NG), CountText(개수), StatusText(안내)를 바꾼다.
    /// 실패 시: 카메라 미개방·숫자 아님·서버 꺼짐·서버 오류(400 등) 모두 StatusText 에 안내하고 끝낸다. 예외를 밖으로 던지지 않는다.
    /// async : 이 함수 안에서 await(기다리기)를 쓰겠다는 표시. void 와 짝인 async void 는 이벤트 함수에서만 허용된다.
    /// </summary>
    private async void InspectButton_Click(object sender, RoutedEventArgs e)
    {
        // ── 1. 보낼 재료가 있는지 확인 ──────────────────────────────────────────
        // 카메라가 안 열렸으면 _frame 이 비어 있어 보낼 게 없다.
        if (_capture == null || _frame.Empty())
        {
            StatusText.Text = "먼저 카메라를 열어 주세요";
            return;
        }

        // ── 2. 입력칸 글자 → 정수 ──────────────────────────────────────────────
        // TextBox.Text 는 항상 문자열("3")이다. int.TryParse 가 "3" → 3 으로 바꿔 본다.
        // out int bolt : TryParse 는 결과를 두 개 낸다 — 성공 여부(true/false)는 돌려주고, 숫자 자체는 out 뒤의 변수에 써넣는다.
        //                Python 이라면  ok, bolt = try_parse(text)  처럼 쓸 것을 C# 은 이렇게 쓴다.
        // 하나라도 실패하면(글자·빈칸) 서버가 422 를 돌려주므로 보내기 전에 여기서 막는다.
        if (!int.TryParse(BoltExpectedBox.Text, out int bolt) ||
            !int.TryParse(NutExpectedBox.Text, out int nut) ||
            !int.TryParse(WasherExpectedBox.Text, out int washer))
        {
            StatusText.Text = "기대 개수는 숫자로 입력해 주세요";
            return;
        }

        // ── 3. 프레임 → JPEG 바이트 ────────────────────────────────────────────
        // byte[] = 바이트 배열. 파일 내용을 메모리에 든 모양 그대로다.
        // ImEncode(".jpg") = cv2.imencode(".jpg", frame). 16:9 원본을 그대로 보내고, 가운데 1:1 크롭은 서버(main.py)가 한다.
        // Timer_Tick 과 이 함수는 같은 줄(UI 스레드)에서 번갈아 실행되므로, 인코딩 도중에 _frame 이 덮어써질 걱정은 없다.
        byte[] jpeg = _frame.ImEncode(".jpg");

        // ── 4. multipart/form-data 요청 조립 ───────────────────────────────────
        // multipart/form-data = "파일 + 글자 칸 여러 개" 를 한 요청에 담는 HTTP 형식. /docs 의 Execute 가 보내던 것과 같은 모양.
        // using var x = … : 파일 맨 위의 using(import)과 글자만 같고 다른 것. "이 함수가 끝나면 x 를 정리(Dispose)해라". Python 의 with.
        using var form = new MultipartFormDataContent();

        // Add(내용, 칸 이름, 파일 이름). 칸 이름 "image" 는 main.py 의 인자 이름  image: UploadFile = File(...)  과 글자까지 같아야 서버가 찾는다.
        // 파일 이름 "frame.jpg" 는 서버가 안 쓰므로 아무거나. ByteArrayContent = 바이트 배열을 요청 본문에 담는 포장지.
        form.Add(new ByteArrayContent(jpeg), "image", "frame.jpg");

        // Form(...) 칸 셋. 칸 이름 bolt/nut/washer 도 main.py 인자 이름과 같다.
        // 서버는 int 로 선언했지만 HTTP 는 글자만 나르므로 ToString() 으로 "3" 을 만들어 보낸다. 서버가 다시 3 으로 바꾼다.
        form.Add(new StringContent(bolt.ToString()), "bolt");
        form.Add(new StringContent(nut.ToString()), "nut");
        form.Add(new StringContent(washer.ToString()), "washer");

        // ── 5. 보내고 기다리기 ─────────────────────────────────────────────────
        // 응답이 오기 전에 또 누르면 요청이 겹치므로 버튼을 잠근다. 아래 finally 에서 반드시 푼다.
        InspectButton.IsEnabled = false;
        StatusText.Text = "검사 중...";

        // try / catch / finally = Python 의 try / except / finally.
        try
        {
            // PostAsync("inspect", form) = BaseAddress + "inspect" 로 POST. 이름 끝의 Async 는 "기다려야 하는 함수" 라는 관습.
            // await = 응답이 올 때까지 "이 함수만" 멈춘다. 그동안 WPF 는 다른 일(타이머, 미리보기, 창 이동)을 계속한다.
            //         await 가 없으면 응답이 올 때까지 창 전체가 얼어붙는다("응답 없음"). 서버가 CPU 추론이라 0.2~1초 걸리므로 필요하다.
            //         await 뒤 코드는 응답이 온 뒤 다시 화면 줄(UI 스레드)에서 이어지므로 아래에서 StatusText 등을 바로 만져도 된다.
            HttpResponseMessage response = await _http.PostAsync("inspect", form);

            // 응답 본문(body)을 글자로 꺼낸다. 성공이면 JSON, 400/422 면 {"detail": "..."} 이 온다. 이것도 기다려야 해서 await.
            string body = await response.Content.ReadAsStringAsync();

            // IsSuccessStatusCode = 상태 코드가 200 대인가. 아니면(400 비사진, 422 비숫자, 500 서버 내부 오류) 본문을 그대로 보여 준다.
            // (int)response.StatusCode = 형 변환(cast). StatusCode 는 이름표 타입(HttpStatusCode.BadRequest)인데 숫자 400 으로 보여 주려고 int 로 바꾼다.
            if (!response.IsSuccessStatusCode)
            {
                StatusText.Text = $"서버 오류 {(int)response.StatusCode}: {body}";
                return;   // finally 는 return 해도 실행된다 → 버튼은 풀린다
            }

            // ── 6. JSON 읽기 ───────────────────────────────────────────────────
            // JsonDocument.Parse(글자) = Python 의 json.loads. using 을 붙인 이유는 위와 같다(다 쓰면 정리).
            using JsonDocument doc = JsonDocument.Parse(body);
            // RootElement = JSON 의 맨 바깥 {…}. 응답 모양: {"result": "OK", "counts": {"bolt": 3, …}, "expected": {…}}
            JsonElement root = doc.RootElement;
            // GetProperty("result") = Python 의 root["result"]. GetString() = 그 값을 문자열로.
            // ?? "?" = 왼쪽이 null 이면 오른쪽을 쓴다. GetString() 은 값이 null 일 수 있다고 선언돼 있어 컴파일러 경고를 막으려고 붙였다. 실제로 서버는 항상 "OK"/"NG" 를 준다.
            string result = root.GetProperty("result").GetString() ?? "?";
            // counts 는 그 안의 {…}. 한 번 꺼내 두고 세 번 쓴다.
            JsonElement counts = root.GetProperty("counts");
            // GetInt32() = 그 값을 정수(int)로. 모델이 센 개수.
            int bolt_count = counts.GetProperty("bolt").GetInt32();
            int nut_count = counts.GetProperty("nut").GetInt32();
            int washer_count = counts.GetProperty("washer").GetInt32();

            // ── 7. 화면에 쓰기 ─────────────────────────────────────────────────
            ResultText.Text = result;
            // 조건 ? A : B = Python 의  A if 조건 else B. Foreground = 글자색. Brushes.Green/Red 는 미리 만들어진 색 붓.
            ResultText.Foreground = result == "OK" ? Brushes.Green : Brushes.Red;
            CountText.Text = $"볼트 {bolt_count} / 너트 {nut_count} / 와셔 {washer_count}";
            // bolt/nut/washer 는 2 번에서 읽은 기대 개수. 결과와 나란히 보여 주면 NG 의 이유를 바로 알 수 있다.
            StatusText.Text = $"검사 완료 (기대 {bolt}/{nut}/{washer})";
        }
        // catch (타입 변수) = 그 종류의 예외만 잡는다. HttpRequestException = 연결 자체가 안 될 때(서버 꺼짐, 주소 오타, 포트 다름).
        // 서버가 켜져 있고 400 을 돌려준 경우는 예외가 아니라 위의 IsSuccessStatusCode 분기로 간다.
        catch (HttpRequestException ex)
        {
            // ex.Message = 예외에 담긴 설명 글자 (예: "대상 컴퓨터에서 연결을 거부했으므로…")
            StatusText.Text = $"서버에 연결할 수 없습니다. uvicorn 이 켜져 있나요? ({ex.Message})";
        }
        // finally = 성공·실패·return 어느 길로 나가든 마지막에 반드시 실행. 버튼을 안 풀면 다시 검사를 못 누른다.
        finally
        {
            InspectButton.IsEnabled = true;
        }
    }

    // ════════════════════════════════════════════════════════════════════════════
    //  창 닫힘 처리 — 이벤트 등록이 아니라 부모(Window)의 함수를 덮어쓰는(override) 방식.
    // ════════════════════════════════════════════════════════════════════════════

    /// <summary>
    /// 창을 닫을 때 실행. 타이머를 멈추고 카메라를 놓아 준다.
    /// 안 놓아 주면 프로그램이 끝난 뒤에도 웹캠이 잡혀 있어, 다음 실행이나 다른 프로그램에서 "카메라를 열 수 없음" 이 난다.
    /// protected = 이 클래스와 자식 클래스만 부를 수 있음. override = 부모(Window)에 이미 있는 OnClosed 를 우리 것으로 덮어쓴다.
    /// 입력: e = 닫힘 정보 (안 쓴다). 출력: 없음.
    /// </summary>
    protected override void OnClosed(EventArgs e)
    {
        _timer.Stop();
        _capture?.Release();
        // base.OnClosed(e) = 부모(Window)가 원래 하던 닫기 처리도 마저 한다. 덮어썼다고 부모 일을 빼먹으면 안 된다.
        base.OnClosed(e);
    }
}
