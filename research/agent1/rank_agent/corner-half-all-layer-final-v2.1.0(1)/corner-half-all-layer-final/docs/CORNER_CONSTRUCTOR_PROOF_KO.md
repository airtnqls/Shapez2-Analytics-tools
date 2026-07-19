# 전층 Corner 판정·구성 정리

## 1. 대상과 표기

한 열은 아래에서 위로 읽은 문자열 `w ∈ {-,S,P,c}*`이다. 맨 위의 `-`는 제거한다. `S`는 모든 일반 조각을 구조적으로 합친 기호다. 층 제한은 임의의 유한한 `L`이며 `|w| ≤ L`이다.

이 브랜치는 다음 두 함수를 제공한다.

```python
is_craftable_column(w) -> bool
construct_corner(w, L) -> CornerConstructionCertificate
```

그리고 실제 네 열 연산까지 내린 재생기는 다음이다.

```python
compile_corner_ir(w, L)      # C1..C7 선형 IR
replay_corner_full(w, L)     # Stack/Generator/Swap/Cut/Push 실제 재생
```

## 2. 판정 정리

**정리 C-Membership.** `w`가 제작 가능한 도형의 한 열로 나타날 수 있을 필요충분조건은 다음 여섯 금지 검색 패턴 중 어느 것도 포함하지 않는 것이다.

```text
R1  -P
R2  ^P*-+c
R3  [^P]P.*c
R4  c-.*c
R5  cS-+c
R6  ^S*-?S*c(.*c)?(S-+)+c
```

구현은 여섯 정규식을 매번 실행하지 않는다. Thompson NFA를 합성하고, reachable DFA를 만든 다음, 동치 상태를 최소화한다. 결과는 19상태 DFA이며 문자열을 한 번만 읽는다.

```text
시간  Θ(L)
메모리 Θ(1)  (입력을 제외한 DFA 상태)
```

금지 상태에 처음 진입하면 `RejectionCertificate(rule, position, prefix)`를 반환한다.

## 3. 의미론적 분해

crystal이 있는 열은 유일하게 다음과 같이 분해된다.

```text
w = Z · c · I1 · c · ... · Im · c · T
```

- `Z`: 최하 crystal 아래 zone
- `Ij`: 두 생존 crystal 사이의 내부 segment
- `T`: 최고 crystal 위의 crystal-free top

DFA 통과 여부는 다음 의미론적 언어와 동치다.

- `I_weak`: event가 허용될 때 가능한 segment
- `I_nat`: overflow event 없이 가능한 segment
- `Z_evt`: event receipt가 있는 zone
- `Z_nat`: event 없는 zone

`analyze_column()`은 자연 경로, event 경로, crystal-free 경로를 결정하고 각 영역 witness를 반환한다.

## 4. 자연 경로 constructor

자연 경로는 다음 유한 일정으로 구성한다.

1. 각 zone/segment witness의 snapshot-S 위치를 C1 또는 C2로 배치한다.
2. 하나의 Generator(C3)로 모든 예정 crystal을 동시에 만든다.
3. plain push가 필요한 zone이면 snapshot bottom이 아직 점유된 동안 C6를 수행한다.
4. 각 sacrificial crystal run을 C4로 제거한다.
5. 각 자연 낙하 조각을 C5로 정확히 한 번 떨어뜨린다.
6. 최고 keeper 위 `T`를 C1/C2로 쌓는다.

`component_plans.py`는 각 segment와 zone에 대해 snapshot과 C4/C5 순서를 결정론적으로 만든다. `corner_natural_plan.py`는 이 component들을 절대 층 좌표로 결합한다.

### 자연 경로의 건전성

각 C-rule은 target A에 대해 다음 국소 효과만 낸다.

- C1: 현재 열의 top에 S 또는 P 한 칸 추가
- C2: 인접 열의 tower에 걸친 `SS` 조각으로 gap 위 S를 anchored 배치
- C3: 현재 global height 아래 `-`/`P`를 c로 변환
- C4: D의 단일 sacrificial c와 cut-adjacent한 A crystal run만 shatter
- C5: B의 해당 층을 P로 만들어 A의 지정 S만 자연 낙하
- C6: cap 미만에서 support-preserving pure lift와 typed receipt

따라서 IR 재생 결과는 component witness의 1차원 이동계와 동일하다.

### 자연 경로의 완전성

판정 정리의 `I_nat`, `Z_nat`, crystal-free top 각각에 대해 component constructor가 존재한다. snapshot을 한 번에 합친 뒤 영역별 C4/C5를 독립적으로 실행할 수 있다. 영역은 생존 keeper crystal로 분리되어 있으므로 한 영역의 shatter/descent가 다른 영역의 조각 수나 순서를 변경하지 않는다.

