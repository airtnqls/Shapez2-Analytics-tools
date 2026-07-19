# 예상 병합 충돌과 회피 원칙

## 파일 소유권

```text
tmam/**                         tmam-integration 전용
shape.py / compact kernel       core-kernel 전용
corner / half files             corner-half 전용
generator files                 generator 전용
stack / pinpush files           stack-pp 전용
shape_classifier.py             최종 전환 시 integration 담당
ProcessTree GUI 파일             최종 전환 시 integration 담당
```

## 흔한 충돌

### 서로 다른 Shape key

모든 plugin은 `backend.key(backend.canonicalize(shape))`만 memo key로 사용한다. 직접 `repr`, hash, rotation canonicalization을 재정의하지 않는다.

### 서로 다른 operation 이름

`tmam.enums.Operation`만 사용한다. 문자열 `PP`, `pinpush`, `Pin Push`를 provider 내부 ID로 혼용하지 않는다.

### 완전성 오해

provider는 구현이 빠르다는 이유로 `Coverage.complete`를 반환하지 않는다. 증명 범위가 정확히 일치해야 한다.

### 분류가 solver를 호출하는 순환

분류기는 `ShapeFacts`만 읽는다. classifier가 tracer를 다시 호출하거나 tracer가 classifier를 호출하지 않는다.

### 비용이 proof correctness를 변경

비용 모델은 후보 선택에만 사용한다. 후보 생성·불가능 판정에서 비용 cut-off를 사용하면 completeness가 깨진다.
