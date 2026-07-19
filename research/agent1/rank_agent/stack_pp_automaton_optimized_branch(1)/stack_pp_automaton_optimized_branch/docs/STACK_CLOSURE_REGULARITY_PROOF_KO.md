# 유한 base family에 대한 전층 Stack closure 정규성

## 1. 명제

폭 4의 구조 도형을 아래에서 위로 읽는다. 한 층은 각 셀이
`-/S/P/c` 중 하나이므로 층 알파벳은 유한하며 크기는 `4^4=256`이다.

다음을 가정한다.

1. 아래 도형 family `F`가 결정론적 유한 layer automaton으로 인식된다.
2. 위에 올리는 각 비어 있지 않은 가시 단층 조각은 유한한 local
   `TopPiecePolicy`로 판정된다.
3. Stack 전상은 canonical visible 동치류로 센다.
   - 결과에 보이는 crystal은 모두 아래 도형 A 소유다.
   - 각 열의 보이는 소유권은 `A* B*`이다.
   - 사라지는 추가 top crystal/상단 garbage는 정규형에서 제외한다.

그러면 다음 언어는 정규언어다.

```text
StackClosure(F) = {
    X | 어떤 안정 A∈F와 허용 단층 조각열 B₀,...,Bₖ가 존재하여
        순서대로 Stack하면 X가 됨
}
```

구현은 `StackClosureAutomaton`이다.

## 2. 비결정 product 상태

한 ownership 경로를 읽는 데 필요한 장기 정보는 다음뿐이다.

```text
m       : 네 열 중 이미 B로 전환된 열, 4비트
has_A   : A가 비어 있지 않은가
β       : 처리한 A prefix의 정확한 support behavior
q       : base-family automaton 상태
```

`β`는 위 경계의 현재 crystal 네 칸에 어떤 외부 support가 들어오는지
16가지 입력 각각에 대해, 현재 경계 support와 이미 잊힌 prefix가 전부
지지되는지를 반환하는 유한 진리표다. 폭이 4로 고정되어 있으므로
가능한 behavior의 우주는 유한하다.

현재 target row와 직전 target row가 주어지면 다음은 모두 국소 계산이다.

- 새로 A→B 전환할 열 선택
- visible target crystal을 B로 보내지 않는 검사
- B pin의 자연 착지 검사
- B normal 수평 성분의 anchor 검사
- top-piece policy 검사
- A support behavior 합성
- base-family 상태 전이

따라서 한 ownership 경로의 product state 우주는 유한하다.

## 3. powerset 결정화

같은 target prefix에는 여러 ownership 경로가 있을 수 있다. 결정론적
closure automaton의 상태를 다음으로 둔다.

```text
(last_target_row, reachable_product_states)
```

`last_target_row`는 다음 층의 착지 판정에 필요하며 256가지뿐이다.
`reachable_product_states`는 유한 product-state 우주의 부분집합이다.

새 target row를 읽으면 모든 현재 product state의 국소 전이를 합집합해
다음 부분집합을 얻는다. 이것은 표준 powerset construction이므로
결정론적이며 상태 우주도 유한하다.

## 4. 수용 조건

입력을 다 읽은 뒤 reachable product state 중 하나가 다음을 만족하면
수용한다.

```text
B가 비어 있지 않음
A가 비어 있지 않음
위에서 추가 support를 주지 않아도 A 전체가 안정함
base-family state가 수용 상태임
```

## 5. 건전성

수용 product path를 하나 선택한다. 각 층 전이는:

- 열별 `A*B*` 소유권을 보존하고,
- visible B의 정확한 착지를 보장하고,
- A support behavior를 실제 support 규칙과 동일하게 합성하고,
- A의 row stream을 `F` automaton에 통과시킨다.

종료 수용 조건으로 A는 안정하고 `A∈F`다. 각 비어 있지 않은 B row는
허용 top piece다. ownership path를 materialize한 후 forward Stack replay로
X가 재현된다.

## 6. 완전성

X에 실제 canonical Stack 제작이 존재한다고 하자. 각 target 셀을 실제
아래 도형 A와 순서대로 쌓인 가시 단층 조각 소유로 표시한다.

- 같은 열에서 B 조각은 A 조각을 통과하지 않으므로 ownership은 `A*B*`다.
- Stack top의 crystal은 결과 전에 제거되므로 visible crystal은 A다.
- 실제로 착지한 B pin/normal 성분은 국소 착지 검사를 통과한다.
- 실제 A의 support derivation은 support behavior 전이 경로에 포함된다.
- A∈F이므로 family 상태도 수용한다.

따라서 실제 제작은 시작 powerset 상태에서 수용 상태까지의 한 경로를
정의한다. 완전한 전상이 있는데 automaton이 거부할 수 없다.

## 7. 복잡도와 한계

최소화된 closure automaton이 준비되어 있으면 membership는 명시적 L층
입력에 대해 `Θ(L)`이다. target별 witness DAG도 층별 reachable state 수에
비례하고, 모든 witness 출력은 output-sensitive다.

다만 powerset 상한은 매우 크다. 유한성은 상태 수가 작다는 뜻이 아니다.
실측 universal base family에서는 정확한 깊이별 reachable state가:

```text
0층:    1
1층:  256
2층: 4019
```

이었다. 따라서 다음 단계에는 residual equivalence/minimization과 실제
HalfFamily가 주는 강한 pruning이 필요하다.

이 정리는 Stack closure에 대한 것이다. `PinPush(F)`가 같은 작은 유한
표현으로 닫힌다는 정리나, PP rank를 무한히 반복했을 때 상태 수가
통제된다는 정리는 포함하지 않는다.
