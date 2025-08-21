from shape import Shape
from i18n import t


def 가장오른쪽_클러스터_위치찾기(s, char):
    """가장 오른쪽 특정 문자 클러스터의 가장 왼쪽 위치를 찾음"""
    for i in range(len(s)-1, -1, -1):
        if s[i] == char:
            # 연속된 문자의 시작점을 찾음
            cluster_start = i
            while cluster_start > 0 and s[cluster_start-1] == char:
                cluster_start -= 1
            # 클러스터의 가장 왼쪽보다 한 칸 왼쪽 위치
            return cluster_start - 1 if cluster_start > 0 else 0
    return -1

def 가장가까운_왼쪽문자_찾기(arr, start_pos, target_char):
    """가장 가까운 왼쪽의 특정 문자를 찾음"""
    for j in range(start_pos - 1, -1, -1):
        if arr[j] == target_char:
            return j
    return -1

def 왼쪽문자_개수세기(arr, pos, char):
    """특정 위치 왼쪽의 특정 문자 개수를 세기"""
    count = 0
    for k in range(pos - 1, -1, -1):
        if arr[k] == char:
            count += 1
        else:
            break
    return count

def 위치의_문자교체(arr, pos, old_char, new_char):
    """특정 위치의 문자를 다른 문자로 교체"""
    if 0 <= pos < len(arr) and arr[pos] == old_char:
        arr[pos] = new_char
        return True
    return False

def 가장높은_c층_찾기(s):
    """문자열에서 가장 높은 c 층을 찾음"""
    for i in range(len(s) - 1, -1, -1):  # 위에서부터 아래로 검사
        if s[i] == 'c':
            return i
    return -1  # c가 없는 경우

def 빈공간을_문자로채우기(arr, empty_char, fill_char, max_layer=None):
    """빈 공간을 특정 문자로 채움 (최대 층 제한 가능)"""
    if max_layer is None:
        max_layer = len(arr)
    
    for i in range(min(len(arr), max_layer + 1)):
        if arr[i] == empty_char:
            arr[i] = fill_char

def 특정위치들에_문자추가(arr, positions, char):
    """특정 위치들에 문자를 추가"""
    for pos in positions:
        if 0 <= pos < len(arr):
            arr[pos] = char

def 범위내_문자를다른문자로채우기(arr, start, end, target_char, fill_char):
    """범위 내의 특정 문자를 다른 문자로 채움"""
    for i in range(start, min(end + 1, len(arr))):
        if arr[i] == target_char:
            arr[i] = fill_char

def 모든문자_교체(arr, old_char, new_char):
    """모든 특정 문자를 다른 문자로 교체"""
    for i in range(len(arr)):
        if arr[i] == old_char:
            arr[i] = new_char

def 배열_시프트(arr, shift_char):
    """첫 글자를 삭제하고 맨 뒤에 특정 문자를 추가"""
    return arr[1:] + [shift_char]

def 범위를_문자로설정(arr, start, end, char):
    """범위를 특정 문자로 설정"""
    for i in range(start, min(end + 1, len(arr))):
        arr[i] = char

def 특정위치들_문자교체(arr, positions, exclude_positions, old_char, new_char):
    """특정 위치들에서 문자를 교체 (제외 위치 고려)"""
    for pos in positions:
        if pos not in exclude_positions and 0 <= pos < len(arr) and arr[pos] == old_char:
            arr[pos] = new_char

def 높이패턴_적용(arr, positions, heights, char):
    """각 위치를 특정 문자로 바꾸고, 높이만큼 왼쪽을 같은 문자로 바꿈"""
    for idx, pos in enumerate(positions):
        if 0 <= pos < len(arr):
            arr[pos] = char
        height = heights[idx]
        for j in range(1, height + 1):
            if pos - j >= 0:
                arr[pos - j] = char

def 채워진배열_생성(length, fill_char):
    """특정 길이의 특정 문자로 가득찬 배열 생성"""
    return [fill_char] * length

def 문자위치들_가져오기(s, *chars):
    """문자열에서 특정 문자들의 위치를 반환"""
    return [i for i, ch in enumerate(s) if ch in chars]

