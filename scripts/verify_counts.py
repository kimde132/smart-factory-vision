# ─────────────────────────────────────────────────────────────────────────────
# 이 파일은 무엇을 하는가
#   계획대로 촬영이 되었는지, 라벨링은 올바르게 되었는지 1차적으로 검사한다.
#   촬영 계획과 export 파일을 비교한다.
#
# 프로젝트 실행 흐름에서 어느 위치인가
#   촬영 → 라벨링 → 현재 스크립트 → 분할 스크립트 → YOLO 학습
#
#   앞: 라벨링 후 export 한 파일, 촬영 계획서 csv
#   뒤: 결과를 보고 차이가 나는 부분을 직접 확인
#
# 이 파일을 이해하기 전에 알아야 할 개념
#   YOLO 라벨의 형식 : 라벨링 클래스가 가장 앞에 위치하고 뒤이어 박스 좌표 4개가 존재한다. 한 줄이 박스 하나이다.
#   images.csv는 계획이고 라벨링한 것이 실제이다.
#            csv는 촬영 "전"에 적어둔 의도이고, 라벨은 촬영 "후"에 사진을 보고 그린 것이다.
#            원래 같아야 하지만 손이 계획을 따라가지 못하면 어긋난다. s01에서 실제로 어긋났다.
#   이 스크립트는 파일을 수정하지 않는다. 어디가 틀렸는지 알 수 없기 때문이다. 결과를 보고 직접 사진을 확인해서 사용자가 직접 수정한다.
#   파일이름(s01_018)이 사진/라벨/csv를 연결해주는 유일한 키이다.
#
# 실행 방법
#   label studio에서 라벨링 후 export한 파일이 dataset/export에 있는지 확인 후 현재 파일 실행
#   ai-server\.venv\Scripts\python.exe scripts\verify_counts.py
#
# 관련 문서:
#   metadata/README.md(CSV 컬럼 설명), docs/labeling-guide.md 1-1(클래스 순서 원본), docs/decisions.md D-009(파일명 규칙)
# ─────────────────────────────────────────────────────────────────────────────


import pathlib  # 경로를 문자열로 저장하면 \같은 특수 문자의 경우 의도와 다르게 해석될 수 있다. 이 라이브러리를 통해 파일경로를 객체로 사용할 수 있다.
import urllib.parse  # URL 인코딩 관련, 경로에서 '\'가 %5C로 변경되는데 이걸 다시 돌려놓기위해서 사용한다.
import csv  # csv 파일을 읽고 이미지별 부품의 개수를 딕셔너리 형태로 쉽게 변경하기 위해서 사용한다.

# 현 프로젝트는 bolt, nut, washer를 구분하는 프로젝트이다.
# label studio에서 export하면 이름으로 나오는게 아니라 숫자로 나오기 때문에 이를 이름으로 변환하기위해서 생성했다.
# 지정한 0, 1, 2 순서는 label studio에서 고정한 클래스 번호이다. 프로젝트가 끝날 때가지 변하지 않는 순서이다.
# 원본은 docs/labeling-guide.md 1-1 표다. 여기와 data.yaml 은 그 표를 옮겨 적은 사본이므로 순서를 임의로 바꾸지 않는다.
CLASS_NAMES = {
    0: "bolt",
    1: "nut",
    2: "washer",
}

# label studio에서 export한 파일의 경로
# 프로젝트 폴더 이름(project-1-at-2026-08-25-...)은 export 할 때마다 새로 생기기 때문에
# 상수에는 export 까지만 담고, 그 아래는 main 에서 glob 으로 훑는다. 경로/*/labels/'*.txt'
# 그래서 export를 여러번 하게되면 중복이 발생한다. 현재는 export가 1개라서 이렇게 진행하고 추후 변경한다.
# __file__ 은 이 스크립트 파일 자신의 경로이고 .parent 는 한 단계 위 폴더를 뜻한다.
# 두 번 올라가면 scripts/ 를 지나 프로젝트 최상위가 되므로, 어느 폴더에서 실행해도 경로가 어긋나지 않는다.
LABEL_PATH = pathlib.Path(__file__).parent.parent / "dataset/export"

