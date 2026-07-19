# GPT 구현 지시문

아래 프롬프트를 새 작업 세션에 그대로 전달한다.

---

당신은 `Shapez2-TMAM-Web-Studio-2.1.0-Focused-UI-Main4-PP.zip`의 **전경로 성능 최적화 담당자**다.

## 목표

단순 비-Claw 도형을 generic 역탐색으로 풀지 말고, 구조를 한 번 스캔하여 `O(L)`에 판정과 제작 프로그램을 직접 합성하라. Claw/복잡 PP만 기존 인증 Claw/Hybrid 또는 Main4 PP 엔진으로 보낸다.

이 작업은 감이나 임의 정규식 추가가 아니다. 반드시 코드 수정, forward replay, differential test, DAG/메모리/호출 횟수 benchmark로 검증한다.

## 입력 자료

1. 기준 ZIP
   - `Shapez2-TMAM-Web-Studio-2.1.0-Focused-UI-Main4-PP.zip`
2. 최적화 설계
   - `docs/tmam_fastpath/01_IMPLEMENTATION_PLAN_KO.md`
3. 테스트 계약
   - `docs/tmam_fastpath/02_TEST_MATRIX_KO.md`
4. 독립 실험
   - `experiments/half_fastpath/half_linear_fastpath.py`
   - `experiments/half_fastpath/optimizer_suite.py`
   - `experiments/half_fastpath/test_half_linear_fastpath.py`
5. 첫 필수 target

```text
SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:
SuSu----:--Su----:SuSu----:--Su----:cwSu----
```

## 절대 조건

- Focused UI를 유지한다.
- fast verdict / analysis / construction 분리를 유지하고 더 엄격히 만든다.
- Main4 PP 판정 논리를 약화시키지 않는다.
- 기존 결정 verdict/ShapeType mismatch는 0이어야 한다.
- 모든 positive witness는 프로젝트의 실제 primitive physics로 forward replay한다.
- fast-path 실패는 generic fallback으로 내려가며 IMPOSSIBLE 근거가 아니다.
- 임의 timeout/예산 소진을 IMPOSSIBLE로 해석하지 않는다.
- DAG 감소를 실제 node/edge/operation/materialized-cell 수로 보고한다.
- 구현하지 않은 것을 구현했다고 쓰지 않는다.

## 1단계: ZIP 감사

압축을 풀고 다음을 찾는다.

- shape parser/normalizer
- compact physics
- classifier/solver entrypoint
- worker message protocol
- mode switch
- proof node/edge types
- graph adapter/DAG/Tree conversion
- shape preview materialization
- cache
- tests/scripts/package.json

파일 목록과 호출 그래프를 `reports/fastpath_source_audit.md`에 기록한다.

## 2단계: 기준선 측정

코드 수정 전에 필수 target과 대표 fixture를 construction mode로 실행한다.

반드시 기록:

- total wall time 및 phase time
- provider inverse calls
- generated candidates
- recursive goals
- cache hits/misses
- proof nodes/edges/operations
- materialized shape 수/cell 수
- graph layout time
- generic planner 진입 여부

결과를 `reports/fastpath_baseline.json`에 저장한다.

## 3단계: 공통 StructuralFeatures

parse/normalize/pillar/half/receipt/crystal/stack-boundary 정보를 요청당 한 번만 계산하는 immutable compact feature object를 구현한다.

- 회전별 문자열 4개 생성 금지
- integer mask/view 사용
- feature cache version token 추가
- 단위 테스트로 O(L) scan count 확인

## 4단계: FastStructuralCompiler registry

다음 순서의 registry를 구현한다.

```text
Basic
Corner
Half subtypes
Swappable
Simple Stack
no-overflow receipt
```

각 compiler는 `match(features)`와 `compile(match, mode)`를 제공한다. 후보 compiler 수는 상수다.

## 5단계: Half subtype 실험 기반 도출

외부 ShapeType과 별도의 내부 subtype을 둔다.

초기:

