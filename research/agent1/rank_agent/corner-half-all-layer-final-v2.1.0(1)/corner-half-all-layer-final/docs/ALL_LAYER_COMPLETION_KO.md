# Corner–Half 전층 완료 정리

## 1. 범위

구조 알파벳은 다음 네 기호다.

```text
-  빈칸
S  임의의 일반 조각
P  핀
c  크리스탈
```

층 제한 `L`은 임의의 유한한 양의 정수다. 색상과 `C/R/S/W` subtype은
구조 제작 가능성에 영향을 주지 않으므로 상위 provenance 단계에서 복원한다.

이 브랜치는 다음 다섯 문제를 해결한다.

1. 전층 Corner membership 및 실제 제작 constructor
2. 전층 Half membership 및 실제 제작 constructor
3. Half family의 soundness/completeness
4. Cut의 canonical inverse와 Swap의 exact existence inverse
5. Half family의 최소 deterministic symbolic representation

## 2. Corner 정리

한 column `w`를 아래에서 위로 읽고 맨 위 `-`를 제거한다.

```text
Corner(w)
iff
w가 R1..R6 금지 패턴을 모두 피한다.
```

금지 패턴은 `corner_dfa.py`의 `FORBIDDEN_RULES`에 고정되어 있다. 결합 NFA를
결정화·최소화한 판정기는 19상태이며 `Theta(L)` 시간과 상수 작업 상태를 쓴다.

완전성 방향은 정규식만으로 주장하지 않는다. accepted column을 zone,
internal segment, top으로 분해하고 C1–C7 schedule을 만든다. 각 C-rule은 실제
Stack/Generator/Cut/Swap/PinPush 연산으로 lowering된다. C7은 임의 유한 duty
목록을 동시에 실행하는 overflow predecessor를 좌표식으로 생성한다.

모든 helper는 raw input `SSSS`에서 제작되며 raw proof DAG의 유일한 leaf도
`SSSS`다. Natural helper와 Event helper의 의존 순서는 다음과 같이
well-founded하다.

```text
Direct prefab
 -> Solid Half
 -> Natural Corner
 -> Natural Half
 -> Event Corner
 -> General Half
```

따라서 모든 accepted `w`에 대해 유한한 실제 제작 proof가 존재하고, rejected
`w`에는 최초 위반 rule/position certificate가 존재한다.

## 3. Half 필요충분 정리

oriented east half를 인접한 두 column `H=(u,v)`라 하자.

```text
BuildableHalf(u,v)
iff
Corner(u) and Corner(v) and Stable(u,v).
```

### 필요성

제작 가능한 Half는 operation output이므로 안정하다. 또한 그 두 column은
실제로 제작 가능한 shape에 나타나는 column이므로 Corner 정리에 속한다.

### 충분성

`T=S^L`인 solid normal tower를 잡는다. Corner constructor로 canonical fixture
`C(u)=(u,T,T,T)`와 `C(v)=(v,T,T,T)`를 만든다.

1. `C(v)`를 잘라 east fixture `(v,T)`를 만든다.
2. `C(u)`를 회전·절단하여 west fixture `(T,u)`를 만든다.
3. 두 fixture를 Swap하여 `(v,T,T,u)`를 만든다.
4. 회전하여 `(u,v,T,T)`를 만든다.
5. east를 Cut한다.

버리는 경계 쪽은 normal tower라 target crystal과 cut-adjacent crystal pair를
만들지 않는다. 남은 `(u,v)`는 가정상 안정하므로 Cut 뒤 gravity에도 변하지
않는다. 따라서 결과는 정확히 H다.

이 constructor는 cpcp식 concrete HalfSet의 Ops 1–6 전층 나열을 필요로 하지
않는다. Ops 1–6이 생성하는 모든 Half는 필요성으로 위 조건에 들어가고, 위
조건의 모든 Half는 직접 constructor로 제작되므로 두 family는 같다.

## 4. Cut/Swap inverse

### Cut

모든 `H in HalfFamily`에 대해 `(H | T,T)`인 buildable full parent를 만든다.
그 parent의 east Cutter 결과는 H다. 버리는 쪽의 의미 없는 내용은 solid tower로
정규화하므로 이 API는 모든 syntactic garbage parent를 열거하지 않고,
**Cut 전상 존재성에 대해 완전한 canonical parent 하나**를 반환한다.

### Swap

full target X가 Swappable일 필요충분조건은 두 cutter axis 중 하나에서 두
geometric half가 모두 exact HalfFamily에 속하는 것이다.

```text
Swappable(X)
iff
exists axis in {0,1}:
    EastHalf(rotate(X,axis)) in HalfFamily
    and WestHalf(rotate(X,axis)) in HalfFamily.
```

필요성은 Swapper가 두 입력을 잘라 kept halves를 합친다는 정의에서 따르고,
충분성은 두 Half constructor 결과를 각각 한쪽 operand로 넣어 직접 합치면 된다.
`swap_inverse_candidates()`는 180도 중복을 제거한 두 axis 후보를 모두 낸다.

## 5. Symbolic closure와 최소 상태

Half 한 층은 두 셀의 쌍이므로 16문자 알파벳을 이룬다. Half 언어는 다음 세
정규언어의 교집합이다.

```text
Corner(left) x Corner(right) x JointStability
```

- 각 Corner: 19상태
- 공동 안정성: 6상태 최소 DFA
- 원시 product 상한: `19*19*6 = 2166`
- 시작 상태에서 reachable: 552
- Hopcroft 최소화: **210상태**

210개 상태는 전부 reachable하다. 서로 다른 모든 상태쌍
`210*209/2 = 21,945`개에는 수용 여부를 분리하는 suffix가 있다. 따라서
Myhill–Nerode 정리에 의해 oriented normalized Half 언어의 deterministic
상태 수 210은 최소다.

판정 시간은 `Theta(L)`, 판정 작업 메모리는 `Theta(1)`이다. 후보 DB나 고정층
pattern table은 필요하지 않는다.

## 6. 전층성

전층 결론은 cap 1–7의 수치 귀납이 아니다.

- Corner C1–C7 rule schema는 층 인덱스를 상대좌표로 사용한다.
- Half 충분성 construction은 임의 L의 tower `S^L`에 대해 동일하다.
- DFA 전이는 입력 층마다 동일한 유한 table을 적용한다.
- 모든 loop와 proof recursion에는 유한 schedule 또는 위의 단계 순서가 있다.

따라서 모든 유한 L에서 판정·constructor·inverse가 종료하고 정리가 성립한다.
고정층 exact set과 고층 replay는 이 증명의 구현 오류를 찾는 감사 자료다.

## 7. 최종 감사

최종 수락 결과는 `reports/FINAL_ACCEPTANCE.json`과
`reports/FINAL_FULL_ACCEPTANCE.log`에 있다.

핵심 결과:

```text
Corner regex/DFA/semantic                   349,525 cases, mismatch 0
Corner accepted constructor                 104,191 cases, failure 0
Corner cap7 raw proof forest                  4,320 roots, failure 0
Half cpcp exact bitset cap1..6                    FP 0 / FN 0
Half cap4 constructor 전체                    16,193, failure 0
Half minimality state pairs                   21,945/21,945 distinguished
Cutter inverse cap3 전체                       1,796, failure 0
Swapper existence cap2 full target            65,536, mismatch 0
189-layer event Corner raw proof                 replay OK
```

이는 Lean/Coq proof kernel 결과는 아니다. 자족적 수학 증명, 최소 automaton
certificate, raw-input operation DAG, 독립 forward replay 및 exact fixed-cap
oracle를 결합한 결과다.
