# ╔══════════════════════════════════════════════════════════════════════════════════════════╗
# ║  verify_counts.py — 촬영 계획(images.csv)과 라벨링 결과(YOLO 라벨 .txt)의 부품 개수를 대조한다        ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════╝
#
# ┌ 0. 이 파일은 무엇이고 언제 돌리나 ─────────────────────────────────────────────────────────
# │
# │  계획대로 촬영이 되었는지, 라벨링은 올바르게 되었는지 1차적으로 검사한다. 촬영 계획과 export 파일을 비교한다.
# │  파일을 수정하지 않는다. 어디가 틀렸는지(csv 탓인지 라벨 탓인지) 코드는 알 수 없기 때문이다. 결과를 보고 사용자가 사진을 확인해 직접 고친다.
# │
# │  촬영 → 라벨링 → [현재 파일] → split_dataset.py → train.py
# │  앞: 라벨링 후 Label Studio 에서 export 한 폴더가 dataset/export 에 있어야 한다. 촬영 계획서 metadata/images.csv.
# │  뒤: 결과를 보고 차이가 나는 부분을 직접 확인. 0건("검사완료 이상 없음")이어야 다음 단계로 간다.
# │      s01 은 35장 중 16장 24건이 어긋났고(23건 csv, 1건 라벨), s02~s09 는 0건.
# │
# │  실행 (프로젝트 최상위에서)
# │      ai-server\.venv\Scripts\python.exe scripts\verify_counts.py
# │
# │  실행 순서: main() → load_planned_counts(csv) → export 폴더의 라벨 .txt 마다 parse_label_filename + count_classes → 이름 비교 → 개수 비교 → 요약
# │
# ├ 1. 이름은 세 종류 ─────────────────────────────────────────────────────────────────────
# │
# │  ① Python 키워드      : import def return for in with if not else continue
# │  ② 라이브러리가 정한 이름
# │       pathlib.Path .parent .stem .glob .name        ← pathlib (Python 기본)
# │       urllib.parse.unquote                           ← urllib (Python 기본)
# │       csv.DictReader                                 ← csv (Python 기본)
# │       open .split .values .items set sorted len print  ← Python 내장
# │  ③ 내가 지은 이름
# │       상수: CLASS_NAMES LABEL_PATH CSV_PATH
# │       함수: parse_label_filename count_classes load_planned_counts main
# │       변수: new_filename result class_count class_name split_line reader row planned actual label_file name count
# │             only_label only_plan common sort_common mismatch_images mismatch_items file_name actual_count plan_count
# │       csv 컬럼 이름: image_name bolt_count nut_count washer_count  (metadata/README.md 에 정의)
# │
# ├ 2. import 사전 ────────────────────────────────────────────────────────────────────────
# │
# │  import pathlib        (Python 기본) → 경로 객체. 여기서는 from … import Path 대신 모듈째 가져와 pathlib.Path 로 쓴다(같은 것)
# │  import urllib.parse   (Python 기본) → %5C 같은 URL 인코딩 되돌리기
# │  import csv            (Python 기본) → csv 파일을 행 단위 딕셔너리로 읽기
# │
# ├ 3. 알아야 할 개념 ───────────────────────────────────────────────────────────────────
# │
# │  YOLO 라벨 형식  : 한 줄이 박스 하나. "클래스번호 x중심 y중심 너비 높이" (좌표는 0~1 비율). 예: "1 0.19 0.41 0.08 0.07"
# │                    이 스크립트는 첫 칸(클래스 번호)만 센다. 좌표는 안 본다.
# │  계획 vs 실제    : images.csv 는 촬영 "전" 에 적어둔 의도이고, 라벨은 촬영 "후" 에 사진을 보고 그린 것.
# │                    원래 같아야 하지만 손이 계획을 따라가지 못하면 어긋난다. s01 에서 실제로 어긋났다(D-012).
# │  키              : 파일이름(s01_018)이 사진/라벨/csv 를 연결해 주는 유일한 키다.
# │  Label Studio export 이름 : 1ffa3f20__rename%5Cs01%5Cs01_018.txt 처럼 난수 + 경로가 URL 인코딩되어 붙어 있다. 그래서 parse_label_filename 이 필요.
# │
# │  자료 모양
# │    count_classes 출력       : {'bolt': 5, 'nut': 5, 'washer': 3}                       ← 세 키 항상 있음
# │    load_planned_counts 출력 : {'s01_001': {'bolt': 0, 'nut': 2, 'washer': 4}, …}        ← 위와 안쪽 모양이 같다
# │    actual (main 안)         : 위와 같은 모양, 라벨에서 만든 것
# │
# │  관련 문서: metadata/README.md(CSV 컬럼 설명), docs/labeling-guide.md 1-1(클래스 순서 원본), docs/decisions.md D-009(파일명 규칙)·D-012(수량 오류 대책)
# └────────────────────────────────────────────────────────────────────────────────────────


