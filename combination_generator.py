import re
from typing import List


def check_single_string_patterns(string: str) -> bool:
    """단일 문자열에 대한 불가능한 패턴들을 검사"""
    patterns = [
        r'^P*-+c',      # 2-1: 시작이 P*, 그 다음 -+, 그 다음 c
        r'[^P]P.*c',    # 2-2: P가 아닌 문자 다음에 P, 그 다음 임의 문자들, 그 다음 c
        r'c-.*c',       # 2-3: c 다음에 -, 그 다음 임의 문자들, 그 다음 c
        r'c.-+c',       # 2-4: c 다음에 임의 문자 1개, 그 다음 -+, 그 다음 c
        r'-P'           # 추가: -P 패턴도 불가능
    ]
    
    for pattern in patterns:
        if re.search(pattern, string):
            return True
    return False


def generate_valid_combinations(max_length: int = 10) -> List[List[str]]:
    """
    -, S, c, P로 구성된 모든 조합을 길이별로 생성하되,
    불가능한 패턴은 제외하고 유효한 조합만 반환
    
    Args:
        max_length: 최대 길이 (기본값: 10)
    
    Returns:
        List[List[str]]: 각 길이별 유효한 조합들의 리스트
    """
    characters = ['-', 'S', 'c', 'P']
    results = []
    
    # 1글자부터 시작
    current_valid = []
    for char in characters:
        if not check_single_string_patterns(char):
            current_valid.append(char)
    
    results.append(current_valid.copy())
    print(f"길이 1: {len(current_valid)}개의 유효한 조합")
    
    # 2글자부터 max_length까지
    for length in range(2, max_length + 1):
        next_valid = []
        
        # 이전 길이의 유효한 조합들에 각 문자를 추가
        for base_string in current_valid:
            for char in characters:
                new_string = base_string + char
                if not check_single_string_patterns(new_string):
                    next_valid.append(new_string)
        
        results.append(next_valid.copy())
        print(f"길이 {length}: {len(next_valid)}개의 유효한 조합")
        
        # 다음 반복을 위해 현재 유효한 조합 업데이트
        current_valid = next_valid
        
        # 더 이상 유효한 조합이 없으면 중단
        if not current_valid:
            print(f"길이 {length}에서 더 이상 유효한 조합이 없습니다.")
            break
    
    return results


def save_combinations_to_file(combinations: List[List[str]], filename: str = "valid_combinations.txt"):
    """유효한 조합들을 파일에 저장 (순수 데이터만)"""
    with open(filename, 'w', encoding='utf-8') as f:
        for combo_list in combinations:
            for combo in combo_list:
                f.write(f"{combo}\n")
    
    print(f"결과가 {filename}에 저장되었습니다.")


def print_combination_summary(combinations: List[List[str]]):
    """조합 결과 요약 출력"""
    total_count = 0
    print("\n=== 조합 생성 결과 요약 ===")
    for length, combo_list in enumerate(combinations, 1):
        count = len(combo_list)
        total_count += count
        print(f"길이 {length}: {count}개")
        
        # 처음 몇 개 예시 출력
        if count > 0:
            examples = combo_list[:5]
            print(f"  예시: {', '.join(examples)}")
            if count > 5:
                print(f"  ... 외 {count - 5}개")
        print()
    
    print(f"총 {total_count}개의 유효한 조합이 생성되었습니다.")


def test_patterns():
    """패턴 검사 테스트"""
    test_cases = [
        ("P", False),    # 유효
        ("PP", False),   # 유효
        ("P-c", True),   # 불가능: P*-+c
        ("PP-c", True),  # 불가능: P*-+c
        ("SP", True),    # 유효
        ("-P", True),    # 불가능: -P 패턴
        ("c-c", True),   # 불가능: c-.*c
        ("cSc", True),   # 유효
        ("S", False),    # 유효
        ("c", False),    # 유효
        ("-", False),    # 유효
    ]
    
    print("=== 패턴 검사 테스트 ===")
    for test_string, expected in test_cases:
        result = check_single_string_patterns(test_string)
        status = "통과" if result == expected else "실패"
        print(f"{test_string}: {result} (예상: {expected}) - {status}")


if __name__ == "__main__":
    # 패턴 검사 테스트
    test_patterns()
    
    print("\n" + "="*50)
    print("유효한 조합 생성을 시작합니다...")
    
    # 조합 생성
    LENGTH = 10
    combinations = generate_valid_combinations(LENGTH)
    
    # 결과 출력
    print_combination_summary(combinations)
    
    # 파일 저장
    save_combinations_to_file(combinations, f"data/all_corner_len{LENGTH}.txt")