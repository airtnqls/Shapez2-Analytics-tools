# Shapez 2 Claw 역산기: O(L^4) Eager-Column 연구 체크포인트

## 1. 현재 O(L^5)의 원인

현재 frontier solver의 비상수 상태는

- 처리한 predecessor source layer `s` — O(L)
- 네 열의 target ordinary/pin cursor `(c0,c1,c2,c3)` — O(L^4)

이고 support / destroy-connectivity / pillar-DFA / cutter-axis 상태는 폭 4 고정이므로 L과 무관한 상수 상태다.
따라서 거친 상한은 O(L^5)이다.

## 2. 정의

Pin Push 후 생기는 바닥 receipt pin을 각 열의 token sequence에서 먼저 제거한다.

처리된 predecessor row가 `0..s`일 때, `R=s+1`이라 두고:

- `E_q(R)` = target의 q열에서 높이 `<=R`인 ordinary/pin token 개수
- `C_q(s)` = predecessor의 q열에서 source row `<=s`에 배치한 ordinary/pin 개수
- `delta_q(s) = E_q(s+1) - C_q(s)`

열 순서가 보존되고 source row s의 조각은 lift 후 s+1보다 위로 갈 수 없으므로 항상 `delta_q >= 0`이다.

`delta_q=0`인 열을 **eager column**이라 부른다. 그 열에는 아직 읽지 않은 높은 source row에서 현재 result prefix 안으로 떨어질 token이 없다.

## 3. Eager-Column Lemma 후보

> 안정한 overflow Pin-Push predecessor X에 대해, 모든 source cut s에서
>
> `min_q delta_q(s) = 0`.

즉 매 단계마다 적어도 한 열은 eager다.

plain Pin Push는 별도 O(L) inverse로 처리하므로 이 정리는 overflow 경로에만 필요하다.

## 4. 복잡도 감소

source s와 eager 열 q를 고정하면

`C_q(s) = E_q(s+1)`

이므로 q열 cursor는 target과 s에서 직접 계산된다. 저장할 자유 cursor는 나머지 세 개뿐이다.

- eager 열 선택: 4가지 — 상수
- source: O(L)
- 나머지 cursor 3개: O(L^3)
- 고정 폭 automaton state: 상수
- row transition 선택: 상수

따라서 시간과 메모리 상태 수가

`O(4 * L * L^3) = O(L^4)`

가 된다.

여러 열이 eager이면 가장 작은 q를 canonical leader로 선택하거나, 4개 variant를 모두 허용해도 상수배뿐이다.

## 5. 구현상 pruning

각 target과 bottom receipt mask에 대해 다음 prefix table을 미리 계산한다.

```cpp
prefix[q][r] = number of remaining target S/P tokens in column q
               whose target_layer <= r;
```

source row s의 transition에서 `next_consumed`를 만든 직후:

```cpp
bool has_eager = false;
for (int q = 0; q < 4; ++q) {
    if (next_consumed[q] == prefix[q][s + 1]) {
        has_eager = true;
        break;
    }
}
if (!has_eager) continue;
```

완전한 증명이 끝나면 이 pruning은 해를 제거하지 않는다. 상태 key 자체를 3-cursor + leader로 바꾸면 명시적인 O(L^4) 구현이 된다.

## 6. 현재 실측

### authoritative 5-layer Claw 40,171개

원본 결정론적 `claw_process`가 생성한 predecessor를 provenance Pin-Push simulator로 재생했다.

- target: 40,171
- source cut: 160,684
- eager lemma 위반: 0

### 작은 층 전체 predecessor 전수검사

Claw corpus만이 아니라, `{-,S,P,c}`의 모든 안정 predecessor 중 top row에 crystal이 있는 overflow 입력을 조사했다.

- L=2: 안정 predecessor 31,755개, 위반 0
- L=3: 안정 predecessor 5,503,119개, 위반 0

L=3은 전체 `4^(4L)=16,777,216` 구조를 전수검사했다.

### 무작위 고층 안정 predecessor

- L=4: 안정 표본 10,268개, 위반 0
- L=5: 안정 표본 23,170개, 위반 0

테스트는 증명이 아니지만, 기존 5층 정규형에만 우연히 맞는 성질은 아니라는 강한 근거다.

## 7. 증명 방향

`delta_q(s)>0`은 source cut 위의 noncrystal trajectory가 q열에서 result cut 아래로 내려왔음을 뜻한다.
네 열 모두 delta가 양수라고 가정하면 네 열 모두에 cut-crossing trajectory가 존재한다.

증명은 다음 separator 명제로 환원될 가능성이 높다.

> 폭 4 원통 strip에서 네 열 모두를 통과하는 downward noncrystal trajectories는, 안정 predecessor에서 overflow로 제거되는 crystal support component가 ground에서 해당 faller들까지 연결되는 모든 support derivation을 동시에 끊도록 배치될 수 없다.

직관적으로 네 열의 crossing trajectories가 원통을 가로지르는 separator를 만들며, 그 separator 아래의 support crystal과 overflow top crystal을 하나의 4-connected destroy component로 연결하려면 trajectory를 통과해야 한다. crystal과 noncrystal은 같은 cell을 점유할 수 없으므로 모순이다.

엄밀화해야 할 부분:

1. 서로 다른 source row에서 시작하는 trajectory들을 staircase separator로 정규화
2. singleton pin과 ordinary horizontal group을 동시에 처리
3. D 직접 파괴뿐 아니라 D 제거 후 unsupported crystal U가 생기는 경우 처리
4. support derivation과 crystal 4-connectivity의 관계를 정확히 분리

## 8. 더 낮은 복잡도의 가능성

- 고정된 하나의 열이 모든 source cut에서 eager라면 O(L^3)이나, 40,171 corpus에서는 eager leader가 바뀌는 사례가 있어 일반적으로는 성립하지 않는다.
- eager leader 변경 횟수가 O(1)이라는 더 강한 정리가 나오면 O(L^3) 또는 O(L^2) direct construction 가능성이 있다.
- 현재 확실히 노릴 수 있는 다음 목표는 O(L^4) lemma 완결과 exact solver pruning이다.

## 9. 현재 판정

- O(L^4) 알고리즘 아이디어: 구체적으로 발견됨
- 데이터/작은 층 전수검증: 통과
- 전층 수학적 증명: 아직 미완성
- 기존 solver에 넣을 코드 위치: `next_consumed` 계산 직후