# ▸ import pathlib(② 모듈째): 경로를 문자열로 저장하면 \ 같은 특수 문자가 의도와 다르게 해석될 수 있다. 객체로 다루면 안전하다. 아래에서 pathlib.Path 로 쓴다.
import pathlib  # 경로를 문자열로 저장하면 \같은 특수 문자의 경우 의도와 다르게 해석될 수 있다. 이 라이브러리를 통해 파일경로를 객체로 사용할 수 있다.
# ▸ import urllib.parse(② URL 다루기): export 파일 이름에서 경로 구분자 \ 가 %5C 로 바뀌어 있는데, 이걸 다시 돌려놓기 위해(unquote).
import urllib.parse  # URL 인코딩 관련, 경로에서 '\'가 %5C로 변경되는데 이걸 다시 돌려놓기위해서 사용한다.
# ▸ import csv(② csv 읽기·쓰기): images.csv 를 행마다 딕셔너리로 읽으려고(DictReader).
import csv  # csv 파일을 읽고 이미지별 부품의 개수를 딕셔너리 형태로 쉽게 변경하기 위해서 사용한다.

# ▸ 단어 분해: CLASS_NAMES(③) = { 0(정수 키): "bolt", 1: "nut", 2: "washer" }   (딕셔너리)
# ▸ 뜻: 클래스 번호 → 이름. Label Studio 가 export 하면 이름이 아니라 숫자로 나오기 때문에 이름으로 바꾸려고.
# ▸ 0, 1, 2 순서는 Label Studio 에서 고정한 클래스 번호. 프로젝트가 끝날 때까지 변하지 않는 순서.
# ▸ 원본은 docs/labeling-guide.md 1-1 표. 여기와 data.yaml 은 그 표를 옮겨 적은 사본이므로 순서를 임의로 바꾸지 않는다.
# ▸ predict_count.py 는 같은 것을 튜플 ("bolt", "nut", "washer") 로 갖고 있다. 여기선 번호로 찾아야 해서 딕셔너리.
CLASS_NAMES = {
    0: "bolt",
    1: "nut",
    2: "washer",
}

# ▸ 단어 분해: LABEL_PATH(③) = pathlib.Path(__file__).parent(scripts/).parent(최상위) / "dataset/export"
# ▸ 뜻: Label Studio 가 export 한 폴더들의 부모. 실제 라벨은 그 아래 project-1-at-2026-08-25-…/labels/*.txt.
# ▸ 왜 export 까지만: 프로젝트 폴더 이름(project-1-at-…)은 export 할 때마다 새로 생기기 때문에 상수에는 export 까지만 담고, 그 아래는 main 에서 glob 으로 훑는다.
# ▸ 그래서 export 를 여러 번 하면 같은 이름이 중복으로 잡힌다. main 이 중복을 만나면 멈추게 해 뒀다(상태판 "export 를 두 벌 이상 쌓지 말 것").
# ▸ __file__ 은 이 파일 자신의 경로, .parent 는 한 단계 위. 두 번 올라가면 최상위라 어느 폴더에서 실행해도 어긋나지 않는다. (resolve() 는 안 썼다 — 절대 경로로 실행하면 문제없다)
LABEL_PATH = pathlib.Path(__file__).parent.parent / "dataset/export"

