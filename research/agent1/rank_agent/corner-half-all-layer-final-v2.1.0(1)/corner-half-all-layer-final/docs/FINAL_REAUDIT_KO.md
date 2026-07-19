# Corner/Half 전층 최종 재감사

이 문서는 기존 체크포인트에 적힌 수치를 그대로 복사한 것이 아니라, 최종
릴리스에서 다시 실행한 독립 감사와 수학적 완료 범위를 기록한다.

## 1. 최종 정리

임의의 유한 cap `L`에 대해 다음이 성립한다.

```text
Corner(w)
<=> w가 여섯 금지 column 패턴을 모두 피한다.

BuildableHalf(u,v)
<=> Corner(u) and Corner(v) and Stable(u,v).

Swappable(X)
<=> 두 cutter axis 중 하나에서 X의 두 geometric half가 모두 HalfFamily다.
```

각 `True` 판정은 raw input `SSSS`만을 잎으로 갖는 실제 operation DAG를
선택적으로 생성한다. 사용되는 내부 연산은 Rotate, Cut, Swap, Stack,
Generator, PinPush뿐이다.

## 2. 왜 Half 충분성이 일반 역열거 없이 성립하는가

`u`와 `v`의 Corner constructor가 각각 canonical full fixture
`(u,T,T,T)`, `(v,T,T,T)`를 만든다고 하자. `T=S^L`이다.

1. `(v,T,T,T)`를 cut하여 east fixture `(v,T)`를 만든다.
2. `(u,T,T,T)`를 rotate/cut/rotate하여 west fixture `(T,u)`를 만든다.
3. Swap으로 `(v,T,T,u)`를 만든다.
4. 회전하여 `(u,v,T,T)`를 만든다.
5. Cut east를 수행한다. discarded side는 normal tower이므로 target crystal을
   shatter하지 않으며, `(u,v)`는 가정상 안정하므로 gravity 후에도 동일하다.

따라서 두 column과 안정성만으로 직접 constructor가 존재한다. cpcp의 concrete
Half Ops 1–6을 전층에서 미리 나열할 필요가 없다.

## 3. 실제 재실행 결과

- Corner regex/DFA/semantic, 길이 0..9: 349,525개, 불일치 0
- Corner compact constructor, 길이 0..10의 accepted 104,191개: 실패 0
- C7 생성 event column, 최대 200층·11 duty: 10,000개, 실패 0
- Corner raw proof forest cap7: 4,320 root, 유일 raw leaf 1종, replay 실패 0
- 189층 event Corner raw proof: 4,991 unique node, replay 실패 0
- Half constructor cap4 전체: 16,193개, 실패 0
- Half raw replay cap1..3 전체: 1,993개, 실패 0
- cpcp-style exact Half bitset cap1..6: FP 0, FN 0
- Half DFA normalized word 높이 0..5: 1,048,576개, semantic mismatch 0
- 210상태 DFA: 210/210 reachable, 21,945/21,945 상태쌍 구별 가능
- Cutter inverse cap3 전체 Half: 1,796개 raw proof forest replay 실패 0
- cap2 full target 65,536개: canonical Swap existence/replay mismatch 0
- cap2 Swappable target: 35,017개, distinct accepted axis 65,522개
- raw Swap proof 2,000-target 표본: shared proof forest replay 실패 0

## 4. 최소 상태

- Corner language: 19-state minimal DFA
- 두 열 공동 안정성: 6-state minimal DFA
- reachable raw product: 552 states
- oriented normalized Half language: **210-state minimal DFA**

최소성은 Hopcroft 반환값만 믿지 않는다. 모든 상태가 reachable하고, 서로 다른
모든 상태쌍에 대해 수용 여부를 분리하는 suffix가 존재함을 reverse pair BFS로
검사한다.

## 5. 완료 범위와 제외 범위

완료:

- 구조 alphabet `- / S / P / c`의 전층 membership
- Corner와 Half의 raw-input structural constructor
- canonical Cut/Swap inverse existence와 witness
- Half의 최소 deterministic symbolic recognizer

별도 브랜치:

- 색상·C/R/S/W subtype provenance 및 Painter 배치
- 전체 TMAM의 Stack/PP rank closure
- 인게임 blueprint 회로화

색상과 normal subtype은 구조 buildability에 영향을 주지 않으므로, 이 분리는
Corner/Half 정리의 soundness/completeness를 약화하지 않는다.
