# Crystal Generator 전층 정규형과 family-제약 역관계

## 0. 범위

이 문서는 Shapez 2 Quad Mode의 Crystal Generator 한 연산을 모든 유한 층수에 대해 다룬다.
목표는 다음 네 가지다.

1. Generator의 정확한 전방 의미를 고정한다.
2. 어떤 도형이 Generator의 결과가 될 수 있는지 즉시 판정한다.
3. 가능한 전상을 개별 도형으로 열거하지 않고 층별 제약으로 표현한다.
4. 그 제약을 이미 증명된 제작 가능 family와 직접 교차하여 부모 증명을 찾는다.

이 정리는 전체 TMAM의 완전성을 혼자 증명하지 않는다. Generator 노드는 정확히 해결하지만,
그 이전 도형이 제작 가능한지는 전달받은 family가 책임진다.

---

## 1. 모델

한 셀의 구조 종류는 다음 네 개다.

```text
-  빈칸
S  임의의 일반 조각
P  핀
c  크리스탈
```

정확한 도형에서는 일반 조각의 subtype/색상과 크리스탈 색상도 보존한다.
층은 아래에서 위로 `0,1,...`이고, 네 열은 `q=0,1,2,3`이다.

도형 `Y`의 전역 높이 `H(Y)`는 가장 높은 점유 셀의 층 번호에 1을 더한 값이다.
점유 셀이 없으면 `H(Y)=0`이다.

선택된 Generator 색상을 `k`라고 하자. 전방 연산 `G_k`는 다음과 같다.

- `H=H(Y)`를 먼저 계산한다.
- 모든 `0 <= l < H`, 모든 열 `q`에 대해:
  - `Y[l,q]`가 `-` 또는 `P`이면 `k`색 크리스탈로 바꾼다.
  - 일반 조각 또는 기존 크리스탈이면 그대로 둔다.
- `l >= H`에는 아무것도 만들지 않는다.
- 중력을 호출하지 않는다.

Generator가 끝난 직후 `0..H-1`의 모든 셀이 점유되어 있으므로 중력이 필요하지 않다.

---

## 2. Generator 결과 도형의 완전 특성화

### 정리 1 — 비생산적 결과까지 포함한 image 정리

비어 있지 않은 도형 `X`가 색상 `k` Generator의 결과일 필요충분조건은 다음과 같다.

1. `X`의 높이를 `H`라고 할 때, `0 <= l < H`의 모든 셀이 점유되어 있다.
2. `X`에는 핀이 없다.

즉 `X`는 일반 조각과 크리스탈만으로 꽉 찬 `H x 4` 직사각 슬래브다.

#### 필요성

Generator는 높이 아래의 모든 빈칸과 핀을 크리스탈로 바꾼다. 일반 조각과 기존
크리스탈도 점유 상태를 유지한다. 따라서 결과의 높이 아래에는 빈칸과 핀이 없다.
입력 최상층의 적어도 한 셀은 점유되어 있었고, 그 셀은 사라지지 않으므로 높이도 같다.

#### 충분성

조건을 만족하는 `X`에 대해 입력을 그대로 `Y=X`로 두면 된다. `X`에는 빈칸과 핀이
없으므로 Generator는 아무 셀도 바꾸지 않고 `G_k(Y)=X`다. 이 증명은 no-op 전상까지
허용한 image 정리다.

빈 도형은 빈 도형에서만 나온다.

### 정리 2 — 생산적 Generator 결과

`G_k(Y)=X`이고 `Y != X`인 생산적 전상이 존재할 필요충분조건은:

1. `X`가 정리 1의 완전 슬래브이고,
2. `X`에 색상 `k`의 크리스탈이 하나 이상 존재한다.

충분성은 그 크리스탈 하나를 입력에서 핀으로 바꾸면 된다. 입력은 여전히 완전 슬래브라
높이가 유지되고 안정하며, Generator가 그 핀을 원래 `k`색 크리스탈로 되돌린다.

이 한-핀 전상은 **항상 안정한 전상**이지만, 반드시 제작 가능한 전상이라는 뜻은 아니다.
제작 가능성은 family 교집합으로 판정해야 한다.

---

## 3. 모든 전상의 정확한 셀별 정규형

`X`가 정리 1을 만족한다고 하자. `Y`가 `G_k(Y)=X`를 만족할 필요충분조건은 다음이다.

- `X[l,q]`가 일반 조각이면 `Y[l,q]`는 동일 subtype/색상의 일반 조각이다.
- `X[l,q]`가 `k`가 아닌 색의 크리스탈이면 `Y[l,q]`는 동일 크리스탈이다.
- `X[l,q]`가 `k`색 크리스탈이면 `Y[l,q]`는 정확히 다음 셋 중 하나다.

```text
- , P , 같은 k색 크리스탈
```

