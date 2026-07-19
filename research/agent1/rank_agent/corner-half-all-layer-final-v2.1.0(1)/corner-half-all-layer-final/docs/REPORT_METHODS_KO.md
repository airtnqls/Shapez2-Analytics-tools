# 검증 방법

## 1. 판정 언어

`test_corner_exact.py`는 길이 0–9의 모든 문자열 349,525개에서 다음을
비교한다.

1. 여섯 Python forbidden regex
2. 최소 19상태 DFA
3. semantic factor/route parser

불일치는 0이다.

## 2. 물리와 안정성

`research_physics.py`와 `structural_physics.py`는 독립적으로 작성한 구조
물리 구현이다.

- 전체 소형 상태 65,792개
- 단일 row 256개
- row pair 65,536개

또한 `test_stability_characterization.py`는:

```text
Stable(X) <=> every occupied cell belongs to support_closure(X)
```

을 cap2 전체 65,536상태와 3~30층 무작위 100,000상태에서 slow full-gravity
정의와 대조한다.

## 3. Corner component와 constructor

segment/zone natural/event planner는 각 move를 독립 1D semantics로 재생한다.
그 다음 두 수준을 검사한다.

- `corner_macro_replay.py`: C1–C7 helper 설치 뒤 실제 forward operation.
- `corner_full_replay.py`: 모든 intermediate를 실제 4열 structural shape로 유지.

compact constructor는 길이0..10의 수용열 104,191개 전체와 고층 생성
corpus에서 검사한다.

## 4. C7

세 종류의 검증을 사용한다.

1. cap6 single-duty systematic enumeration
2. separated multi-duty systematic/random generation
3. 실제 event-language column에서 생성한 duty 목록

모든 certificate는 다음을 별도로 확인한다.

```text
predecessor stable
helper columns Corner-craftable
PinPush(predecessor).A == expected A
```

## 5. Half 정리

cap1–6에서는 cpcp exact HalfSet을 bitset으로 export한 oracle과 theorem이
예측한 key 집합을 **비트 단위로 전부 비교**한다. 단순 count 비교가 아니다.
모든 cap에서 false positive와 false negative가 0이다.

cap7은 4,320 craftable columns의 ordered pair를 support criterion으로 세어
published exact total 7,905,398과 대조한다.

constructor 검증은 실제 Swap → Rotate → Cut replay를 사용한다.

## 6. Raw-operation proof DAG

`proof_dag.py`의 verifier는 compact certificate의 result를 믿지 않고 각
노드를 child 결과에서 다시 실행한다. 잎은 raw `SSSS` 한 종류뿐이다.

대형 forest는 메모리 반환을 보장하기 위해 다음 세 명령을 별도 프로세스로
실행한다.

```bash
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode corner7
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode half4
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode high189
```

결과는 `reports/PROOF_DAG_AUDIT.json`에 보존한다.

- cap7 모든 Corner 4,320 roots
- cap4 모든 Half 16,193 roots
- 189층 event Corner stress proof

모두 replay/stability failure 0이다.

## 7. 결정성

1,000 Corner + 1,000 Half를 독립 재생하여 certificate hash를 비교한다.
고정 SHA-256은:

```text
f3fa1b522f90018ed8310bc85db62c18a28aa2afa389811f84d786c2dd2a37e6
```

## 8. 테스트의 역할

전수/무작위 검사는 구현 오류 탐지용이다. 전층 완전성은 다음 문서의
귀납·직접 construction으로 증명한다.

- `CORNER_CONSTRUCTOR_PROOF_KO.md`
- `HALF_FAMILY_THEOREM_KO.md`
- `RAW_OPERATION_PROOF_DAG_KO.md`

Proof assistant kernel proof는 아니며, 자족적 수학 증명과 독립 실행 가능한
forward certificate를 결합한다.
