# Provider acceptance tests

상위 브랜치는 병합 전에 `tmam.testkit.audit_relation`을 사용한다.

```python
report = audit_relation(
    provider,
    sample_goal,
    backend=compact_backend,
    forward=independent_forward_model,
)
assert report.valid, report.issues
```

검사 항목:

- candidate operation과 provider operation 일치
- candidate target과 goal 일치
- 모든 child progress 엄격 감소
- certificate forward replay가 target과 일치
- provider가 complete라고 선언한 범위 기록

추가로 각 provider branch가 자체적으로 제출해야 하는 자료:

1. 작은 층 전체 exact differential test
2. 7층 이상 adversarial/random test
3. soundness proof
4. completeness proof 또는 명시적 partial 범위
5. worst-case complexity
6. deterministic output hash
7. 최소 반례 저장 형식
