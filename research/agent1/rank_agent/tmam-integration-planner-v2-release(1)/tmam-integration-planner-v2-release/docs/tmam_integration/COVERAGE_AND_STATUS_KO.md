# POSSIBLE / IMPOSSIBLE / UNKNOWN 및 coverage

## POSSIBLE

다음 조건을 모두 만족한 ProofNode가 하나 이상 존재한다.

1. 모든 child가 POSSIBLE proof를 가짐.
2. child progress가 parent보다 엄격히 작음.
3. candidate target이 canonical goal과 일치함.
4. 독립 `ForwardModel.replay()`가 target을 정확히 재생함.

partial provider가 있어도 위 witness가 존재하면 POSSIBLE 자체는 확정이다. 다만 최소 비용의 전역 최적성은 `optimal=False`일 수 있다.

## IMPOSSIBLE

다음 조건을 모두 만족할 때만 허용한다.

1. 필수 relation ID가 전부 등록됨.
2. 필수 operation에 provider가 존재함.
3. 관련 provider가 `Coverage.complete`임.
4. provider candidate iterator가 실제로 exhausted됨.
5. 모든 candidate가 적어도 하나의 완전한 IMPOSSIBLE child 때문에 실패함.
6. replay-valid proof가 없음.

admissible lower-bound pruning은 기존 best proof의 비용 최적성에는 사용할 수 있지만, **proof가 하나도 없는 상태의 IMPOSSIBLE 증명에는 사용할 수 없다.** 부재 증명은 complete+exhausted가 필요하다.

## UNKNOWN

다음 중 하나라도 해당한다.

- provider 미등록
- `Coverage.partial`
- timeout
- resource limit
- `NotImplementedError`
- provider candidate stream 중단
- child가 UNKNOWN
- forward replay model 미설정
- replay exception/mismatch로 provider 신뢰가 깨짐
- recursion-stack cycle

UNKNOWN은 불가능과 동일하지 않다.

## OperationEvidence

- proof 발견: `possible=True`. 존재 판정은 complete.
- proof 없음 + complete/exhausted: `possible=False`.
- proof 없음 + partial/missing/unknown child: `possible=None`.

strict Claw는 다음이 모두 확정됐을 때만 계산한다.

```text
Pin Push = True
Swap     = False
Stack    = False
```

하나라도 `None`이면 strict Claw도 UNKNOWN이다.
