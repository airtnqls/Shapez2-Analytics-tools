# POSSIBLE / IMPOSSIBLE / UNKNOWN

```text
POSSIBLE:
독립 forward replay가 통과한 proof 존재

IMPOSSIBLE:
필요한 complete relation이 모두 exhaustive하게 실패

UNKNOWN:
provider coverage 불완전, timeout, resource limit, 미구현 relation,
unknown child, replay 불가, cycle
```

## IMPOSSIBLE 선언 조건

1. `PlannerConfig.required_relation_ids`가 전부 등록됨.
2. required operation에 provider가 존재함.
3. 모든 관련 provider가 `Coverage.complete`임.
4. candidate iterator가 끝까지 exhausted됨.
5. 모든 candidate가 완전한 IMPOSSIBLE child 때문에 실패함.
6. replay-valid proof가 없음.

하나라도 미충족이면 UNKNOWN이다.

## POSSIBLE과 최적성

partial provider가 있어도 valid proof 하나가 있으면 POSSIBLE이다. 다만 `solve_min_cost().optimal`은 False일 수 있다.

## strict Claw

```text
Pin Push = possible
Swap     = impossible
Stack    = impossible
```

세 operation decision이 모두 확정됐을 때만 strict Claw를 결정한다.
