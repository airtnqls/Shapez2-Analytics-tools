# Core Kernel 물리 사양과 정당성

## 1. 의미 기준

구조 물리의 기준은 다음 두 구현을 대조해 고정했습니다.

- `cpcp1998/shapez2-solver`, `src/shape.cpp`, blob `0bc7a30b7ccf5de609eab3eeb67de05988647d9f`
- `airtnqls/Shapez2-Analytics-tools`, `shape.py`, blob `272a6fc9fde3ae0911a6997e21461c6cfff5bea8`

두 구현이 안정한 정상 operation input에서 동치인 최적화는 허용하지만, 의미가 모호할 때는 첫 번째 구현을 권위 기준으로 둡니다.

## 2. 상태 표현

폭은 항상 4입니다. 각 셀은:

```text
00 empty
01 ordinary
10 pin
11 crystal
```

따라서 한 층은 정확히 8비트이고, 아래층이 더 낮은 바이트입니다.

```text
bits = row[0] | row[1] << 8 | row[2] << 16 | ...
```

`CompactShape(bits, cap)`은 불변이며 `bits`의 모든 셀은 cap 아래에 있어야 합니다. 색과 일반도형 subtype은 물리에 영향을 주지 않으므로 저장하지 않습니다.

## 3. Gravity

### 3.1 지원의 최소 고정점

바닥의 모든 점유 셀을 시작으로 다음 규칙을 닫습니다.

1. 지원된 셀 바로 위의 점유 셀은 지원됨.
2. 같은 층에서 인접한 두 non-pin 셀 사이로 지원이 전달됨.
3. 지원된 crystal 바로 아래 crystal은 매달려 지원됨.

packed 구현은 이 유향 그래프를 BFS합니다. 각 셀은 처음 지원될 때 한 번만 큐에 들어가므로 폭 4에서 셀 수에 선형입니다.

### 3.2 Crystal 제거

지원되지 않은 crystal을 삭제합니다. Crystal 수평·수직 연결 자체가 지원을 전달하므로 한 crystal component 안의 지원 여부는 동일합니다. 따라서 모든 비지원 crystal을 개별로 지우는 것은 그 component를 shatter하는 것과 같습니다.

### 3.3 낙하

레이어 1부터 위로 한 번 순회합니다.

- pin은 singleton group입니다.
- 다른 비지원 non-crystal은 같은 층의 수평 ring component로 묶입니다.
- 그룹의 낙하 거리는 각 사용 열의 빈 거리 최솟값입니다.
- 낮은 레이어가 먼저 정착하므로 이후 그룹은 이미 정착한 결과를 봅니다.

packed 구현은 열마다 `settled_top[4]`만 유지합니다. 레이어 `l`을 처리하기 직전 이 값은 각 열에서 `l` 아래의 가장 높은 최종 점유층입니다. 따라서 그룹의 낙하 거리는:

```text
min(l - settled_top[q] - 1 for q in group_columns)
```

입니다. 그룹이 내려간 뒤 해당 열의 frontier를 갱신하고, 원래 레이어에 남은 셀을 frontier에 반영합니다.

### 3.4 단일 sweep의 안정성

지원된 셀은 이동하지 않습니다. 비지원 crystal은 낙하 전에 제거됩니다. 비지원 일반 그룹은 낮은 층부터 최종 물질 위에 내려앉거나 같은 그룹의 다른 열 때문에 anchored됩니다. Anchored group 안에서는 최종적으로 자연 착지한 구성원에서 수평 지원이 전달됩니다. 따라서 결과에 다시 Gravity를 적용해도 바뀌지 않습니다.

이 성질은 코드에서 idempotence 속성과 1·2층 전수검사로도 감사합니다.

## 4. 구조 연산

### Rotate

시계방향 한 번은 새 열 `q`에 이전 열 `q-1 mod 4`를 놓습니다.

### Mirror

권위 구현의 `q -> 3-q` reflection을 사용합니다. 기존 프로젝트의 다른 reflection 축도 회전과 합치면 같은 D4 orbit을 생성하므로 canonicalization 결과 집합은 같습니다.

### Cut

Vertical:

```text
east = columns 0,1
west = columns 2,3
boundary edges = (1,2), (3,0)
```