# ▸ CSV_PATH(③): 촬영 계획을 작성한 csv 파일의 경로. metadata/ 는 git 에 남는 유일한 데이터 근거.
CSV_PATH = pathlib.Path(__file__).parent.parent / "metadata/images.csv"


# ═══════════════════════════════════════════════════════════════════════════════════════════
#  함수 넷 — 이름 뽑기 / 라벨 세기 / csv 읽기 / 대조
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ▸ 단어 분해: def parse_label_filename(③)(filename(③ 문자열 인자)):
def parse_label_filename(filename):
    """파일명에서 난수, 경로, 확장자를 제외한 파일 이름을 추출한다.

    사진 / 라벨 / images.csv 셋을 짝지을 수 있는 유일한 키가 이 이름이다.

    입력:
        filename(str): 폴더에 저장되어있는 파일의 이름 예) 1ffa3f20__rename%5Cs01%5Cs01_018.txt

    출력:
        파일 이름에서 난수, 경로, 확장자를 제외한 이름(str) 예) s01_018

    실패 시:
        예외는 나지 않는다. 대신 조건이 깨지면 조용히 틀린 값을 돌려주므로 그쪽이 더 위험하다.
        난수(1ffa3f20__)가 지금 떨어져 나가는 것은 그것이 "1ffa3f20__rename" 이라는
        앞쪽 경로 조각에 붙어 있어서, 마지막 조각을 고르면 함께 버려지기 때문이다.
        label studio 스토리지를 dataset/rename/s01 처럼 세션 폴더로 직접 잡으면
        파일명에 경로 구분자가 없어져 "1ffa3f20__s01_018" 이 그대로 남는다.
        다만 그 경우 main 의 이름 집합 비교에서 "라벨에만 있는 것" 으로 드러난다.
    """
    # ▸ 단어 분해: new_filename(③) = urllib.parse.unquote(② URL 인코딩 되돌리기)(filename)
    # ▸ 뜻: %5C → \ . "1ffa3f20__rename%5Cs01%5Cs01_018.txt" → "1ffa3f20__rename\s01\s01_018.txt"
    # ▸ 왜: 이 단계를 건너뛰면 아래 split 이 %5C 를 구분자로 알아보지 못한다.
    new_filename = urllib.parse.unquote(filename)
    # ▸ 단어 분해: new_filename = new_filename.split(② 구분자로 쪼개 리스트로)("\\"(백슬래시 한 글자))
    # ▸ 뜻: ["1ffa3f20__rename", "s01", "s01_018.txt"]. 같은 변수에 다시 넣었으니 이제 문자열이 아니라 리스트다.
    # ▸ 왜 "\\": 파이썬에서 \ 는 이스케이프 문자라서, 글자 그대로 쓰려면 "\\" 로 두 번 적어야 한다.
    new_filename = new_filename.split("\\")
    # ▸ result(③) = new_filename[-1](① 음수 인덱스 = 뒤에서 첫 번째)
    # ▸ 마지막 조각이 실제 파일명이다. 앞쪽 조각에 붙어 있던 난수는 여기서 함께 버려진다.
    result = new_filename[-1]
    # ▸ result = pathlib.Path(result).stem(② 확장자를 뗀 파일명): s01_018.txt → s01_018
    # ▸ 다른 선택: replace(".txt", "") 도 되지만 파일명 중간에 .txt 가 들어 있으면 그것까지 지운다. .stem 이 안전하다.
    result = pathlib.Path(result).stem
    return result


