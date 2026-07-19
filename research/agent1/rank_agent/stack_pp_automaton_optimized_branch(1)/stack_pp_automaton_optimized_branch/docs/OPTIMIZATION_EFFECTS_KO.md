# 최적화별 효과표

수치는 `reports/stack_automaton_benchmark.json`과 `reports/state_explosion_analysis.json`에서 재현 가능하다.

| 최적화 | 전 | 후 | 감소 |
|---|---:|---:|---:|
| Support concrete residual state | 2,011 | 131 | 93.49% |
| Previous-row context 종류 | 256 | 16 | 93.75% |
| L3 state, compact no-subsumption 대비 | 8,111 | 2,082 | 74.33% |
| Max subset size | 25 | 5 | 80.00% |
| Complete reachable DFA | 2,536 | 962 | 62.07% |
| Global row alphabet class | 256 | 200 | 21.88% |
| Raw dense transition 대비 sparse action group | 649,472 | 45,995 | 92.92% |
| Synthetic family quotient L3 cumulative state | 54,640 | 24,386 | 55.37% |

## 전체 reachable state

Universal 1-state bottom family, 전체 256행:

```text
legacy:       L0 1, L1 256, L2 4,019, L3 진단 300초 내 미완료
optimized:    L0 1, L1 81, L2 942, L3 2,082, L4 2,497, L5 2,527
complete:     live 2,536
minimized:    962 (dead block 포함)
```

Legacy L3 진단 중단은 불가능 판정이 아니며 benchmark status로만 기록한다.

## single-target median

600개/층 warm-cache structural target:

| L | Legacy membership | Optimized lazy | Complete minimized | Witness reconstruction |
|---:|---:|---:|---:|---:|
| 1 | 1.542 us | 0.621 us | 0.260 us | 8.723 us |
| 2 | 41.312 us | 18.308 us | 0.651 us | 16.174 us |
| 3 | 74.232 us | 32.429 us | 0.972 us | 23.285 us |
| 4 | 114.192 us | 45.068 us | 1.342 us | 31.687 us |
| 5 | 158.790 us | 56.955 us | 1.643 us | 39.270 us |

Complete minimized membership는 parent history를 저장하지 않는다. witness가 필요한 target에 대해서만 source lazy automaton이 경로를 재구성한다.

## 메모리

| 표현 | automaton-owned memory |
|---|---:|
| Optimized L5, build cache 포함 | 32,402,260 B |
| Optimized L5, build cache 해제 | 11,036,844 B |
| Complete minimized table | 3,488,257 B |

Python process 최대 RSS에는 interpreter, allocator arena, import된 legacy 모듈과 shared table이 포함되므로 automaton-owned size와 다르다. 두 값은 benchmark JSON에 함께 기록했다.