# 촬영 계획을 작성한 csv파일의 경로
CSV_PATH = pathlib.Path(__file__).parent.parent / "metadata/images.csv"


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
    # unquote 는 URL 인코딩을 원래 글자로 되돌린다. %5C -> \
    # 이 단계를 건너뛰면 아래 split 이 %5C 를 구분자로 알아보지 못한다.
    new_filename = urllib.parse.unquote(filename)
    # 원본 경로가 rename\s01\s01_018 형태로 들어 있으므로 \ 로 쪼갠다.
    # 파이썬에서 \ 는 이스케이프 문자라서, 글자 그대로 쓰려면 "\\" 로 두 번 적어야 한다.
    new_filename = new_filename.split("\\")
    # 마지막 조각이 실제 파일명이다. 앞쪽 조각에 붙어 있던 난수는 여기서 함께 버려진다.
    result = new_filename[-1]
    # .stem 은 확장자를 뗀 파일명이다. s01_018.txt -> s01_018
    # replace(".txt", "") 와 달리 파일명 중간에 .txt 가 들어 있어도 안전하다.
    result = pathlib.Path(result).stem
    return result


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
    # 세 클래스를 0으로 먼저 채워둔다.
    # 이렇게 하지 않으면 와셔가 한 개도 없는 사진에서 'washer' 키 자체가 생기지 않는다.
    # 그러면 대조하는 쪽에서 매번 .get(이름, 0) 을 써야 하고, 한 군데만 빠뜨려도 KeyError 가 난다.
    # 빈 트레이(s01_029, 0바이트)가 {0, 0, 0} 으로 나오는 것도 이 초기화 덕분이다.
    class_count = {}
    for class_name in CLASS_NAMES.values():
        class_count[class_name] = 0

    # with 문은 블록이 끝나면 예외가 나든 말든 파일을 반드시 닫아준다.
    with open(label_path, "r", encoding="utf-8") as f:
        # 파일 객체를 for 로 돌면 한 줄씩 읽힌다. 라벨은 한 줄이 박스 하나다.
        for line in f:
            # 공백으로 쪼갠다. "1 0.19 0.41 0.08 0.07" -> ['1', '0.19', '0.41', '0.08', '0.07']
            # line[0](첫 글자)이 아니라 split 을 쓰는 이유는, 클래스 번호가 10 이상이 되면
            # 첫 글자만 읽고 조용히 틀린 값을 세기 때문이다.
            split_line = line.split()
            # 빈 줄이면 split 결과가 [] 라서 아래 [0] 에서 IndexError 가 난다. 건너뛴다.
            if not split_line:
                continue
            # 파일에서 읽은 값은 전부 문자열이다. '1' 과 1 은 다른 값이라
            # int() 로 바꾸지 않으면 CLASS_NAMES['1'] 에서 KeyError 가 난다.
            class_name = CLASS_NAMES[int(split_line[0])]
            # 같은 클래스가 여러 개 나오므로 클래스별로 누적한다.
            class_count[class_name] += 1

    return class_count


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
        # DictReader 는 첫 줄을 헤더로 읽어서, 각 행을 {컬럼명: 값} 딕셔너리로 돌려준다.
        # 컬럼 순서가 바뀌어도 깨지지 않는다.
        reader = csv.DictReader(f)
        for row in reader:
            # CSV 에서 읽은 값은 전부 문자열이다. '0' 과 0 은 다른 값이라
            # int() 로 바꾸지 않으면 나중에 개수 비교에서 35장 전부 불일치로 나온다.
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
    # [1단계] 계획 쪽을 통째로 읽어온다.
    planned = load_planned_counts(CSV_PATH)

    # [2단계] 실제 쪽을 만든다. planned 와 같은 모양이 되도록 쌓는다.
    actual = {}
    # glob 은 폴더를 훑어서 조건에 맞는 파일을 전부 찾아준다. * 는 "아무거나" 라는 뜻이다.
    # */labels/*.txt = "export 아래 아무 폴더 안의 labels 안의 아무 .txt".
    # 개수를 코드에 적지 않으므로 세션이 10개로 늘어도 이 줄은 그대로다.
    for label_file in LABEL_PATH.glob("*/labels/*.txt"):
        # glob 이 돌려주는 것은 문자열이 아니라 Path 객체다.
        # .name 은 파일명 문자열이라 파싱에 쓰고, label_file 자체는 파일을 열 때 쓴다.
        name = parse_label_filename(label_file.name)
        count = count_classes(label_file)
        # 딕셔너리는 같은 키에 또 넣으면 앞의 것을 조용히 덮어쓴다.
        # export 폴더가 2개 이상 쌓이면 같은 이름이 두 번 잡히는데, 개수는 그대로라
        # 아무 이상이 없어 보인다. 그래서 덮어쓰지 않고 멈춘다.
        if name in actual:
            print(f"{name} 중복입니다.")
            return
        actual[name] = count

    # [3단계] 개수보다 이름을 먼저 비교한다.
    # 35 대 35 로 개수가 같아도 이름이 다를 수 있고, 여기가 어긋나 있으면 개수 비교는 의미가 없다.
    # 딕셔너리를 set() 에 넣으면 키만 모인다. 집합끼리 빼면 "한쪽에만 있는 것" 이 나온다.
    only_label = set(actual) - set(planned)
    only_plan = set(planned) - set(actual)

    if len(only_label) == 0 and len(only_plan) == 0:
        print("이름 불일치 없음")
    else:
        # f-string 은 문자열 앞에 f 를 붙이면 {} 안의 값이 그 자리에 끼워 넣어지는 문법이다.
        print(f"계획에만 있는 것: {only_plan}")
        print(f"라벨에만 있는 것: {only_label}")

    # [4단계] 양쪽에 다 있는 이름만 개수를 비교한다. & 는 교집합이다.
    # 정렬하는 이유는 출력이 s01_001 순서로 나와야 이 결과를 보며
    # images.csv 를 위에서 아래로 훑어 고칠 수 있기 때문이다.
    common = set(actual) & set(planned)
    sort_common = sorted(common)
    mismatch_images = 0  # 장 수
    mismatch_items = 0  # 부품 수
    print("[개수 검사]")
    for file_name in sort_common:
        # 딕셔너리는 통째로 비교가 된다. 세 부품이 전부 같으면 아래를 돌 필요가 없다.
        if actual[file_name] != planned[file_name]:
            mismatch_images += 1
            for class_name in CLASS_NAMES.values():
                actual_count = actual[file_name][class_name]
                plan_count = planned[file_name][class_name]
                if plan_count != actual_count:
                    # 괄호 안은 실제 - 계획이다. 부호로 몇 개 더 놓였는지 덜 놓였는지가 보인다.
                    print(
                        f"파일명: {file_name} 부품: {class_name} 계획: {plan_count} 실제: {actual_count} ({actual_count - plan_count})"
                    )
                    mismatch_items += 1
    # [5단계] 요약. 한 장에서 두 부품이 틀리면 장 수는 1, 건수는 2 늘어난다.
    if mismatch_images == 0:
        print("검사완료 이상 없음")
    else:
        print(
            f"총 {len(common)}장 중 {mismatch_images}장에서 총 {mismatch_items}건 불일치"
        )


# 이 파일을 직접 실행했을 때만 main() 을 부른다.
# 다른 파일에서 from verify_counts import count_classes 처럼 함수만 가져다 쓸 때
# main() 이 멋대로 실행되는 것을 막아준다.
if __name__ == "__main__":
    main()
