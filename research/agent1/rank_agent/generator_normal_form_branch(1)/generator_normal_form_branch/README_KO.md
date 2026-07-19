# Generator Normal Form 브랜치

Crystal Generator 전층 의미, 완전한 역관계, family-constrained product DP,
색상 provenance, witness certificate를 구현한 독립 브랜치 산출물이다.

## 실행

```bash
python tests/test_generator_normal_form.py
python tests/benchmark_generator.py
```

## 핵심 사용

```python
from tmam.relations.generator import (
    GeneratorConstraint,
    solve_with_family,
)

constraint = GeneratorConstraint.structural(target_rows)
witness = solve_with_family(constraint, lower_rank_family)
witness.certify()
```

전상을 리스트로 만든 뒤 각각 TMAM을 재귀 호출하지 않는다. 목표를 최대 81개/층의 행 제약으로
바꾸고 lower-rank family automaton과 즉시 product한다.

## 상태

- Generator 전방 의미: 완료
- 구조/색상 역관계 건전성·완전성: 완료
- 생산적 normal form 및 종료 척도: 완료
- deterministic family product solver: 완료
- 2층 전수 대조: 완료
- 현재 Shape.py 수정 패치: 포함
- 전체 buildable family: 다른 브랜치의 책임
