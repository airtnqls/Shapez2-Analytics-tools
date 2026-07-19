# Main4 PP Proof Synthesis

## 양성 witness

Main4 PP 엔진은 다음 정보를 반환한다.

- `predecessor`: Rank0 Pin Push 직전 도형
- `predecessorStack`: predecessor가 Stack으로 제작될 때의 bottom/top 조각
- `receiptTargets`: 제작 순서대로 나열한 Pin Push 출력
- `kind`: `primitive-rank0` 또는 `receipt-chain`

Proof builder는 predecessor를 먼저 materialize한 뒤 `receiptTargets`마다 독립 `PIN_PUSH` operation node를 만든다. 각 출력은 `pushPin(previous, cap)`과 정확히 일치해야 한다.

## 음성 certificate

음성 결과에는 안정성, Corner/Half/Swap, Stack closure, PP 정규형 closure 항목이 포함된다. PP 항목은 Rank0 frontier와 모든 유일 receipt predecessor 후보가 소진됐음을 기록한다.

## Focused UI와의 결합

- 빠른 판정: Proof graph 없이 verdict만 반환
- 분석: witness와 분류 근거까지 반환
- 제작 과정: Half proof forest와 PP receipt edge를 DAG로 materialize
- Tree 보기: DAG의 공유 하위 공정을 사용 위치별로 복제
