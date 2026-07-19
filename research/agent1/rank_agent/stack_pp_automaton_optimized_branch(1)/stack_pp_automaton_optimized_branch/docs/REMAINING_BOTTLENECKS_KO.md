# 남은 병목과 연구 경계

## 1. 의미 있는 bottom-family state

Universal family는 상태 1개라 complete minimized Stack DFA가 962상태로 닫혔다. 실제 Half family, StackClosure(Half), PP-rank family는 residual state가 더 많다.

Family-state quotient hook이 큰 효과를 보였지만, 잘못된 quotient는 completeness를 파괴한다. `corner-half`는 가능한 한 최소화된 exact DFA와 residual inclusion certificate를 제공해야 한다.

## 2. powerset determinization의 이론적 최악

Antichain은 실제 product subset을 크게 줄이지만 NFA determinization의 최악 지수성을 제거했다는 정리는 아니다. 서로 포함되지 않는 family residual이 많이 생기면 subset 수는 다시 증가할 수 있다.

따라서 target 한 개를 판정할 때는 full DFA를 만들지 말고 lazy on-demand membership을 사용한다.

## 3. nested Stack closure

`StackClosure(F)`가 finite이면 다음 product에 재사용할 수 있다. 그러나 rank마다 complete automaton을 전부 determinize/minimize하는 것이 항상 실용적이라는 결과는 아직 없다.

## 4. PP symbolic image

이번 최적화는 Stack closure representation을 안정화했다. 다음은 여전히 열려 있다.

- `PinPush(F)`의 작은 exact symbolic image
- same-batch essential basis의 symbolic cleanup
- rank iteration의 fixed point 또는 반복 정규형
- negative/fixed-point certificate

따라서 일반 PP rank가 전층에서 완성됐다고 주장하지 않는다.

## 5. Witness/materialization 비용

Exists-only compiled table은 매우 작지만, 실제 proof tree에는 ownership path, bottom witness, top piece witness, forward replay가 필요하다. 이는 출력 크기에 비례하며 제거할 수 없다.

## 6. 실제 core/half 통합

현재 구조 row relation은 검증됐지만 최종 병합 후 반드시:

- CompactShape row reader
- exact Stack materializer
- Half family automaton
- top piece constructor
- forward Stack replay

를 연결해 fixed-cap cpcp oracle 및 기존 Shape.py와 다시 차등검증해야 한다.
