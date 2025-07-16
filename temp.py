def build_shape(s):
    L = len(s)
    Drop_위치 = []
    Drop_높이 = []
    Drop_새위치 = []

    # A: str를 깊은 복사해옴.
    A = s

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
                # 그 S를 c 왼쪽으로 옮김
                A = A[:sIdx] + A[sIdx+1:]
                A = A[:cIdx-1] + 'S' + A[cIdx-1:]
                newSIdx = cIdx - 1
                Drop_새위치.append(newSIdx)
                # cIndices 재계산
                cIndices = [j for j, ch in enumerate(A) if ch == 'c']
                # 옮겨진 S로 인해 현재 c의 위치가 한 칸 뒤로 밀렸으므로 i 조정
                if i < len(cIndices):
                    cIndices[i] = cIndices[i] + 1
            pass
        i += 1

    # A: 빈 공간을 c로 채움.
    A = A.replace('-', 'c')
    # A: 첫 글자를 삭제함. 맨 뒤에 - 추가.
    A = A[1:] + '-'

    # B: str를 깊은 복사해옴.
    B = s
    # B: 빈 공간을 P로 채움.
    B = B.replace('-', 'P')
    # B: c를 S로 바꿈.
    B = B.replace('c', 'S')
    # B: 맨 뒤에 - 추가.
    B = B + '-'
    # Drop_위치만큼 반복: Drop_위치[i]를 P로 바꿈.
    for idx in Drop_위치:
        B = B[:idx] + 'P' + B[idx+1:]
    # B: 첫 글자를 삭제함.
    B = B[1:]

    # C: L 길이의 -로 가득찬 문자열 생성.
    C = '-' * L
    originalC_S_indices = [i for i, ch in enumerate(s) if ch == 'c' or ch == 'S']

    # C: 0부터 Drop_위치[-1]까지 전부 c로 바꿈. Drop_위치가 없으면 연속된 c 범위까지 c로 바꿈.
    if len(Drop_위치) > 0:
        lastDropPos = Drop_위치[-1]
        C = 'c' * (lastDropPos + 1) + C[lastDropPos + 1:]
    else:
        # C를 전부 'c'로 채움
        C = 'c' * L

    # C: 모든 Drop_위치를 제외한 입력 str의 각 c와 s의 위치를 C에서 그 위치들에서 c를 S로 바꿈.
    for originalIdx in originalC_S_indices:
        if originalIdx not in Drop_위치:
            if C[originalIdx] == 'c':
                C = C[:originalIdx] + 'S' + C[originalIdx+1:]

    # C: 첫 글자를 삭제함. 맨 뒤에 - 추가.
    C = C[1:] + '-'

    # C: 각 Drop_새위치를 S로 바꾸고, Drop_높이 만큼 그 왼쪽을 S로 바꿈.
    for idx, newPos in enumerate(Drop_새위치):
        C = C[:newPos] + 'S' + C[newPos+1:]
        height = Drop_높이[idx] + 1
        for j in range(1, height + 1):
            if newPos - j >= 0:
                C = C[:newPos - j] + 'S' + C[newPos - j + 1:]

    # D: L길이의 c로 가득찬 문자열 생성
    D = 'c' * L

    # 최종 결과 생성
    maxLength = max(len(A), len(B), len(C), len(D))
    results = []
    for i in range(maxLength):
        dChar = D[i] if len(D) > i else ' '
        cChar = C[i] if len(C) > i else ' '
        aChar = A[i] if len(A) > i else ' '
        bChar = B[i] if len(B) > i else ' '
        results.append(f"{dChar}{cChar}{aChar}{bChar}")
    return ':'.join(results)

# example.txt에서 줄 읽기
with open("example.txt", "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

print(f"읽어온 줄 수: {len(lines)}")

# 각 줄에 대해 build_shape 실행 및 결과 저장
output_lines = []
for i, line in enumerate(lines):
    result = build_shape(line)
    output_lines.append(result)
    print(f"처리 중 ({i+1}/{len(lines)}): {line} -> {result}")

print(f"생성된 결과 수: {len(output_lines)}")

# 결과를 텍스트 파일로 저장
with open("derived_combinations_len6.txt", "w", encoding="utf-8") as f:
    for out in output_lines:
        f.write(out + "\n")

print(f"파일에 저장된 결과 수: {len(output_lines)}")