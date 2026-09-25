/*
  이 파일은 검사 화면의 "동작"을 담당한다. 화면 배치는 MainWindow.xaml 이 담당한다.
  실행 흐름: App.xaml 이 이 창을 연다 → "카메라 열기" 클릭 → 웹캠을 열고 타이머 시작
            → 타이머가 33ms 마다 프레임을 읽어 CameraImage 에 넣는다 → (③에서) "검사" 클릭 → /inspect 호출.
  알아야 할 개념: x:Name 을 붙인 XAML 요소는 여기서 변수처럼 쓸 수 있다.
                  이벤트 = "이 일이 생기면 이 함수를 불러라". Click, Tick 이 이벤트다.
*/

using System.Windows;              // Window, RoutedEventArgs (WPF 창과 이벤트의 기본 타입)
using System.Windows.Threading;    // DispatcherTimer (WPF 용 타이머)
using OpenCvSharp;                 // VideoCapture, Mat (C# 판 cv2)
using OpenCvSharp.WpfExtensions;   // ToBitmapSource() — Mat 을 WPF 가 그릴 수 있는 형식으로 바꾸는 변환기

// OpenCvSharp 에도 Window 라는 클래스가 있어 이름이 겹친다(CS0104). 이 파일의 Window 는 WPF 창이라고 못 박는다.
using Window = System.Windows.Window;

namespace SmartFactoryVision.Client;

/// <summary>
/// 검사 화면 창. 웹캠 미리보기와 (③에서) 검사 요청을 담당한다.
/// </summary>
public partial class MainWindow : Window
{
    // 열려 있는 카메라. 아직 안 열었으면 null 이라서 타입 뒤에 ? 를 붙였다.
    private VideoCapture? _capture;

    // 프레임을 담는 그릇. cv2 의 numpy 배열에 해당한다. 33ms 마다 새로 만들면 낭비라 하나를 재사용한다.
    private readonly Mat _frame = new Mat();

    // 33ms 마다 Tick 이벤트를 울리는 타이머. readonly = 만든 뒤 다른 것으로 바꾸지 않는다는 표시.
    private readonly DispatcherTimer _timer = new DispatcherTimer();

    /// <summary>
    /// 창이 만들어질 때 한 번 실행된다. XAML 을 읽고, 타이머의 간격과 할 일을 정해 둔다.
    /// </summary>
    public MainWindow()
    {
        InitializeComponent();   // XAML 대로 화면 요소를 만들고 x:Name 을 연결한다 (자동 생성 g.cs 에 있음)

        // 33ms ≈ 초당 30장. 웹캠이 보통 30fps 라 그보다 자주 읽어도 같은 프레임이 나온다.
        _timer.Interval = TimeSpan.FromMilliseconds(33);
        // 타이머가 울릴 때마다 Timer_Tick 을 불러라. += 는 이벤트에 함수를 등록하는 문법.
        _timer.Tick += Timer_Tick;
    }

    /// <summary>
    /// "카메라 열기" 버튼. 콤보박스에서 고른 번호의 웹캠을 열고 타이머를 시작한다.
    /// 입력: sender = 눌린 버튼, e = 클릭 정보 (WPF 가 정한 모양. 둘 다 안 쓴다)
    /// 실패 시: 카메라를 못 열면 StatusText 에 안내를 쓰고 그대로 끝낸다. 예외는 던지지 않는다.
    /// </summary>
    private void OpenCameraButton_Click(object sender, RoutedEventArgs e)
    {
        // 이미 열려 있던 카메라가 있으면 먼저 정리한다. 안 하면 카메라를 두 번 잡아 두 번째부터 실패한다.
        _timer.Stop();
        _capture?.Release();   // ?. = _capture 가 null 이 아닐 때만 Release() 호출

        // 콤보박스 항목이 "0","1","2" 순서라 선택된 순번(SelectedIndex)이 곧 카메라 번호다.
        int index = CameraIndexBox.SelectedIndex;

        // cv2.VideoCapture(index) 와 같다. 내장 카메라가 0, USB 웹캠은 PC 마다 0 또는 1.
        _capture = new VideoCapture(index);

        // 열기에 실패하면(번호가 틀리거나 다른 프로그램이 쓰는 중) 안내만 하고 멈춘다.
        if (!_capture.IsOpened())
        {
            StatusText.Text = $"카메라 {index}번을 열 수 없습니다. 번호를 바꿔 보세요";
            return;
        }

        _timer.Start();
        StatusText.Text = $"카메라 {index}번 열림";
    }

    /// <summary>
    /// 타이머가 울릴 때마다(33ms) 실행. 프레임 한 장을 읽어 화면의 Image 에 넣는다.
    /// 입력: sender = 타이머, e = 빈 정보 (DispatcherTimer 가 정한 모양. 안 쓴다)
    /// </summary>
    private void Timer_Tick(object? sender, EventArgs e)
    {
        // 카메라가 없거나, 읽기에 실패했거나, 빈 프레임이면 이번 틱은 건너뛴다.
        // Read() 는 cv2 의 cap.read() 와 같다. 성공하면 true 를 돌려주고 _frame 에 그림을 채운다.
        if (_capture == null || !_capture.Read(_frame) || _frame.Empty())
        {
            return;
        }

        // Mat(OpenCV 형식) → BitmapSource(WPF 형식). XAML 의 <Image> 는 이 형식만 그릴 수 있다.
        CameraImage.Source = _frame.ToBitmapSource();
    }

    /// <summary>
    /// 창을 닫을 때 실행. 카메라를 놓아 주지 않으면 다음 실행 때 "카메라를 열 수 없음" 이 난다.
    /// override = 부모(Window)에 이미 있는 OnClosed 를 우리 것으로 덮어쓴다는 뜻.
    /// </summary>
    protected override void OnClosed(EventArgs e)
    {
        _timer.Stop();
        _capture?.Release();
        base.OnClosed(e);   // 부모가 원래 하던 닫기 처리도 마저 한다
    }
}