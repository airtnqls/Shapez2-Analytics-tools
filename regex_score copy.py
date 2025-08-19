import functools
import re

HYBRID_PATTERNS = {
    "P-PP:P-[PS]S:PSc[^c]:[^-]-S[^c]:cS[^c][^c]": "0000:0000:0001:0001:0011",
    "P-P[^c]:P-[^-][^c]:PSc[^c]:[^-]-S[^c]:cS[^c][^c]": "0001:0001:0001:0001:0011",
    "--PP:PP[PS]c:SS[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]": "0000:0000:0010:0111:0111",
    "P-PP:PSS[^c]:P-[^c][^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0001:0011:0011:0111",
    "--PP:--[PS]c:SS[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]": "0000:0000:0010:0111:1111",
    "[P-]-PP:[P-]-[^-][^-]:[PS][S-]c[Sc]:[^-]-S[^c]:cS[^c][^c]": "0000:0000:0000:0001:0011",
    ".-PP:.-c[SP]:-SS[^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0000:0001:0011:0111",
    "[P-]-[P-]P:[c-]-[c-][PS]:SSS[^c]:S[^c][^c][^c]:c[^c][^c][^c]": "0000:0000:0001:0111:0111",
    "P[P-]P[P-]:[^-]-[^c]-:cS[^c]S:[^c][^c][^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:1111:1111", # Symmetry
    "[P-][P-]PP:[P-].[^-][^-]:[S-][S-][PS][Sc]:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0000:0000:0011:0111",
    ".[-]PP:[P-]-[^-][^-]:.SS[^c]:.[P-][^c][^c]:cS[^c][^c]": "0000:0000:0001:0011:0011",
    "-.PP:-.[^-][^-]:[Sc]-[PS][^-]:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0000:0000:0011:1111",
    "..P.:..[PS].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0000:0010:0011:1111",
    "...P:...[^c]:-[Sc]S[^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0001:0001:0011:0111",
    "P..[^c]:[^-]..[^c]:[^-][Sc]S[^c]:[^-]-[^c][^c]:cS[^c][^c]": "0001:0001:0001:0011:0011",
    "..P.:..[PS].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0000:0010:0011:0111",
    "P.P.:..[^c].:[Sc]S[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]": "0000:0010:0010:0111:0111", # Symmetry
    "..P.:..[^c].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0010:0010:0011:0111",
    "..P.:..[^c].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:0011:1111",
    "...P:...[^c]:S[Sc]S[^c]:S[^c][^c][^c]:c[^c][^c][^c]": "0000:0001:0001:0111:0111",
    "..P.:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:0111:1111", # Symmetry
    "P.P.:..[PS].:..[^c].:cS[^c]S:[^c][^c][^c][^c]": "0000:0000:0010:0010:1111", # Symmetry
    "P.P.:[^-].[^-].:..[^-].:cS[^c]S:[^c][^c][^c][^c]": "0000:0000:0000:0010:1111", # Symmetry
    "..P.:..[PS].:..[^c].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0000:0010:0010:0011",
    "..P.:..[^c].:..[^c].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0010:0010:0010:0011",
    "..P.:..[^-].:..[PS].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0000:0000:0010:0111", # Symmetry
    "..P.:..[PS].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0000:0010:0010:0111", # Symmetry
    "..P.:..[^c].:[Sc].[^c]S:..[^c][^c]:cS[^c][^c]": "0000:0010:0010:0011:0011",
    "..P.:..[^c].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0010:0010:0010:0111", # Symmetry
    "...P:...[^c]:.[Sc]S[^c]:..[^c][^c]:cS[^c][^c]": "0000:0001:0001:0011:0011",
    "..P.:..[^c].:..[^c].:cS[^c]S:[^c][^c][^c][^c]": "0000:0010:0010:0010:1111", # Symmetry
    "..P.:..[PS].:..[^c]S:..[^c][^c]:cS[^c][^c]": "0000:0000:0010:0011:0011",
    "....:....:..[PS].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0000:0000:0010:0011",
    "....:....:..[PS][Sc]:[^P][P-][^c][^c]:cS[^c][^c]": "0000:0000:0000:0011:0011",
    "....:....:..[^-].:[Sc]-[PS][^-]:cS[^c][^c]": "0000:0000:0000:0000:0011",
    "..P.:..[PS].:..[^c].:..[^c].:cS[^c]S": "0000:0000:0010:0010:0010", # Symmetry
    "..P.:..[^c].:..[^c].:..[^c].:cS[^c]S": "0000:0010:0010:0010:0010", # Symmetry
    "....:....:..[PS].:..[^c].:cS[^c]S": "0000:0000:0000:0010:0010", # Symmetry
    "....:....:....:..[PS].:cS[^c]S": "0000:0000:0000:0000:0010" # Symmetry
}
def calculate_specificity_score(pattern_string: str) -> int:
    """정규식 패턴의 구조적 구체성 점수를 계산합니다."""
    # (이전과 동일한 함수)
    score = 0
    i = 0
    while i < len(pattern_string):
        char = pattern_string[i]
        if char == '[':
            end_bracket_index = pattern_string.find(']', i)
            if end_bracket_index != -1:
                score += (2 if pattern_string[i+1] == '^' else 3)
                i = end_bracket_index
        elif char == '.': score += 1
        elif char != ':': score += 4
        i += 1
    return score

