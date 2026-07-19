# CPCP형 제작 레시피

## 문제

기존 ZIP 화면은 `ProofGraph.nodes` 배열 순서를 제작 순서처럼 사용했다. 배열 순서는
그래프 생성 구현의 세부사항일 뿐 부모 도형이 먼저 만들어진다는 보장이 없고, Cut/Swap의
선택되지 않은 출력과 공유되는 중간 도형도 재생기가 직접 추측해야 했다.

## 공용 계약

Worker는 proof 모드에서 `proof`와 함께 `processRecipe`를 반환한다.

- `operationNodeId`: 공정을 만든 연산 backpointer
- `dependencyStepIds`: 먼저 완료되어야 하는 부모 공정
- `inputs`: 입력 도형과 역할(바닥, 상단, 입력 A/B 등)
- `outputs`: 실제 출력과 ghost/미사용 출력
- `selectedOutputNodeIds`: 목표 제작 경로에서 선택된 출력
- `sharedShapeNodeIds`: 둘 이상의 후속 공정이 재사용하는 도형

이는 CPCP 검색이 새 도형을 처음 발견할 때 생성 연산과 부모를 저장하는 방식과 같은
책임 경계를 갖는다. 현재 엔진이 제공하는 witness/forest를 backpointer DAG로 만든 다음,
Kahn 위상 정렬로 안정적인 단계 순서를 계산한다.

## GUI 사용

- Next.js 제작 과정 재생기는 `processRecipe`와 같은 위상 순서를 사용한다.
- PyQt는 동일 Worker 결과를 JSON-lines로 받고 DAG와 상세 JSON을 표시한다.
- 큰 DAG는 목표 출력 근처에서 열리고, 전체 그래프는 `화면 맞춤`으로 확인한다.
- primitive까지 전개할 수 없는 인증 macro는 숨기지 않고 warning으로 남긴다.