def Drop정보_수집(s):
    """모든 c에 대해 반복하여 Drop 관련 정보를 수집"""
    Drop_위치 = []
    Drop_높이 = []
    Drop_새위치 = []
    
    A = list(s)
    cIndices = [i for i, ch in enumerate(A) if ch == 'c']
    
    i = 0
    while i < len(cIndices):
        cIdx = cIndices[i]
        # c 왼쪽이 - 라면
        if cIdx > 0 and A[cIdx - 1] == '-':
            # 가장 가까운 왼쪽 S를 찾음
            sIdx = 가장가까운_왼쪽문자_찾기(A, cIdx, 'S')
            if sIdx != -1:
                Drop_위치.append(sIdx)
                # sIdx 왼쪽의 - 개수 세기
                spaceCount = 왼쪽문자_개수세기(A, sIdx, '-')
                
                # S의 아래가 첫 문자열까지 -로 연속되어있다면 높이에서 1을 뺀다
                if spaceCount == sIdx:
                    spaceCount -= 1
                
                Drop_높이.append(spaceCount)
                # 새 위치 기록 (c 왼쪽)
                newSIdx = cIdx - 1
                Drop_새위치.append(newSIdx)
                # S를 -로 제거만 함
                위치의_문자교체(A, sIdx, 'S', '-')
        i += 1
    
    return Drop_위치, Drop_높이, Drop_새위치, A

def build_cutable_shape(s):
    L = len(s)
    
    # 가장 오른쪽 c 클러스터의 가장 왼쪽 위치를 찾음
    L2 = 가장오른쪽_클러스터_위치찾기(s, 'c')
    
    # Drop 관련 정보 수집
    Drop_위치, Drop_높이, Drop_새위치, A_modified = Drop정보_수집(s)
    
    # A 처리: S가 제거된 상태를 저장
    AA = A_modified.copy()
    A = A_modified.copy()
    
    # A: 가장 높은 c 층까지만 빈 공간을 c로 채움
    highest_layer = 가장높은_c층_찾기(s)
    if highest_layer != -1:
        빈공간을_문자로채우기(A, '-', 'c', highest_layer)
    
    # A: Drop_새위치에 S 추가
    특정위치들에_문자추가(A, Drop_새위치, 'S')
    
    # B 처리: AA를 복사하여 처리
    B = AA.copy()
    
    # B: L2까지의 빈 공간을 P로 채움
    if L2 != -1:
        범위내_문자를다른문자로채우기(B, 0, L2, '-', 'P')
    
    # B: c를 S로 바꿈
    모든문자_교체(B, 'c', 'S')
    
    # B: 가장 높은 c층 이상의 빈 공간을 S로 채움
    if highest_layer != -1:
        for i in range(highest_layer, len(B)):
            if B[i] == '-':
                B[i] = 'S'
    
    # C 처리: L 길이의 -로 가득찬 리스트 생성
    C = 채워진배열_생성(L, '-')
    originalC_S_indices = 문자위치들_가져오기(s, 'c', 'S')
    
    # C: L2까지 c로 바꿈
    if L2 != -1:
        범위를_문자로설정(C, 0, L2, 'c')
    
    # C: 모든 Drop_위치를 제외한 입력 str의 각 c와 s의 위치를 C에서 그 위치들에서 c를 S로 바꿈
    특정위치들_문자교체(C, originalC_S_indices, Drop_위치, 'c', 'S')
    
    # D: L길이의 -로 가득찬 리스트 생성
    D = 채워진배열_생성(L, '-')
    
    return format_final_result(A, B, C, D)

