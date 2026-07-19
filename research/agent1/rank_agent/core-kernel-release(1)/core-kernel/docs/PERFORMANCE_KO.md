# 성능 보고서

`reports/benchmark.json`은 packed kernel과 의도적으로 단순한 독립 reference를 같은 입력에서 비교합니다. 절대 시간은 환경 의존적이며, speedup은 아키텍처 선택을 위한 참고치입니다.

중앙값 요약:

| cap | Gravity | Pin Push | Stack | Cut |
|---:|---:|---:|---:|---:|
| 5 | 약 1.4× | 약 1.1× | 약 1.4× | 약 1.2× |
| 20 | 약 1.7× | 약 1.6× | 약 1.6× | 약 1.6× |
| 50 | 약 2.4× | 약 2.9× | 약 2.6× | 약 1.9× |
| 100 | 약 2.6× | 약 3.1× | 약 3.2× | 약 2.2× |
| 200 | 약 3.1× | 약 4.0× | 약 4.8× | 약 2.4× |

주요 최적화:

- immutable two-bit cells
- one byte per layer
- 256개 row lookup table
- support BFS에서 셀당 최대 한 번 enqueue
- 낙하 거리용 `settled_top[4]` frontier
- `int.to_bytes` / `int.from_bytes` 일괄 직렬화
- 연산 중 색상/subtype 객체 생성 없음

현재 코어는 Python 구현입니다. TMAM 상태 수가 커진 뒤에도 이 부분이 병목이면 같은 byte/cell ABI를 유지한 C++/Rust extension을 추가할 수 있습니다. 다른 브랜치 API는 바뀌지 않아야 합니다.

## 100,000층 scaling

`reports/scaling.json`의 full-`S` 반복 family 결과:

| cap | Gravity | Rotate | Pin Push | Stack |
|---:|---:|---:|---:|---:|
| 1,000 | 0.004 s | 0.00009 s | 0.004 s | 0.007 s |
| 10,000 | 0.042 s | 0.00095 s | 0.048 s | 0.099 s |
| 100,000 | 0.450 s | 0.012 s | 0.454 s | 0.864 s |

이는 하나의 규칙적인 family에 대한 scaling 관측이며 전체 입력의 최악시간 측정은 아닙니다. 다만 cap을 고정 폭의 레이어 stream으로 처리하며 구체 도형 공간을 열거하지 않는다는 점을 확인합니다.
