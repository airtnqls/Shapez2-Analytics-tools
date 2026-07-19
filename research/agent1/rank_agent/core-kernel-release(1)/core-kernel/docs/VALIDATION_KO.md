# 검증 보고서 요약

## 빠른 테스트

```text
15 passed
```

검사 항목:

- 구조/정확 코드 parse round-trip
- cap 명시성
- 회전 4회 항등, mirror involution, canonical orbit
- Gravity idempotence
- 모든 forward operation의 안정성
- protocol replay
- legacy-like adapter round-trip

## 독립 reference 차등감사

`reports/validation_exact.json`:

```text
Support fixed point와 Gravity 전체 raw 상태
  cap 1:      256
  cap 2:   65,536
  합계:    65,792
  불일치:       0

2층 unary 전체 raw 상태
  상태:     65,536
  연산: rotate1, rotate2, mirror, generator,
        pin_push, vertical cut, horizontal cut
  불일치:        0

Binary 입력
  cap 1 전체 ordered pair: 65,536쌍
  cap 1..12 안정 무작위:   5,000쌍
  cap 13..40 안정 무작위:     50쌍
  Stack/양방향 Swap 불일치: 0
```

독립 reference는 packed helper를 재사용하지 않고 list와 권위 C++ 순서를 직접 구현합니다.

## 고층 속성감사

`reports/validation_high_caps.json`:

```text
cap 41..512 무작위: 1,000쌍
Gravity idempotence 실패: 0
Pin Push 안정성 실패: 0
회전/반사 군 법칙 실패: 0
권위 Stack vs 프로젝트식 compact Stack 실패: 0
```

## 사용자 데이터

`reports/user_corpora.json`:

| 코퍼스 | parse | structural round-trip | stable |
|---|---:|---:|---:|
| `40171.txt` 첫 40,171줄 | 40,171 | 40,171 | 39,802 |
| `all40171clawsnohybrid.txt` | 40,171 | 40,171 | 40,171 |
| 5층 Claw-Hybrid 샘플 | 367 | 367 | 367 |

`40171.txt`의 일부 줄은 완성 target이 아니라 분할/보조 입력이므로 개별적으로 불안정할 수 있습니다. 동일 데이터에서 재구성된 Claw target 코퍼스는 전부 안정합니다.

## 아직 남은 감사

현재 실행 컨테이너에는 원본 저장소 전체와 PyQt runtime이 없으므로 `scripts/legacy_differential.py`는 여기서 실행하지 못했습니다. 이 스크립트는 실제 저장소 안에서 다음을 직접 비교합니다.

- `Shape.apply_physics`
- rotate
- Pin Push
- Generator
- Stack
- 양방향 half cutter
- Swap

병합 전 필수 게이트로 사용하십시오.
