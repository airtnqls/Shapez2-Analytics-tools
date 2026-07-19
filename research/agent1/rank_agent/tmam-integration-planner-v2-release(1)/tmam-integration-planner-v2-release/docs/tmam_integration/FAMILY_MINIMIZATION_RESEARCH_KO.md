# Family closure / 최소화 연구 노트

## 제공 도구

- 완전 DFA 표현
- unreachable state 제거
- partition refinement 최소화
- union / intersection / difference product
- 두 automaton의 최단 구별 suffix 탐색
- rank별 family sequence와 stabilization 검사
- explicit abstract-state least fixed point audit

## 권장 실험 흐름

```text
small-L exact oracle
→ symbolic family 후보 생성
→ DFA 최소화
→ 다음 rank/family와 equivalence 비교
→ 구별 suffix를 반례로 저장
→ frontier 상태 의미를 보강
→ 귀납 증명
```

## 중요한 판정

rank n과 n+1 family DFA가 동치이면 closure가 고정됐다는 강한 증거다. 하지만 자동 학습 결과만으로 정리를 선언하면 안 된다. 각 state가 미래 연산에 대해 충분한 congruence임을 별도로 증명해야 한다.

## 상태 폭발 기록

각 rank마다 반드시 저장한다.

- 최소화 전/후 상태 수
- transition 수
- 이전 rank와의 shortest counterexample
- buildability false-positive/false-negative oracle 비교
- witness constructor 성공률

이 기록이 전체 TMAM의 전층 가능성을 판단하는 핵심 자료다.
