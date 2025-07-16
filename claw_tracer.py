def build_cutable_shape(s):
    L = len(s)
    L2 = -1
    # 가장 오른쪽 c 클러스터의 가장 왼쪽 위치를 찾음
    for i in range(L-1, -1, -1):
        if s[i] == 'c':
            # 연속된 c의 시작점을 찾음
            cluster_start = i
            while cluster_start > 0 and s[cluster_start-1] == 'c':
                cluster_start -= 1
            # 클러스터의 가장 왼쪽보다 한 칸 왼쪽 위치
            L2 = cluster_start - 1 if cluster_start > 0 else 0
            break
    Drop_위치 = []
    Drop_높이 = []
    Drop_새위치 = []

    # A: 리스트로 변환하여 효율적 조작
    A = list(s)

    # 모든 c에 대해 반복:
    cIndices = [i for i, ch in enumerate(A) if ch == 'c']

    i = 0
    while i < len(cIndices):
        cIdx = cIndices[i]
        # c 왼쪽이 - 라면
        if cIdx > 0 and A[cIdx - 1] == '-':
            # 가장 가까운 왼쪽 S를 찾음.
            sIdx = -1
            for j in range(cIdx - 1, -1, -1):
                if A[j] == 'S':
                    sIdx = j
                    break
            if sIdx != -1:
                Drop_위치.append(sIdx)
                # sIdx 왼쪽의 - 개수 세기
                spaceCount = 0
                for k in range(sIdx - 1, -1, -1):
                    if A[k] == '-':
                        spaceCount += 1
                    else:
                        break
                Drop_높이.append(spaceCount)
                # 새 위치 기록 (c 왼쪽)
                newSIdx = cIdx - 1
                Drop_새위치.append(newSIdx)
                # S를 -로 제거만 함 (리스트에서 직접 수정)
                A[sIdx] = '-'
        i += 1

    # AA: S가 제거된 상태를 저장 (깊은 복사)
    AA = A.copy()
    
    # A: 빈 공간을 c로 채움.
    for i in range(len(A)):
        if A[i] == '-':
            A[i] = 'c'

    # A: 반복문 완료 후 각 Drop_새위치에 S 추가
    for newPos in Drop_새위치:
        if newPos < len(A):
            A[newPos] = 'S'
            
    # B: s를 복사하여 처리
    B = list(AA)

    # B: L2까지의 빈 공간을 P로 채움. (L2 있다고 가정)
    for i in range(min(L2 + 1, len(B))):
        if B[i] == '-':
            B[i] = 'P'
            
    # B: c를 S로 바꿈.
    for i in range(len(B)):
        if B[i] == 'c':
            B[i] = 'S'
    
    # C: L 길이의 -로 가득찬 리스트 생성.
    C = ['-'] * L
    originalC_S_indices = [i for i, ch in enumerate(s) if ch == 'c' or ch == 'S']

    # C: 0부터 Drop_새위치[-1]까지 전부 c로 바꿈. Drop_새위치가 없으면 L2까지 c로 바꿈.
    if len(Drop_새위치) > 0:
        lastDropPos = Drop_새위치[-1]
        for i in range(lastDropPos + 1):
            C[i] = 'c'
    else:
        # C를 0부터 L2위치까지 c로 변경
        if L2 != -1:
            for i in range(L2 + 1):
                C[i] = 'c'

    # C: 모든 Drop_위치를 제외한 입력 str의 각 c와 s의 위치를 C에서 그 위치들에서 c를 S로 바꿈.
    for originalIdx in originalC_S_indices:
        if originalIdx not in Drop_위치:
            if originalIdx < len(C) and C[originalIdx] == 'c':
                C[originalIdx] = 'S'
    
    # D: L길이의 c로 가득찬 리스트 생성
    D = ['-'] * L

    # 최종 결과 생성 (리스트를 문자열로 변환)
    A_str = ''.join(A)
    B_str = ''.join(B)
    C_str = ''.join(C)
    D_str = ''.join(D)
    
    maxLength = max(len(A_str), len(B_str), len(C_str), len(D_str))
    results = []
    for i in range(maxLength):
        dChar = D_str[i] if len(D_str) > i else ' '
        cChar = C_str[i] if len(C_str) > i else ' '
        aChar = A_str[i] if len(A_str) > i else ' '
        bChar = B_str[i] if len(B_str) > i else ' '
        results.append(f"{dChar}{cChar}{aChar}{bChar}")
    return ':'.join(results)