def build_pinable_shape(s):
    L = max(len(s), Shape.MAX_LAYERS)
    
    # 가장 오른쪽 c 클러스터의 가장 왼쪽 위치를 찾음
    L2 = 가장오른쪽_클러스터_위치찾기(s, 'c')
    
    # Drop 관련 정보 수집
    Drop_위치, Drop_높이, Drop_새위치, A_modified = Drop정보_수집(s)
    
    # A 처리: S가 제거된 상태를 저장
    AA = A_modified.copy()
    A = A_modified.copy()
    
    # A: 가장 높은 c 층까지만 빈 공간을 c로 채움
    highest_layer = 가장높은_c층_찾기(s)
    if highest_layer != -1:
        빈공간을_문자로채우기(A, '-', 'c', highest_layer)
    
    # A: Drop_새위치에 S 추가
    특정위치들에_문자추가(A, Drop_새위치, 'S')
    
    # A: 첫 글자를 삭제함. 맨 뒤에 - 추가
    A = 배열_시프트(A, '-')
    
    # A: s의 첫 글자가 -인 경우, A의 첫 글자부터 연속된 c를 -로 변경
    if s and (s[0] in ['-', 'S']):
        for i in range(len(A)):
            if A[i] == 'c':
                A[i] = '-'
            else:
                break
    
    # B 처리: 원본을 복사하여 처리
    B = list(s)
    
    # B: L2까지의 빈 공간을 P로 채움
    if L2 != -1:
        범위내_문자를다른문자로채우기(B, 0, L2, '-', 'P')
    
    # B: c를 S로 바꿈
    모든문자_교체(B, 'c', 'S')
    
    # B: 가장 높은 c층 이상의 빈 공간을 S로 채움
    if highest_layer != -1:
        for i in range(highest_layer, len(B)):
            if B[i] == '-':
                B[i] = 'S'
    
    # B: 첫 글자를 삭제함. 맨 뒤에 - 추가
    B = 배열_시프트(B, '-')
    
    # C 처리: L 길이의 -로 가득찬 리스트 생성
    C = 채워진배열_생성(L, '-')
    originalC_S_indices = 문자위치들_가져오기(s, 'c', 'S')
    
    # C: L2까지 c로 바꿈
    if L2 != -1:
        범위를_문자로설정(C, 0, L2, 'c')
    
    # C: 모든 Drop_위치를 제외한 입력 str의 각 c와 s의 위치를 C에서 그 위치들에서 c를 S로 바꿈
    특정위치들_문자교체(C, originalC_S_indices, Drop_위치, 'c', 'S')
    
    # C: 각 Drop_새위치를 S로 바꾸고, Drop_높이 만큼 그 왼쪽을 S로 바꿈
    높이패턴_적용(C, Drop_새위치, Drop_높이, 'S')
    
    # C: 첫 글자를 삭제함. 맨 뒤에 - 추가
    C = 배열_시프트(C, '-')
    
    # D: L길이의 c로 가득찬 리스트 생성
    D = 채워진배열_생성(L, 'c')
    
    # s의 맨 첫 문자가 'S'라면 추가 처리
    if s and s[0] == 'S':
        # A의 맨 아래 연속된 '-' 중에서 가장 위 '-'를 'S'로 바꿈
        for i in range(len(A)):
            if A[i] == '-':
                # 다음 문자가 '-'가 아닐 때까지 계속 진행
                if i + 1 >= len(A) or A[i + 1] != '-':
                    A[i] = 'S'
                    # C의 같은 위치가 'S'라면, 그 S를 맨 첫글자 c와 문자를 바꿈
                    if i < len(C) and C[i] == 'S':
                        C[i] = 'c'
                        C[0] = 'S'
                    break
            else:
                break
    
    return format_final_result(A, B, C, D)


def build_pinable_shape2(s):
    L = max(len(s), Shape.MAX_LAYERS)
    
    # 가장 오른쪽 c 클러스터의 가장 왼쪽 위치를 찾음
    L2 = 가장오른쪽_클러스터_위치찾기(s, 'c')
    
    
    pass

def build_quad_shape(s):
    """단순모서리용: 쿼드 셰잎 빌드"""
    A = list(s)
    return format_final_result(A, A, A, A)

def build_double_shape(s):
    """스택모서리용: 더블 셰잎 빌드"""
    A = list(s)
    max_length = len(s)
    B = ['S'] * max_length
    
    return format_final_result(A, B, B, A)