## 5. C7 overflow event 정리

자연 경로로 만들 수 없는 weak-strict segment와 일부 zone은 하나의 overflow event를 사용한다.

각 duty는 다음 중 하나다.

```text
ANCHORED  source f → target t
NATURAL   source f → surviving blocker 위 t
FLOOR     source f → floor/receipt cell 0
```

`compile_c7(post_lift_A, L, duties)`는 A-B-C-D 네 열 predecessor를 공식으로 만든다.

- C: `c^L` trigger column
- B: 모든 static duty 층에 S, 각 faller source 층에 P인 연속 tower
- D: duty별 anchor/pedestal/relay/rider를 합친 연속 tower
- A: event 직전 target snapshot

### C7 불변식

1. predecessor 전체는 안정하다.
2. C의 최고 crystal overflow가 C 전체를 파괴한다.
3. 각 D relay crystal은 C와 연결되어 같은 event에서 파괴된다.
4. B의 source-level P는 faller에 수평 support를 주지 않는다.
5. D rider는 faller와 같은 수평 group으로 낙하해 지정 target에서 멈춘다.
6. static A cell은 B의 S duty로 고정된다.
7. 서로 다른 duty unit은 survivor anchor/keeper와 높이 간격으로 분리된다.
8. event 후 A는 `_expected_after_event()`와 정확히 같다.

### C7 predecessor 제작의 비순환성

C7 predecessor의 네 열 `(A,B,C,D)`는 모두 자연 경로 열이다. 또한 orientation `(B,C)|(D,A)`에서 두 half가 각각 안정하다. 따라서:

1. 자연 Corner constructor로 stable half `(B,C)`를 만든다.
2. 자연 Corner constructor로 stable half `(D,A)`를 만든다.
3. Swapper로 `(B,C,D,A)`를 만든다.
4. 시계 방향 회전으로 `(A,B,C,D)`를 얻는다.
5. Pin Pusher를 적용한다.

이 과정은 event Corner를 다시 부모로 요구하지 않으므로 순환하지 않는다.

## 6. primitive prefab의 원재료 도달성

C1..C7이 사용하는 모든 helper는 raw input `SSSS`에서 제작된다.

- 임의 단층 S mask: Cutter/Rotate/Swapper
- solid tower: 단층 mask 반복 Stack
- 단일 P: `build_one_pin()`의 pedestal/overflow/shatter/isolate recipe
- 한 층만 c인 solid helper: 그 층만 gap인 S scaffold를 Stack한 뒤 Generator
- 한 층만 P인 solid helper: 아래 solid 층 → one-pin layer → 위 solid 층
- `c^L` trigger: target 열만 빈 full tower를 만든 뒤 Generator

`primitive_prefabs.py`는 위 recipe를 실제 structural operation으로 재생한다. 특히 pin은 입력으로 가정하지 않는다.

## 7. 실제 네 열 full replay

`compile_corner_ir()`은 모든 accepted `w`를 C1..C7 선형 프로그램으로 내린다. `replay_corner_full()`은 각 IR step마다:

- 필요한 helper prefab을 별도 child certificate로 제작하고,
- Swapper로 helper를 설치하고,
- 실제 Stack/Generator/Cut/PinPush를 수행하고,
- helper를 canonical solid tower로 복원한다.

모든 `FullOperationStep`에는 `before`, `operand`, `after`, target-column before/after가 기록된다. 따라서 integration branch는 이를 그대로 proof tree node로 바꿀 수 있다.

## 8. 종료성과 복잡도

- DFA 판정: `Θ(L)`
- semantic factorization 및 component 계획: `Θ(L)`
- C7 duty 수: 최대 `O(L)`
- Corner IR 길이: `O(L)`
- 압축 certificate 생성: `O(L)`
- helper recipe를 중복 없이 DAG로 공유한 proof 크기: 다항식
- helper를 매 step 독립 확장하는 단순 선형 목록: 최악 `O(L²)`

모든 loop는 층 좌표를 단조롭게 소비하거나 유한한 duty/move 목록을 소비하므로 모든 유한 L에서 종료한다.

## 9. 결론

**정리 C-Construct.** 모든 유한 `L`과 모든 `|w|≤L`에 대해:

```text
is_craftable_column(w) = True
```

이면 `replay_corner_full(w,L)`은 raw input prefab leaf와 실제 game operation으로 이루어진 유한 proof를 반환하며, 모든 intermediate가 안정하고 최종 q0 column은 정확히 `w`이다. 반대로 DFA reject certificate가 있으면 판정 정리에 의해 어떤 제작 과정도 존재하지 않는다.