Horizontal:

```text
north = columns 3,0
south = columns 1,2
boundary edges = (0,1), (3,2)
```

경계를 가로지르던 crystal pair가 있으면 그 4-connected component를 양쪽에서 제거하고 각 half에 독립 Gravity를 적용합니다.

### Swap

두 입력을 같은 축으로 Cut한 뒤 반대 half를 교차 결합합니다. Half는 이미 안정하고 지원은 물질 추가에 대해 단조이므로 결합 뒤 추가 Gravity가 필요 없습니다.

### Stack

cap `L`의 bottom은 작업공간 `0..L-1`, top은 `L+1..2L`에 놓습니다. 사이의 `L`층은 비어 있습니다. 작업공간에 Gravity를 한 번 적용하고 아래 `L`층만 남깁니다.

`stack_compact_equivalent()`는 기존 프로젝트식 최적화입니다.

```text
top crystal 제거
→ top을 bottom의 trimmed height 바로 위에 배치
→ Gravity
→ cap truncation
```

안정 입력에서 권위 Stack과 일치하는지 별도 검사하지만, 증명 소비 전까지 public proof replay는 `stack()`을 사용합니다.

### Pin Push

1. 모든 기존 층을 한 층 올림.
2. 이전 바닥이 점유된 열에 바닥 pin 삽입.
3. cap을 넘은 old top을 삭제. 넘친 crystal이 연결된 살아남는 crystal component도 shatter.
4. Gravity.

### Crystal Generator

현재 global height 아래의 empty/pin을 crystal로 바꿉니다. 생성 후 그 직육면체 영역은 수직으로 꽉 차므로 별도 Gravity가 필요 없습니다.

## 5. 기존 프로젝트와 의도적으로 다른 경계 사례

### Empty Generator

권위 구현에서 empty shape의 height는 0이므로 Generator 결과도 empty입니다. 기존 프로젝트는 빈 객체에 한 empty layer를 추가한 뒤 crystal로 채울 수 있습니다. 실제 제작 연산 입력은 빈 shape가 아니므로 정상 domain에는 영향이 없지만, 코어는 권위 의미를 따릅니다.

### Unstable 외부 입력

게임 연산의 입력은 이전 연산 결과이므로 안정합니다. 기존 프로젝트의 일부 메서드는 외부 unstable 객체를 먼저 안정화하거나 특별처리합니다. 코어의 operation semantics는 권위 구현과 동일하게 안정 입력을 계약으로 삼으며, `apply_gravity()`는 별도로 어떤 raw 상태에도 사용할 수 있습니다.

### Color와 subtype

Painter 및 색 복원은 별도 provenance branch의 책임입니다. 이 커널의 `S`는 모든 ordinary subtype을 나타냅니다.

## 6. 복잡도

폭이 4로 고정된 명시적 `L`층 입력에 대해:

| 연산 | 시간 | 추가 공간 |
|---|---:|---:|
| parse/format | O(L) | O(L) |
| rotate/mirror/generator | O(L) | O(L) |
| support | O(L) | O(L) |
| gravity | O(L) | O(L) |
| cut/pin push | O(L) | O(L) |
| stack | O(L) | O(L) |

레이어 직렬화는 `int.to_bytes`/`int.from_bytes`로 일괄 처리하며, 낙하 거리에는 네 열 frontier만 사용합니다.

## 7. Packed 구현 정당성 요약

1. **표현 보존:** 한 셀의 2비트 값과 list reference의 셀 값이 일대일 대응합니다.
2. **지원 보존:** BFS edge가 권위 지원 규칙 세 가지와 정확히 일치하므로 같은 최소 고정점을 계산합니다.
3. **Shatter 보존:** crystal 4-connectivity neighbor가 동일합니다.
4. **낙하 보존:** bottom-up invariant에 의해 `settled_top`이 권위 구현의 아래쪽 occupancy scan과 같은 blocker를 반환합니다.
5. **연산 보존:** 각 연산은 같은 중간 배치, shatter seed, cap 절단 및 Gravity 순서를 사용합니다.

따라서 packed 결과는 독립 reference 결과와 같습니다. 기계 검사는 `reports/validation_exact.json`에 기록됩니다.