# ▸ 단어 분해: def count_classes(③)(label_path(③ Path 객체 인자)):
def count_classes(label_path):
    """export된 라벨링 파일에서 각 클래스별로 라벨링이 몇개되어있는지 확인한다.

    입력:
        label_path(Path객체) : 라벨 파일 "한 개"의 경로. 폴더가 아니다.
                               예) dataset/export/project-1-at-.../labels/1ffa3f20__....txt

    출력:
        class_count(딕셔너리) : 라벨링 파일에 클래스별로 개수를 정리한 딕셔너리
                                예) {'bolt': 5, 'nut': 5, 'washer': 3}
                                세 키는 항상 들어 있다. 0개인 부품도 0으로 채워서 돌려준다.

    실패 시:
        라벨에 CLASS_NAMES에 없던 숫자(예: 3)가 있으면 KeyError 가 난다.
        첫 조각이 숫자가 아니면 int() 에서 ValueError, 파일이 없으면 open() 에서 FileNotFoundError.
        어느 쪽이든 멈추는 편이 낫다. 조용히 넘어가면 개수가 틀린 채로 대조가 진행된다.
    """
    # ▸ 단어 분해: class_count(③) = {}(빈 딕셔너리) → for class_name in CLASS_NAMES.values(② 값들만: "bolt","nut","washer")(): class_count[class_name] = 0
    # ▸ 뜻: 세 클래스를 0 으로 먼저 채워 둔다. predict_count.py 의 딕셔너리 컴프리헨션 {name: 0 for …} 과 같은 일을 for 문으로 쓴 것.
    # ▸ 왜: 이렇게 하지 않으면 와셔가 한 개도 없는 사진에서 'washer' 키 자체가 생기지 않는다.
    #   그러면 대조하는 쪽에서 매번 .get(이름, 0) 을 써야 하고, 한 군데만 빠뜨려도 KeyError 가 난다.
    #   빈 트레이(s01_029, 0바이트 라벨)가 {0, 0, 0} 으로 나오는 것도 이 초기화 덕분이다.
    class_count = {}
    for class_name in CLASS_NAMES.values():
        class_count[class_name] = 0

    # ▸ 단어 분해: with(① 끝나면 닫기) open(② 파일 열기)(label_path, "r"(읽기 모드), encoding="utf-8") as f(③ 파일 객체):
    # ▸ with 문은 블록이 끝나면 예외가 나든 말든 파일을 반드시 닫아 준다.
    with open(label_path, "r", encoding="utf-8") as f:
        # ▸ for line(③) in f: 파일 객체를 for 로 돌면 한 줄씩 읽힌다. 라벨은 한 줄이 박스 하나.
        for line in f:
            # ▸ split_line(③) = line.split(② 공백으로 쪼개기)()  — 인자 없으면 공백·탭·줄바꿈 전부 구분자.
            # ▸ "1 0.19 0.41 0.08 0.07" → ['1', '0.19', '0.41', '0.08', '0.07']
            # ▸ 왜 line[0](첫 글자)이 아니라 split: 클래스 번호가 10 이상이 되면 첫 글자만 읽고 조용히 틀린 값을 센다.
            split_line = line.split()
            # ▸ if not split_line: 빈 줄이면 split 결과가 [] 라서 아래 [0] 에서 IndexError. continue(① 이번 줄 건너뛰고 다음 줄).
            if not split_line:
                continue
            # ▸ 단어 분해: class_name(③) = CLASS_NAMES[ int(② 글자→정수)(split_line[0](첫 칸)) ]
            # ▸ 왜 int(): 파일에서 읽은 값은 전부 문자열이다. '1' 과 1 은 다른 값이라 int() 로 바꾸지 않으면 CLASS_NAMES['1'] 에서 KeyError.
            class_name = CLASS_NAMES[int(split_line[0])]
            # ▸ class_count[class_name] += 1 : 같은 클래스가 여러 개 나오므로 클래스별로 누적한다.
            class_count[class_name] += 1

    return class_count


