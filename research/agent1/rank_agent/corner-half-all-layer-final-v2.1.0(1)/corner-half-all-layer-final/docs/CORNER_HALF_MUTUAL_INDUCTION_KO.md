# Corner constructor와 Half constructor의 비순환 상호귀납

## 1. 감사에서 발견한 문서 공백

기존 raw proof 구현은 실제로 사이클 없이 종료했지만, 문서가 다음 의존성을
충분히 분리하지 않았다.

```text
Corner helper half -> Half exchange
Half exchange       -> Corner constructors
```

이를 단순히 서로 참조하면 논리적 순환이다. 실제 구현과 증명은 다음 단계로
분리되어야 한다.

---

## 2. 단계화된 증명

### 단계 A — 직접 prefab

raw `SSSS`에서 다음을 Half 정리 없이 만든다.

- S-only shape
- S/P-only stable shape
- 한 번의 Generator로 가능한 solid S/c shape
- 단일 pin과 solid pin tower
- solid crystal trigger

모든 proof는 실제 Rotate/Cut/Swap/Stack/Generator/PinPush DAG다.

### 단계 B — Solid-Half exchange

두 열에 gap `-`가 없는 직접 prefab column만 사용하는 stable half는 각
column의 직접 canonical proof를 교환하여 만든다. 이 단계는 일반 Corner
정리나 일반 Half 정리를 사용하지 않는다.

### 단계 C — Natural Corner

C1–C6 natural constructor가 설치하는 비자명한 helper half는 전부 단계 B의
solid-half다.

코드 의존 그래프를 cap7 모든 natural Corner 3,212개에서 감사한 결과,
cache에 의존하지 않고 모든 operand를 독립 분류한 최종 감사에서 일반 Half
helper 경로를 사용하는 natural root는 1,139개였고, 총 dependency edge는
2,438개였다. 서로 다른 child column은 20종뿐이며 모두 gap 없는 solid tower
또는 `S* c S*` solid column이다. 모든 edge에서 child의 gap 수가 parent보다
엄격히 작고 dependency SCC는 0개였다.

이는 코드 표본만의 우연이 아니다. C1/C2 operand는 단층, C3/C6은 unary,
C4 helper는 solid tower + 한 위치 crystal인 solid tower, C5 helper는 solid
S/P tower다. 따라서 natural constructor는 general Half theorem에 의존하지
않는다.

### 단계 D — Natural-Half exchange

단계 C에서 모든 natural Corner canonical constructor가 확보되었으므로,
두 natural Corner 열의 안정한 pair는 exchange construction으로 만든다.

### 단계 E — Event Corner

C7 predecessor의 `(B,C)`와 `(D,A)`는 compiler 불변식상 모두 안정한
natural-half다. 단계 D로 둘을 만들고 Swap/Rotate한 뒤 Pin Push한다.
따라서 event target 자신이나 event Corner child를 재귀 호출하지 않는다.

### 단계 F — General Half

단계 C와 E로 모든 Corner constructor가 확보되었다. 이제 임의의 안정한
Corner pair `(u,v)`에 대해 두 canonical Corner proof를 교환하여 일반 Half를
만든다.

이 순서는:

```text
Direct prefab
 -> Solid Half
 -> Natural Corner
 -> Natural Half
 -> Event Corner
 -> General Half
```

이며 뒤 단계가 앞 단계만 참조하므로 well-founded하다.

---

## 3. 기계 감사

`reports/natural_corner_dependency_audit.json`은 cap7 natural Corner raw proof
호출 그래프를 기록한다.

```text
natural roots          3,212
half-dependent roots    1,139
dependency edges        2,438
unique child columns       20
strongly connected components with cycle 0
all children solid and all edges strictly decrease parent gap count
maximum dependency depth 1
```

또한 complete raw proof forest를 다시 독립 재생했다.

```text
cap7 Corner roots  4,320   replay failure 0
cap4 Half roots   16,193   replay failure 0
sole raw leaf      SSSS
```

기계 감사는 단계화된 수학 증명의 구현 오류를 찾기 위한 것이며, 종료성의
근거 자체는 위 A→F 순서다.
