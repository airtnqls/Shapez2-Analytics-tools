# Raw Pin Push Frontier / Eager-Column L4 체크포인트

## 결론

일반 PP(Pin Push rank/family) 연구에는 **Claw 전용 L3 solver만으로는 부족**하며,
Claw 조건을 제거한 raw Pin Push frontier가 반드시 필요하다.

권장 구조는 다음과 같다.

```text
plain inverse O(L)
    -> certified Claw specialized L3
    -> eager-column L4 (실험적 일반 PP 가속)
    -> raw frontier (완전성 기준점)
```

## 세 모드의 정확한 역할

### 1. raw mode

- Pin Push 물리 관계만 표현한다.
- Swapper/Stacker/Claw/rank 조건을 포함하지 않는다.
- eager pruning과 fixed-two-eager pruning을 모두 끈다.
- `UNSAT` 또는 family fixed-point의 완전성 판단은 이 모드에 의존해야 한다.

### 2. eager-L4 mode

- 매 source cut에서 적어도 한 열이 eager라는 후보 정리를 사용한다.
- 네 cursor 중 하나를 목표 prefix에서 복원하여 상태 수를 O(L^5)에서 O(L^4)로 줄인다.
- 작은 층 전체검사와 일반 안정 overflow 표본에서 강하게 검증됐지만,
  전층 수학 증명은 아직 미완성이다.
- 따라서 현재는 feature flag / 반례 탐색 / 양성 가속으로 사용한다.
- 이 모드의 `UNSAT`만으로 최종 음성 판정을 내리면 안 된다.

### 3. claw-L3 mode

- 순수 Claw의 Swapper/Stacker 배타성을 이용해 fixed eager pair를 사용한다.
- 정확한 Claw certificate가 있을 때만 안전하다.
- 일반 PP target에는 적용하면 안 된다.

## 일반 PP에서 raw frontier가 필요한 이유

일반 PP target은 Stackable 또는 Swappable이어도 유효하다. 따라서 세 열 또는 네 열에서
독립 낙하가 생기는 전상을 허용해야 하며, Claw L3의 `active columns <= 2` 정리를 적용할 수 없다.

raw relation은 다음 API의 기반이 되어야 한다.

```python
pinpush_preimages(target, predecessor_family)
```

frontier 상태와 family automaton을 product하여:

```text
RawPinPushState x FamilyState
```

를 구성한다. Claw, Claw-Hybrid, PP rank는 이 raw relation에 family 조건을 곱한 특수 사례다.

## ZIP 구성

- `docs/EAGER_COLUMN_L4_RESEARCH_KO.md`
  - L4 정리 후보, 상태 수 계산, 증명 공백
- `patches/eager_prune_patch.cpp`
  - 기존 raw frontier에 삽입할 pruning sketch
- `validation/eager_exhaustive_l3.cpp`
  - L=3 전체 구조 검사기
- `validation/check_eager_column.py`
  - 40,171 predecessor provenance 검사기
- `validation/provenance_sim.py`
  - 독립 Pin Push provenance simulator
- `comparison_claw_l3/`
  - L3 Claw 전용 정리와 패치. raw PP에 직접 적용하지 말 것
- `data/all40171clawsnohybrid.txt`
  - 5층 Claw 회귀 데이터

## 중요한 누락

이 체크포인트에는 **이전 세션에서 생성했던 전체 raw frontier 엔진 본체가 포함되어 있지 않다.**
현재 활성 런타임에 그 파일이 남아 있지 않아, 여기에는 L4 연구 문서·패치·검사기만 보존했다.

따라서 이 ZIP은 drop-in solver가 아니라:

1. raw frontier를 보존해야 하는 이유
2. L4 pruning을 적용할 정확한 위치
3. 일반 PP와 Claw L3의 경계
4. 독립 검증 코드

를 담은 연구 체크포인트다.

전체 raw frontier 엔진 파일을 다시 사용할 때 `patches/eager_prune_patch.cpp`를 feature flag로
연결하되, 기본값은 raw mode로 두는 것이 안전하다.

## 권장 옵션

```cpp
enum class PinPushSearchMode {
    RawComplete,
    EagerL4Experimental,
    CertifiedClawL3,
};
```

- `RawComplete`: 최종 UNSAT 및 family fixed-point 증명
- `EagerL4Experimental`: 반례 탐색과 속도 비교
- `CertifiedClawL3`: Claw certificate가 이미 있는 입력의 빠른 witness 생성