# ▸ 단어 분해: def load_planned_counts(③)(csv_path(③)):
def load_planned_counts(csv_path):
    """images.csv 를 읽어 사진별 "계획" 개수를 돌려준다.

    출력 모양을 count_classes 와 똑같이 맞춘 것이 요점이다.
    모양이 같아야 main 에서 값만 비교하면 되고, 다르면 비교하면서 변환까지 해야 한다.

    입력:
        csv_path(Path객체) : metadata/images.csv 의 경로

    출력:
        result(딕셔너리) : {사진이름: {부품이름: 개수}} 형태
                           예) {'s01_001': {'bolt': 0, 'nut': 2, 'washer': 4}, ...}

    실패 시:
        컬럼 이름이 바뀌면 row["bolt_count"] 에서 KeyError 가 난다.
        숫자 칸이 비어 있거나 숫자가 아니면 int() 에서 ValueError,
        파일이 없으면 open() 에서 FileNotFoundError 가 난다.
    """
    result = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        # ▸ reader(③) = csv.DictReader(② 클래스)(f)
        # ▸ 뜻: 첫 줄을 헤더로 읽어서, 각 행을 {컬럼명: 값} 딕셔너리로 돌려주는 읽기 객체. 컬럼 순서가 바뀌어도 깨지지 않는다.
        # ▸ 다른 선택: csv.reader 는 각 행을 리스트로 준다. 그러면 row[3] 처럼 순번으로 꺼내야 해서 컬럼이 늘면 깨진다.
        reader = csv.DictReader(f)
        # ▸ for row(③ 딕셔너리 하나 = 사진 한 장) in reader:
        for row in reader:
            # ▸ 단어 분해: result[ row["image_name"](키) ] = { "bolt": int(row["bolt_count"]), … }
            # ▸ 왜 int(): CSV 에서 읽은 값은 전부 문자열이다. '0' 과 0 은 다른 값이라 int() 로 바꾸지 않으면 나중에 개수 비교에서 35장 전부 불일치로 나온다.
            # ▸ 키 이름 "bolt"/"nut"/"washer" 는 count_classes 의 출력과 같게. 컬럼 이름 bolt_count 등은 metadata/README.md 에 정의된 것.
            result[row["image_name"]] = {
                "bolt": int(row["bolt_count"]),
                "nut": int(row["nut_count"]),
                "washer": int(row["washer_count"]),
            }
    return result