```text
HALF_DIRECT
HALF_MONOTONE_STACK
HALF_SINGLE_SWAP
HALF_NO_OVERFLOW_PIN
HALF_PERIODIC_PIN_SWAP
HALF_EVENT_SEQUENCE
```

먼저 필수 target의 `HALF_PERIODIC_PIN_SWAP`을 실제 primitive sequence로 구현한다.

중요:

- 사진/레거시 중간 도형에서 실제 순차 Pin/Swap 과정을 복원한다.
- 구조 word를 단순 재조립하는 가짜 replay는 최종 증명이 아니다.
- 각 primitive를 프로젝트 physics로 replay해 최종 target과 정확히 일치시킨다.
- period 탐색은 event gap/KMP/Z 등으로 최악 O(L)이어야 한다.
- 과매칭 mutation을 모두 replay 또는 거부한다.

그 후 legacy/data corpus의 Half들을 signature로 군집화한다.

권장 signature:

- support spine mask
- crystal event sequence/gaps
- pin event sequence
- stable cut axes
- unique stack ownership boundary
- row transition word
- orientation class

각 군집마다:

1. 대표/경계/반례 추출
2. 전용 O(L) recognizer 후보
3. concrete constructor
4. primitive replay
5. small-cap exact differential
6. 성공한 것만 registry 승격

## 6단계: Simple Stack/Swap/Receipt

- Stack: 모든 split을 solve하지 말고 ownership transition으로 유일/상수 후보만 산출
- Swap: cut-stable source halves를 직접 구성하고 Swap 1회
- Receipt: prefix 한 번 스캔, core solve 1회, PinPush k회 append

모호하면 기존 generic engine으로 fallback한다.

## 7단계: Proof IR

전체 shape를 모든 node에 저장하지 않는다.

- parent ids
- operation + args
- changed rows/cells delta
- result hash
- replay status
- 간헐적 checkpoint

DAG와 Tree는 같은 compact proof를 읽고, Tree는 view occurrence만 복제한다.

shape preview는 선택/viewport 진입 시 lazy materialize한다.

## 8단계: 모드 분리

FAST:
- proof node 0
- full witness table/graph/layout 0

ANALYSIS:
- subtype/reason/compact decomposition만
- proof lowering/layout 0

CONSTRUCTION:
- 선택 proof만 lowering/replay
- 초기 전체 node preview 생성 금지

각 금지 경로가 실제로 호출되지 않았음을 metrics test로 증명한다.

## 9단계: Generic fallback 최적화

- shared provider spool
- positive/negative subgoal memoization
- solve/analyze inverse 중복 제거
- existence mode first witness stop
- min-cost mode만 branch-and-bound
- lazy candidate iterator
- symmetry compact canonicalization
- cache versioning

## 10단계: 필수 테스트

`02_TEST_MATRIX_KO.md`를 모두 구현한다.

특히 필수 target에서:

- primitive replay PASS
- generic planner calls 0
- inspected rows <= 명시 상수 × L
- node 50% 이상 감소
- materialized cell 45% 이상 감소
- fast/analysis/construction 분리 PASS

그리고 L=10,20,50,100,200,500 성장률을 보고한다.

## 11단계: 산출물

최종적으로 다음을 생성한다.

```text
Shapez2-TMAM-Web-Studio-2.2.0-Focused-UI-Main4-PP-FastPath.zip
reports/fastpath_source_audit.md
reports/fastpath_baseline.json
reports/fastpath_validation.json
reports/fastpath_growth.json
reports/fastpath_dag_comparison.json
reports/fastpath_failures.json
FASTPATH_IMPLEMENTATION_KO.md
```

ZIP을 다시 압축 해제해 다음을 재실행한다.

- unit tests
- typecheck
- worker build
- production build/static export
- worker smoke
- static smoke
- 필수 target construction/replay

최종 답변에는 측정값, 미해결 경계, SHA256, 실제 ZIP 링크만 명확히 제공한다.

작업 도중 질문으로 멈추지 말고, 실패하면 원인을 최소 반례와 로그로 남긴 뒤 수정·재실행한다.

---