def format_final_result(A, B, C, D):
    """최종 결과를 포맷팅"""
    A_str = ''.join(A)
    B_str = ''.join(B)
    C_str = ''.join(C)
    D_str = ''.join(D)
    
    maxLength = max(len(A_str), len(B_str), len(C_str), len(D_str))
    results = []
    for i in range(maxLength):
        aChar = A_str[i] if len(A_str) > i else '-'
        bChar = B_str[i] if len(B_str) > i else '-'
        cChar = C_str[i] if len(C_str) > i else '-'
        dChar = D_str[i] if len(D_str) > i else '-'
        results.append(f"{aChar}{bChar}{dChar}{cChar}")
    return ':'.join(results)

def corner_process(shape: Shape, classification: str = None) -> tuple[str, str]:
    """단일 Shape 객체를 받아 Corner 처리를 수행하고 결과와 건물 작동 정보를 반환합니다."""
    if classification is None:
        classification, _ = shape.classifier()

    # 1사분면(q1) 기둥 추출
    q1_pillar = ""
    for layer in shape.layers:
        quad = layer.quadrants[0]  # TR 사분면
        if quad is None:
            q1_pillar += "-"
        elif quad.shape in ['C', 'S', 'R', 'W']:
            q1_pillar += "S"
        else:
            q1_pillar += quad.shape
    SIMPLE_CORNER = "analyzer.shape_types.simple_corner"
    STACK_CORNER = "analyzer.shape_types.stack_corner"
    SWAP_CORNER = "analyzer.shape_types.swap_corner"
    CLAW_CORNER = "analyzer.shape_types.claw_corner"
    CLAW_HYBRID_CORNER = "analyzer.shape_types.claw_hybrid_corner"
    if classification == SIMPLE_CORNER:
        # 단순모서리: 빌드 쿼드 셰잎, "스왑"
        result = build_quad_shape(q1_pillar)
        return result, "스왑"
    elif classification == STACK_CORNER:
        # 스택모서리: 빌드 더블 셰잎, "스왑"
        result = build_double_shape(q1_pillar)
        return result, "스왑"
    elif classification == SWAP_CORNER:
        # 스왑모서리: 빌드 컷에이블 셰잎, "스왑"
        result = build_cutable_shape(q1_pillar)
        return result, "스왑"
    elif classification == CLAW_CORNER:
        # 클로모서리: 빌드 핀에이블 셰잎, "핀푸시"
        result = build_pinable_shape(q1_pillar)
        return result, "핀푸시"
    elif classification == CLAW_HYBRID_CORNER:
        # 클로모서리: 빌드 핀에이블 셰잎, "핀푸시"
        result = build_pinable_shape2(q1_pillar)
        return result, "핀푸시"
    else:
        # 모서리가 아닌 경우 기본 처리 (또는 오류 처리)
        # 이 경우는 모서리 도형만 들어온다고 가정하므로, 기본값을 정하거나 예외 발생
        result = build_pinable_shape(q1_pillar) # 기본값으로 cutable 처리
        return result, "핀푸시"

def process_all_shapes_from_file(input_filepath: str, output_filepath: str):
    """입력 파일에서 도형 코드를 읽어 Corner 처리를 수행하고 결과 파일을 생성합니다."""
    # example.txt에서 줄 읽기
    with open(input_filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"읽어온 줄 수: {len(lines)}")

    # 각 줄에 대해 build_shape 실행 및 결과 저장
    output_lines = []
    for i, line in enumerate(lines):
        shape_obj = Shape.from_string(line)
        result, _ = corner_process(shape_obj) # Shape 객체로 처리
        output_lines.append(result)
        print(f"처리 중 ({i+1}/{len(lines)}): {line} -> {result}")

    print(f"생성된 결과 수: {len(output_lines)}")

    # 결과를 텍스트 파일로 저장
    with open(output_filepath, "w", encoding="utf-8") as f:
        for out in output_lines:
            f.write(out + "\n")

    print(f"파일에 저장된 결과 수: {len(output_lines)}")

if __name__ == "__main__":
    # 기본 파일 경로
    input_file = "data/example.txt"
    output_file = "data/derived_combinations_len6.txt"
    process_all_shapes_from_file(input_file, output_file)
