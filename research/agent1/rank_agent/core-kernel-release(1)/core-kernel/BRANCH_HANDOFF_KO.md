# `core-kernel` 브랜치 인계서

## 병합 목표

기존 프로젝트 UI/분류 코드는 그대로 두고, 새 TMAM 연구가 공유할 구조 코어를 추가합니다.

## 권장 커밋 단위

1. `core: add immutable CompactShape and row tables`
2. `core: add exact structural physics and operations`
3. `core: add reference oracle, adapters, and replay protocol`
4. `test: add exhaustive and high-cap differential audits`
5. `docs: add semantics, validation, performance, and merge contracts`

## 병합 시 충돌 예상

현재 브랜치는 기존 파일을 수정하지 않으므로 직접 충돌은 거의 없습니다. 통합 담당자가 선택할 사항은 패키지 위치뿐입니다.

### `src/` 레이아웃을 채택할 경우

이 디렉터리를 그대로 병합합니다.

### 기존 flat 레이아웃을 유지할 경우

`src/shapez2_core/`를 저장소 루트의 `shapez2_core/`로 옮기고 import만 유지합니다. 내부 상대 import이므로 패키지 자체 수정은 필요 없습니다.

## Downstream 준비 상태

- Corner/Half: 바로 `CompactShape`, `cut`, `canonical_with_transform` 사용 가능
- Generator: 바로 `crystal_generator`와 replay protocol 사용 가능
- Stack/PP: 바로 `stack`, `pin_push`, `support_positions`, `shatter_crystals` 사용 가능
- TMAM: `ForwardCall`을 proof certificate leaf로 사용 가능

## 필수 병합 게이트

```bash
python -m pip install -e .
PYTHONPATH=src pytest
PYTHONPATH=src python scripts/legacy_differential.py --cases 10000 --max-cap 20
```

세 번째 명령은 실제 원본 저장소 안에서만 실행 가능합니다. 실패하면 기존 프로젝트가 권위 semantics와 다른 입력을 최소 반례로 저장하고, 코어를 조용히 변경하지 말고 의미 결정 문서를 먼저 갱신하십시오.

## 보류 사항

- exact color/subtype provenance
- 기존 `Shape` 메서드의 core delegate화
- C++ extension
- binary cache file format versioning

이 항목들은 downstream 요구가 확정된 뒤 별도 브랜치에서 진행하는 것이 안전합니다.
