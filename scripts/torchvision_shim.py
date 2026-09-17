# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   이 노트북에서 torchvision 을 불러올 수 없는 문제를 우회한다.
#   Windows 의 Smart App Control 이 torchvision 의 C++ 확장 파일(_C.pyd, 서명 없음)을 차단해서
#   `import torchvision` 자체가 "operator torchvision::nms does not exist" 로 죽는다.
#   (9/10 에 label-studio.exe 를 막았던 것과 같은 원인. setup-log.md 5-2, 5-3)
#
#   ultralytics 는 torchvision 을 NMS(겹친 박스 정리) 한 군데에만 쓰고,
#   torchvision 이 없을 때를 대비한 순수 PyTorch 구현(TorchNMS.nms)을 이미 갖고 있다.
#   그런데 추론 준비(warmup) 단계에서 `import torchvision` 을 무조건 실행하기 때문에
#   그 한 줄이 죽는다. 그래서 "torchvision" 이라는 이름의 가짜 모듈을 먼저 등록해 두고,
#   그 안의 ops.nms 자리에 ultralytics 의 순수 PyTorch NMS 를 꽂아 넣는다.
#   결과는 torchvision 이 있을 때와 같다 (ultralytics 문서: "matches torchvision behavior exactly").
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   추론을 하는 모든 스크립트(predict_count.py, 나중의 FastAPI 서버)가
#   `from ultralytics import YOLO` **보다 먼저** 이 파일을 import 한다. 순서가 바뀌면 효과가 없다.
#     import torchvision_shim   # noqa: F401  ← 이 줄이 위에
#     from ultralytics import YOLO
#   학습(train.py)은 Colab 에서 돌고 거기서는 torchvision 이 정상이라 이 파일이 필요 없다.
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   sys.modules : 파이썬이 "이미 불러온 모듈"을 이름 → 모듈 객체로 기억하는 딕셔너리.
#                 `import x` 는 먼저 여기서 "x" 를 찾고, 있으면 파일을 읽지 않고 그것을 돌려준다.
#                 그래서 여기에 미리 넣어 두면 진짜 파일 대신 우리가 만든 것이 쓰인다.
#   NMS (Non-Max Suppression) : 모델이 한 부품에 박스를 여러 개 겹쳐 내놓을 때
#                 확신도가 가장 높은 하나만 남기고 나머지를 지우는 절차. 개수 세기에 직접 영향을 준다.
#
#   ⚠️ Smart App Control 을 끄면 이 파일은 필요 없어진다. 다만 한 번 끄면 Windows 재설치 전엔
#      다시 켤 수 없어서(setup-log.md 5-2) 끄지 않고 우회했다.
# ─────────────────────────────────────────────────────────────────────────────

import sys  # sys.modules 에 가짜 모듈을 등록하려고
import types  # 빈 모듈 객체(ModuleType)와 속성 묶음(SimpleNamespace)을 만들려고

# ultralytics 가 torchvision 없이 쓰는 순수 PyTorch NMS. torchvision.ops.nms 와 인자·반환이 같다.
#   입력: boxes (N, 4) xyxy 텐서, scores (N,) 텐서, iou_threshold float
#   출력: 남길 박스의 인덱스 텐서
from ultralytics.utils.nms import TorchNMS

# 진짜 torchvision 이 이미 불려 있으면(다른 PC, Colab 등) 아무것도 하지 않는다.
# 이 파일을 어디서나 안전하게 import 할 수 있게 하려는 것이다.
if "torchvision" not in sys.modules:
    # 이름만 "torchvision" 인 빈 모듈을 만든다.
    _shim = types.ModuleType("torchvision")
    # ultralytics 가 부르는 것은 torchvision.ops.nms 하나뿐이다. 그 자리에 TorchNMS.nms 를 꽂는다.
    _shim.ops = types.SimpleNamespace(nms=TorchNMS.nms)
    # 버전 문자열을 보는 코드가 있어도 죽지 않도록 표시용 값을 둔다.
    _shim.__version__ = "0.0-shim"
    # 등록. 이 뒤로 `import torchvision` 과 `import torchvision.ops` 는 전부 이 가짜를 받는다.
    sys.modules["torchvision"] = _shim
    sys.modules["torchvision.ops"] = _shim.ops
