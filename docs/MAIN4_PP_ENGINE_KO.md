# Main4 PP Engine Port

## 이식 범위

베이스는 `Shapez2-TMAM-Web-Studio-2.1.0-Focused-UI`다. 다음 PP 관련 요소만 Main4 패키지에서 옮겼다.

- `lib/raw-pinpush-rank0.ts`
- `lib/half-dfa.ts`
- receipt-chain 압축 및 Rank0 solver 연결
- `PinPushWitness`와 Proof graph replay
- Rank0/고층/차분 테스트 fixture

Focused UI의 컴포넌트 구조, Worker 모드 분리, Half proof forest, Claw/Hybrid 자료, DAG/Tree 표시 방식은 유지했다.

## 판정 route

- `rank0-pinpush-frontier`: Rank0 core에서 직접 predecessor를 복원
- `pp-receipt-chain`: receipt chain을 제거한 core에서 predecessor를 복원한 뒤 Pin Push들을 다시 적용
- `pp-closure-exhausted`: 모든 PP core 후보를 소진

## 결과 모델

별도 완료 전제 플래그와 전제 문자열은 제거했다. 정상 완료 결과는 `coverage: complete`로 기록되고, 음성 certificate verifier는 `passed`가 된다.
