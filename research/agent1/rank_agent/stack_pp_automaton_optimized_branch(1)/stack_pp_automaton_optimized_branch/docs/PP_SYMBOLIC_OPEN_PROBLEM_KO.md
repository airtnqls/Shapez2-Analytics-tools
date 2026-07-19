# 일반 PP-essential rank: 완료 부분과 열린 부분

## 완료된 부분

`PPRankEngine`은 정확한 domain callback이 주어졌을 때 cpcp식 batch 의미를
그대로 수행한다.

```text
batch 0 : 증명된 rank-0/base seed의 Stack closure를 Pin Push
batch n : 직전 batch의 retained PP seed의 Stack closure를 Pin Push
```

각 결과에서:

- empty 결과 제외
- Swappable 제외
- lower-rank known base에서 Stackable한 결과 제외
- 같은 batch에서는 엄격히 작은 visible-material progress의 base만 허용
- complete transitive Stack witness로 redundant 결과 cleanup
- 최소 `(batch, predecessor, seed)` parent 보존
- 후기 rank 때문에 redundant가 된 옛 PP는 parent chain용 retained

을 구현한다.

## 정확한 종료 척도

한 PP parent edge는 discovery rank를 엄격히 낮춘다.
같은 batch cleanup의 Stack witness는 visible non-crystal 수를 엄격히
낮춘다. 따라서 certificate dependency는 다음 사전식 순서에서 비순환이다.

```text
(discovery rank, visible non-crystal count, canonical order)
```

## 아직 열린 전층 문제

현재 engine은 `PPRankDomain`이 제공하는 seed/Stack closure/PinPush image를
순회한다. 작은 고정 cap의 concrete oracle에는 완전하지만, 임의 층수의
모든 PP family를 작은 symbolic object로 제공하는 일은 별도 문제다.

특히 필요한 정리는 다음이다.

1. `PinPush(StackClosure(F))`의 exact symbolic 표현
2. Swappable/Stackable 차집합의 exact 표현
3. same-batch essential basis의 symbolic 계산
4. rank를 반복할 때 state growth가 통제되거나 반복 정규형에 들어간다는 증명
5. 불가능 target에서 무한 rank 탐색을 멈추게 하는 fixed-point/negative certificate

`max_batches=N`은 실험 예산일 뿐 fixed-point 증명이 아니다. 구현도
`fixed_point_proved=False`로 이를 노출한다.

## 다음 branch와의 결합점

- `core-kernel`: exact CompactShape Pin Push와 row/materializer
- `corner-half`: finite Half/Swappable family automaton
- `tmam-integration`: retained PP certificate를 ProofNode로 변환
- `family-minimization`: StackClosureAutomaton과 향후 PP family의 residual 최소화