def build_pinable_shape(s):
    L = len(s)
    L2 = -1
    # 가장 오른쪽 c 클러스터의 가장 왼쪽 위치를 찾음
    for i in range(L-1, -1, -1):
        if s[i] == 'c':
            # 연속된 c의 시작점을 찾음
            cluster_start = i
            while cluster_start > 0 and s[cluster_start-1] == 'c':
                cluster_start -= 1
            # 클러스터의 가장 왼쪽보다 한 칸 왼쪽 위치
            L2 = cluster_start - 1 if cluster_start > 0 else 0
            break
    Drop_위치 = []
    Drop_높이 = []
    Drop_새위치 = []

    # A: 리스트로 변환하여 효율적 조작
    A = list(s)

    # 모든 c에 대해 반복:
    cIndices = [i for i, ch in enumerate(A) if ch == 'c']

    i = 0
    while i < len(cIndices):
        cIdx = cIndices[i]
        # c 왼쪽이 - 라면
        if cIdx > 0 and A[cIdx - 1] == '-':
            # 가장 가까운 왼쪽 S를 찾음.
            sIdx = -1
            for j in range(cIdx - 1, -1, -1):
                if A[j] == 'S':
                    sIdx = j
                    break
            if sIdx != -1:
                Drop_위치.append(sIdx)
                # sIdx 왼쪽의 - 개수 세기
                spaceCount = 0
                for k in range(sIdx - 1, -1, -1):
                    if A[k] == '-':
                        spaceCount += 1
                    else:
                        break
                Drop_높이.append(spaceCount)
                # 새 위치 기록 (c 왼쪽)
                newSIdx = cIdx - 1
                Drop_새위치.append(newSIdx)
                # S를 -로 제거만 함 (리스트에서 직접 수정)
                A[sIdx] = '-'
        i += 1

    # AA: S가 제거된 상태를 저장 (깊은 복사)
    AA = A.copy()
    
    # A: 빈 공간을 c로 채움.
    for i in range(len(A)):
        if A[i] == '-':
            A[i] = 'c'

    # A: 반복문 완료 후 각 Drop_새위치에 S 추가
    for newPos in Drop_새위치:
        if newPos < len(A):
            A[newPos] = 'S'
            
    # A: 첫 글자를 삭제함. 맨 뒤에 - 추가.
    A = A[1:] + ['-']

    # B: s를 복사하여 처리
    B = list(s)
    
    # B: L2까지의 빈 공간을 P로 채움. (L2 있다고 가정)
    for i in range(min(L2 + 1, len(B))):
        if B[i] == '-':
            B[i] = 'P'
    
    # B: c를 S로 바꿈.
    for i in range(len(B)):
        if B[i] == 'c':
            B[i] = 'S'
    
    # B: 첫 글자를 삭제함. 맨 뒤에 - 추가.
    B = B[1:] + ['-']

    # C: L 길이의 -로 가득찬 리스트 생성.
    C = ['-'] * L
    originalC_S_indices = [i for i, ch in enumerate(s) if ch == 'c' or ch == 'S']

    # C: 0부터 Drop_새위치[-1]까지 전부 c로 바꿈. Drop_새위치가 없으면 L2까지 c로 바꿈.
    if len(Drop_새위치) > 0:
        lastDropPos = Drop_새위치[-1]
        for i in range(lastDropPos + 1):
            C[i] = 'c'
    else:
        # C를 0부터 L2위치까지 c로 변경
        if L2 != -1:
            for i in range(L2 + 1):
                C[i] = 'c'

    # C: 모든 Drop_위치를 제외한 입력 str의 각 c와 s의 위치를 C에서 그 위치들에서 c를 S로 바꿈.
    for originalIdx in originalC_S_indices:
        if originalIdx not in Drop_위치:
            if originalIdx < len(C) and C[originalIdx] == 'c':
                C[originalIdx] = 'S'

    # C: 각 Drop_새위치를 S로 바꾸고, Drop_높이 만큼 그 왼쪽을 S로 바꿈.
    for idx, newPos in enumerate(Drop_새위치):
        if newPos < len(C):
            C[newPos] = 'S'
        height = Drop_높이[idx]
        for j in range(1, height + 1):
            if newPos - j >= 0:
                C[newPos - j] = 'S'

    # C: 첫 글자를 삭제함. 맨 뒤에 - 추가.
    C = C[1:] + ['-']

    # D: L길이의 c로 가득찬 리스트 생성
    D = ['c'] * L

    # 최종 결과 생성 (리스트를 문자열로 변환)
    A_str = ''.join(A)
    B_str = ''.join(B)
    C_str = ''.join(C)
    D_str = ''.join(D)
    
    maxLength = max(len(A_str), len(B_str), len(C_str), len(D_str))
    results = []
    for i in range(maxLength):
        dChar = D_str[i] if len(D_str) > i else ' '
        cChar = C_str[i] if len(C_str) > i else ' '
        aChar = A_str[i] if len(A_str) > i else ' '
        bChar = B_str[i] if len(B_str) > i else ' '
        results.append(f"{dChar}{cChar}{aChar}{bChar}")
    return ':'.join(results)

# example.txt에서 줄 읽기
with open("data/example.txt", "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

print(f"읽어온 줄 수: {len(lines)}")

# 각 줄에 대해 build_shape 실행 및 결과 저장
output_lines = []
for i, line in enumerate(lines):
    if line[0] == 'P':
        result = build_pinable_shape(line)
    elif line[0] == 'c':
        result = build_cutable_shape(line)
    else:
        result = build_cutable_shape(line)
    output_lines.append(result)
    print(f"처리 중 ({i+1}/{len(lines)}): {line} -> {result}")

print(f"생성된 결과 수: {len(output_lines)}")

# 결과를 텍스트 파일로 저장
with open("data/derived_combinations_len6.txt", "w", encoding="utf-8") as f:
    for out in output_lines:
        f.write(out + "\n")

print(f"파일에 저장된 결과 수: {len(output_lines)}")