추가 전역 조건:

- `H(Y)=H(X)`여야 하므로 입력 최상층이 전부 빈칸이면 안 된다.
- 생산적 전상에서는 적어도 한 `k`색 크리스탈 위치가 입력에서 `-` 또는 `P`여야 한다.

### 건전성

위 조건을 만족하는 각 셀에 전방 규칙을 적용하면 모든 셀이 정확히 `X`로 간다.
최상층 비공백 조건 때문에 Generator가 사용하는 높이도 `H(X)`다.

### 완전성

`G_k(Y)=X`인 실제 전상을 하나 잡는다. 전방 정의를 셀별로 역으로 읽으면 일반 조각과
다른 색 크리스탈은 고정될 수밖에 없고, `k`색 크리스탈만 `-/P/c_k` 중 하나일 수 있다.
또한 입력과 출력 높이가 같으므로 최상층은 비어 있지 않다. 따라서 위 목록이 모든 전상이다.

---

## 4. 전상을 열거하지 않는 표현

한 층은 네 셀이고, 각 셀은 2비트이므로 한 층 구조는 `0..255`의 정수 하나로 표현한다.
목표의 각 층마다 다음 세 마스크만 저장한다.

```text
normal_mask           고정 일반 조각
fixed_crystal_mask    Generator 색상과 다른 고정 크리스탈
eligible_mask         - / P / c 중 하나로 역선택 가능한 목표색 크리스탈
```

한 층의 `eligible_mask` 비트 수가 `r`이면 허용 입력 행은 최대 `3^r <= 81`개다.
도형 전체 후보 수가 `3^(4H)`까지 커져도 이를 리스트나 집합으로 만들지 않는다.

---

## 5. Family-제약 역산

이미 제작 가능하다고 증명된 family `F`가 아래에서 위로 층을 읽는 결정적 automaton으로
표현된다고 하자.

```text
q0 = F.initial_state()
q(l+1) = F.transition(q(l), predecessor_row_l)
accept iff F.is_accepting(qH)
```

Generator 역산기는 다음 product state만 유지한다.

```text
(family_state, changed_bit)
```

`changed_bit`는 지금까지 실제로 생성된 셀이 하나 이상 있었는지 나타낸다.
각 층에서 최대 81개의 허용 행만 `F.transition`에 넣는다. 최상층에서는 전부 빈 행을
제외하고, 마지막에는 family accept와 `changed_bit=1`을 동시에 요구한다.

### 정리 3 — Product DP 건전성

DP가 반환한 행 경로는 각 층의 Generator 역제약을 만족하고, family automaton의 accept
경로다. 따라서 반환 도형은 `F`에 속하며 Generator로 목표를 정확히 재생한다.

### 정리 4 — Product DP 완전성

`Y in F`이고 `G_k(Y)=X`인 실제 생산적 부모가 있다고 하자. 정리 3의 셀별 역정규형 때문에
`Y`의 매 층은 DP가 열거하는 최대 81개 행 중 하나다. `Y in F`이므로 그 행열은 family
accept 경로를 만든다. 생산적이므로 마지막 `changed_bit=1`이다. 따라서 DP는 모든 실제
family 부모를 포함하며, 부모가 있는데 실패할 수 없다.

### 복잡도

family 상태 수를 `|Q|`, 높이를 `H`라 하면:

```text
존재 판정 / 최소 witness: O(81 * H * |Q|) = O(H|Q|)
count (결정적 family):    O(H|Q|)
메모리, 존재/count:       O(|Q|)
메모리, witness 복원:     O(H|Q|)
```

폭 4가 고정이므로 81은 상수다.

---

## 6. 종료 척도와 no-op 제거

`Y=X`인 Generator no-op를 proof graph에 허용하면 다음 자기순환이 생긴다.

```text
X <-Generator- X
```

따라서 TMAM proof search에서는 기본적으로 `productive_only=True`를 사용한다.
생산적 Generator 역간선에서는 변경 셀마다 목표의 크리스탈 하나가 입력의 빈칸 또는 핀으로
바뀐다. 나머지 셀은 크리스탈 수를 늘리지 않으므로:

```text
crystal_count(parent) < crystal_count(target)
```

가 엄격히 성립한다. 따라서 Generator 역간선만 연속으로 따라가는 경로는 반드시 종료한다.
전체 TMAM의 Stack/PinPush 등을 포함한 종료성은 별도의 rank가 필요하지만, Generator가
순환을 만드는 문제는 이 척도로 닫힌다.

---

## 7. 색상 선택

생산적 Generator 색상은 목표에 실제로 존재하는 크리스탈 색 중 하나여야 한다.
색상 종류는 게임에서 상수 개이므로 각 후보 색에 대해 동일한 product DP를 실행할 수 있다.

구조 검색이 끝난 뒤:

