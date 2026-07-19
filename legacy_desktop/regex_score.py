import re

# 사용자가 제공한 39가지 유형의 정규식 패턴
REGEX_PATTERNS = '''
P-PP:PSS[^c]:P-[^c][^c]:SS[^c][^c]:c[^c][^c][^c]
-PPP:SP[^c]S:-P[^c][^c]:cS[^c][^c]:[^c][^c][^c][^c]
--PP:--[PS]c:SS[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]
[P-]-[P-]P:.-.[PS]:SSS[^c]:S[^c][^c][^c]:c[^c][^c][^c]
-PPP:SP[^c]S:-P[^c][^c]:[Sc]S[^c][^c]:c[^c][^c][^c]
--PP:PP[PS]c:SS[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]
-PPP:SP[^c]S:[S-][PS][^c][^c]:[c-]P[^c][^c]:cS[^c][^c]
P-PP:PSS[^c]:P.[^c][^c]:[PS]-[^c][^c]:cS[^c][^c]
P[P-]P[P-]:[^-]-[^c]-:cS[^c]S:[^c][^c][^c][^c]:[^c][^c][^c][^c]
.-PP:.-c[SP]:-SS[^c]:SS[^c][^c]:c[^c][^c][^c]
P-PP:P-[^-][Sc]:PSc[^c]:[^-]-S[^c]:cS[^c][^c]
P-P[^c]:P-[^-][^c]:PSc[^c]:[^-]-S[^c]:cS[^c][^c]
..P.:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]
..P.:..[PS].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]
...P:...[^c]:S[Sc]S[^c]:S[^c][^c][^c]:c[^c][^c][^c]
P.P.:..[^c].:[Sc]S[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]
...P:...[^c]:-[Sc]S[^c]:SS[^c][^c]:c[^c][^c][^c]
..P.:..[^c].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]
..P.:..[PS].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]
-.PP:-.[^-][^-]:[Sc]-[PS][^-]:cS[^c][^c]:[^c][^c][^c][^c]
..P.:..[^c].:..[^c].:cS[^c]S:[^c][^c][^c][^c]
P..[^c]:[^-]..[^c]:[^-][Sc]S[^c]:[^-]-[^c][^c]:cS[^c][^c]
..P.:..[^c].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]
[PS].P.:..[PS].:..[^c].:cS[^c]S:[^c][^c][^c][^c]
[P-][P-]PP:..[^-][^-]:[S-][S-][PS][Sc]:[Sc]S[^c][^c]:c[^c][^c][^c]
.[P-][P-]P:...[^-]:.SS[^c]:.[P-][^c][^c]:cS[^c][^c]
P.P.:[^-].[^-].:..[^-].:cS[^c]S:[^c][^c][^c][^c]
..P.:..[PS].:..[^c][Sc]:..[^c][^c]:cS[^c][^c]
...P:...[^c]:.[Sc]S[^c]:..[^c][^c]:cS[^c][^c]
..P.:..[^c].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]
..P.:..[PS].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]
[P-][P-]PP:[P-].[^-][^-]:[PS].c[Sc]:[^-]-S[^c]:cS[^c][^c]
..P.:..[^c].:[Sc].[^c]S:..[^c][^c]:cS[^c][^c]
..P.:..[^-].:..[PS].:[Sc]S[^c]S:c[^c][^c][^c]
....:....:..[PS][Sc]:.[P-][^c][^c]:cS[^c][^c]
..[PS].:..[^c].:..[^c].:[Sc][P-][^c]S:cS[^c][^c]
..P.:..[PS].:..[^c].:[Sc].[^c]S:cS[^c][^c]
..[PS].:..[^c].:..[^c].:..[^c].:cS[^c]S
..P.:..[PS].:..[^c].:..[^c].:cS[^c]S
....:....:..[PS].:[Sc][P-][^c]S:cS[^c][^c]
....:....:..[^-].:[^-]-[PS][^-]:cS[^c][^c]
....:....:..[PS].:..[^c].:cS[^c]S
....:....:....:..[PS].:cS[^c]S
'''

def calculate_specificity_score(pattern_string: str) -> int:
    """
    정규식 패턴의 구체성 점수를 계산합니다.
    - 리터럴: 4점
    - 긍정 클래스 [..]: 3점
    - 부정 클래스 [^..]: 2점
    - 와일드카드 .: 1점
    """
    score = 0
    i = 0
    while i < len(pattern_string):
        char = pattern_string[i]

        if char == '[':
            # 문자 클래스 ([...]) 처리
            end_bracket_index = pattern_string.find(']', i)
            if end_bracket_index != -1:
                # 클래스 내부의 첫 문자가 '^'이면 부정 클래스
                if pattern_string[i+1] == '^':
                    score += 2  # 부정 클래스 점수
                else:
                    score += 3  # 긍정 클래스 점수
                i = end_bracket_index + 1
                continue
        elif char == '.':
            score += 1  # 와일드카드 점수
        elif char == ':':
            pass  # 구분자는 점수 없음
        else:
            # 그 외 문자는 모두 리터럴로 간주
            score += 4  # 리터럴 점수
        
        i += 1
        
    return score

def analyze_and_sort_patterns(raw_patterns: str):
    """
    주어진 패턴들을 분석하고 구체성 순서로 정렬합니다.
    정렬 기준:
    1. 패턴의 개수 (많을수록 우선)
    2. 구체성 점수 (높을수록 우선)
    """
    lines = raw_patterns.strip().split('\n')
    
    analyzed_list = []
    for line in lines:
        if not line:
            continue
        
        # 1. 패턴 개수 계산 (콜론 개수 + 1)
        num_patterns = line.count(':') + 1
        
        # 2. 구체성 점수 계산
        score = calculate_specificity_score(line)
        
        analyzed_list.append({
            'original': line,
            'num_patterns': num_patterns,
            'score': score
        })
        
    # 정렬: 패턴 개수와 점수 모두 내림차순 (높은 것이 위로)
    sorted_list = sorted(
        analyzed_list,
        key=lambda x: (x['num_patterns'], x['score']),
        reverse=True
    )
    
    return sorted_list

# 스크립트 실행
if __name__ == "__main__":
    sorted_patterns = analyze_and_sort_patterns(REGEX_PATTERNS)
    
    print("--- 정규식 패턴 구체성 순서 자동 정렬 결과 ---")
    print("정렬 기준: 1. 패턴 수(내림차순), 2. 구체성 점수(내림차순)\n")
    
    for i, item in enumerate(sorted_patterns, 1):
        print(f"{item['score']:3d}, {item['original']}")