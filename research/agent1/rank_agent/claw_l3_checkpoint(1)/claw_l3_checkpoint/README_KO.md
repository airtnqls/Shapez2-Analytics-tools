# Claw O(L³) 연구 체크포인트

핵심 문서는 `CLAW_L3_THREE_FALL_PROOF_KO.md`이다.

## 현재 결론

- stable structural Stacker factorization을 Claw 배제 조건으로 쓰는 프로젝트 계약에서는 fixed-two-eager `O(L³)` 축약의 수학적 증명이 닫혔다.
- 원재료부터의 완전 TMAM 의미에서 Stacker 두 factor가 모두 craftable이어야 한다면 bottom factor의 일반 craftability는 별도 과제다.
- 따라서 패치는 프로젝트 분류 계약에서는 exact branch로, 더 강한 TMAM 계약에서는 O(L⁴) fallback을 유지한 guarded branch로 사용하는 것이 안전하다.

## 실행

C++ 검증기 예시:

```bash
g++ -O3 -std=c++20 check_half_top_payload_mechanism_L7.cpp -o check_half
./check_half
```