def main():
    """위 3가지 함수를 불러서 계획(csv)과 실제(라벨)를 대조하고 어긋난 것만 출력한다.

    파일을 "찾는" 일은 이 함수만 한다. 나머지 세 함수는 받은 것만 처리한다.

    출력:
        없다(None). 결과는 print 로만 내보낸다.
        파일은 하나도 쓰지 않는다. 어긋남이 csv 탓인지 라벨 탓인지는 사람이 판단해야 하기 때문이다.

    실패 시:
        같은 이름이 두 번 잡히면 경고를 찍고 중간에 멈춘다(return).
        그 밖의 예외는 위 세 함수의 "실패 시" 를 그대로 따른다.
    """
    # ▸ [1단계] 계획 쪽을 통째로 읽어온다. planned(③) = {'s01_001': {...}, …}
    planned = load_planned_counts(CSV_PATH)

    # ▸ [2단계] 실제 쪽을 만든다. planned 와 같은 모양이 되도록 쌓는다.
    actual = {}
    # ▸ 단어 분해: for label_file(③ Path) in LABEL_PATH.glob(② 패턴에 맞는 파일 찾기)("*/labels/*.txt"):
    # ▸ 뜻: "export 아래 아무 폴더 안의 labels 안의 아무 .txt". * 는 "아무거나".
    # ▸ 개수를 코드에 적지 않으므로 세션이 10개로 늘어도 이 줄은 그대로다.
    for label_file in LABEL_PATH.glob("*/labels/*.txt"):
        # ▸ glob 이 돌려주는 것은 문자열이 아니라 Path 객체다. .name(② 파일명 문자열)은 파싱에 쓰고, label_file 자체는 파일을 열 때 쓴다.
        name = parse_label_filename(label_file.name)
        count = count_classes(label_file)
        # ▸ if name in actual: 이미 같은 키가 있으면 — 딕셔너리는 같은 키에 또 넣으면 앞의 것을 조용히 덮어쓴다.
        # ▸ export 폴더가 2개 이상 쌓이면 같은 이름이 두 번 잡히는데, 개수는 그대로라 아무 이상이 없어 보인다. 그래서 덮어쓰지 않고 멈춘다(return).
        if name in actual:
            print(f"{name} 중복입니다.")
            return
        actual[name] = count

    # ▸ [3단계] 개수보다 이름을 먼저 비교한다. 35 대 35 로 개수가 같아도 이름이 다를 수 있고, 여기가 어긋나 있으면 개수 비교는 의미가 없다.
    # ▸ 단어 분해: only_label(③) = set(② 집합으로)(actual)(딕셔너리를 set 에 넣으면 키만 모인다) -(① 집합 빼기: 왼쪽에만 있는 것) set(planned)
    only_label = set(actual) - set(planned)
    only_plan = set(planned) - set(actual)

    # ▸ len(② 개수)(only_label) == 0 and(① 둘 다) len(only_plan) == 0 : 양쪽 다 비었으면 이름이 정확히 일치.
    if len(only_label) == 0 and len(only_plan) == 0:
        print("이름 불일치 없음")
    else:
        # ▸ f-string: 문자열 앞에 f 를 붙이면 {} 안의 값이 그 자리에 끼워 넣어진다. 집합을 그대로 넣으면 {'s01_036', …} 꼴로 찍힌다.
        print(f"계획에만 있는 것: {only_plan}")
        print(f"라벨에만 있는 것: {only_label}")

    # ▸ [4단계] 양쪽에 다 있는 이름만 개수를 비교한다. &(① 교집합) 는 둘 다에 있는 것.
    # ▸ sorted(② 정렬된 리스트로): 출력이 s01_001 순서로 나와야 이 결과를 보며 images.csv 를 위에서 아래로 훑어 고칠 수 있다. 집합은 순서가 없다.
    common = set(actual) & set(planned)
    sort_common = sorted(common)
    mismatch_images = 0  # 장 수
    mismatch_items = 0  # 부품 수
    print("[개수 검사]")
    for file_name in sort_common:
        # ▸ if actual[file_name] != planned[file_name]: 딕셔너리는 통째로 비교가 된다. 세 부품이 전부 같으면 아래를 돌 필요가 없다.
        if actual[file_name] != planned[file_name]:
            mismatch_images += 1
            # ▸ 어느 부품이 얼마나 틀렸는지 부품별로 다시 본다.
            for class_name in CLASS_NAMES.values():
                actual_count = actual[file_name][class_name]
                plan_count = planned[file_name][class_name]
                if plan_count != actual_count:
                    # ▸ 괄호 안은 실제 - 계획. 부호로 몇 개 더 놓였는지(+) 덜 놓였는지(-)가 보인다.
                    print(
                        f"파일명: {file_name} 부품: {class_name} 계획: {plan_count} 실제: {actual_count} ({actual_count - plan_count})"
                    )
                    mismatch_items += 1
    # ▸ [5단계] 요약. 한 장에서 두 부품이 틀리면 장 수는 1, 건수는 2 늘어난다. s01 이 "16장 24건" 이었던 이유.
    if mismatch_images == 0:
        print("검사완료 이상 없음")
    else:
        print(
            f"총 {len(common)}장 중 {mismatch_images}장에서 총 {mismatch_items}건 불일치"
        )


# ▸ 이 파일을 직접 실행했을 때만 main() 을 부른다.
# ▸ predict_count.py·split_dataset.py 가 from verify_counts import … 로 함수만 가져다 쓸 때 main() 이 멋대로 실행되는 것을 막아준다.
if __name__ == "__main__":
    main()