- 고정 일반 조각은 subtype/색상을 목표에서 복사한다.
- 선택 색과 다른 기존 크리스탈도 목표에서 복사한다.
- 선택 색 위치에서 DP가 `c`를 골랐다면 기존 크리스탈로 복사한다.
- `P` 또는 `-`를 골랐다면 핀/빈칸으로 복원한다.

전방 exact replay로 최종 인증한다.

---

## 8. 세 가지 canonical predecessor

### Raw 최소 부모

family 제약 없이 가장 많은 목표색 크리스탈을 실제 생성하도록 선택한다. 최상층 높이 유지를
위해 필요하면 핀 하나만 둔다. 빠른 예시와 상태 수 측정용이며 안정성·제작 가능성을 보장하지
않는다.

### Stable single-pin 부모

목표를 그대로 복사하고 목표색 크리스탈 하나만 핀으로 바꾼다. 항상 완전 슬래브이므로
안정하고 생산적이다. 그러나 제작 가능 family에 속하는지는 별도 문제다.

### Family canonical 부모

실제 TMAM에서는 이것만 사용한다. family automaton과 product DP를 수행하고 다음 비용을
최소화한다.

```text
기존부터 있던 목표색 크리스탈 수
핀 수
빈칸 수
고정 행 순서
```

다른 비용 정책이 필요하면 planner 쪽에서 대체할 수 있다.

---

## 9. 현재 프로젝트 Shape.py와의 차이

현재 저장소 구현은 빈 입력이면 임의의 빈 한 층을 추가한 뒤 전부 크리스탈로 채운다. 이는
기준 의미의 `Generator(empty)=empty`와 다르다. 또한 실제 점유 높이가 아니라 내부
`layers` 리스트 전체를 채우므로 trailing empty layer가 있으면 결과 높이가 잘못 늘어날 수
있다. 마지막으로 완전 슬래브에 중력을 다시 호출하지만 의미상 필요하지 않다.

이 브랜치의 `patches/shape_py_crystal_generator.patch`는 다음을 고친다.

1. 점유 높이 `H`를 먼저 계산한다.
2. 빈 입력은 빈 출력으로 유지한다.
3. `0..H-1`만 변환한다.
4. 중력 재호출을 제거한다.

---

## 10. 다른 연산과의 정규화 법칙

### 멱등성

첫 Generator 뒤에는 높이 아래에 빈칸과 핀이 없으므로 어떤 색의 Generator를 곧바로 다시
적용해도 아무 변화가 없다. 시간 순서로 `G_a` 다음 `G_b`라면:

```text
G_b(G_a(X)) = G_a(X)
```

따라서 최소 proof에서 연속 Generator는 첫 번째 하나만 남긴다.

### 회전·반사 교환

Generator는 각 셀 종류에 동일한 국소 치환을 적용하고 높이를 바꾸지 않으므로 회전 `R`과
반사 `M`에 대해:

```text
R(G_k(X)) = G_k(R(X))
M(G_k(X)) = G_k(M(X))
```

이 법칙으로 planner는 회전 canonicalization을 Generator 전후 어느 한쪽으로 모을 수 있다.

### 마지막 생성 snapshot

한 제작 역사에서 마지막 Generator 직후 snapshot은 높이 아래가 일반 조각/크리스탈로 완전히
차 있다. 그러므로 최종 도형에서 그 snapshot의 생존 material 아래에 보이는 핀과 gap은 반드시
마지막 Generator 이후 PinPush, crystal shatter, cut/gravity 등의 결과다. Corner/Half/PP branch는
이 사실을 불가능 규칙과 frontier state 축소에 재사용할 수 있다.

### 교환을 주장하지 않는 연산

Generator는 Cut, Stack, PinPush와 일반적으로 교환하지 않는다. crystal 연결, global height,
overflow가 달라지기 때문이다. 이 세 연산과의 순서는 proof tree에 그대로 보존한다.

---

## 11. 전체 TMAM과의 결합

Generator는 독립 ShapeType이 아니라 proof edge다.

```text
ProofNode(
  operation = GENERATOR,
  child = predecessor_proof,
  params = {color, changed_masks},
  certificate = GeneratorWitness,
)
```

planner는 목표가 full/pin-free image 조건을 통과할 때만 Generator branch를 연다. 이후
`GeneratorConstraint ∩ lower_rank_family`를 계산한다. 일반 전상을 만들고 다시 `solve()`를
호출하는 방식은 사용하지 않는다.

Generator branch가 다른 팀에 요구하는 인터페이스는 오직 다음이다.

```python
family.initial_state()
family.transition(state, layer_word) -> state | None
family.is_accepting(state) -> bool
```

따라서 Corner/Half/Stack/PP family가 동일한 층 automaton 계약을 제공하면 바로 product로
합쳐진다.