# 분석을 위해 각 항목을 객체로 변환
patterns_data = []
for regex, mask_str in HYBRID_PATTERNS.items():
    clean_mask_str = mask_str.replace(':', '')
    patterns_data.append({
        'regex': regex,
        'mask_str': mask_str,
        'mask_int': int(clean_mask_str, 2), # 비교를 위해 정수로 변환
        'ones_count': clean_mask_str.count('1'),
        'score': calculate_specificity_score(regex)
    })

def compare_patterns(item1, item2):
    """
    두 패턴의 우선순위를 비교하는 함수.
    -1: item1이 우선, 1: item2가 우선, 0: 동일
    """
    m1 = item1['mask_int']
    m2 = item2['mask_int']

    # 최우선 규칙: 부분집합 관계 확인
    is_1_subset_of_2 = (m1 & m2) == m1
    is_2_subset_of_1 = (m1 & m2) == m2

    if m1 != m2:
        if is_1_subset_of_2: return -1 # item1이 item2의 부분집합이면 item1이 우선
        if is_2_subset_of_1: return 1  # item2가 item1의 부분집합이면 item2가 우선

    # 2차 규칙: 부분집합 관계가 아닐 경우, '1'의 개수로 비교
    if item1['ones_count'] != item2['ones_count']:
        return item1['ones_count'] - item2['ones_count'] # 1의 개수가 적은 쪽이 우선

    # 3차 규칙: '1'의 개수도 같을 경우, 정규식 점수로 비교
    if item1['score'] != item2['score']:
        return item2['score'] - item1['score'] # 점수가 높은 쪽(내림차순)이 우선

    # 모든 조건이 같으면 순서 유지
    return 0

# functools.cmp_to_key를 사용하여 사용자 정의 비교 함수로 정렬
sorted_patterns = sorted(patterns_data, key=functools.cmp_to_key(compare_patterns))


# --- 결과 출력 ---
print("--- '부분집합 관계' 최우선 정렬 결과 ---")
print("정렬 기준: 1. 부분집합 관계, 2. '1'의 개수(오름차순), 3. Regex 점수(내림차순)\n")
print(f"{'Rank':<5} {'1s':<4} {'Score':<6} {'Mask':<32} {'Regex Pattern'}")
print("-" * 100)
for i, item in enumerate(sorted_patterns, 1):
    print(f"{i:<5} {item['ones_count']:<4} {item['score']:<6} {item['mask_str']:<32} {item['regex']}")