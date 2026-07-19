# 집중형 UI 2.1 재구축 기록

## 해결 대상으로 삼은 다섯 문제

1. 제작 과정이 실제 공정에 비해 지나치게 축약됨
2. 웹 도형 시각화가 레거시 GUI와 다름
3. DAG와 Tree가 같은 화면처럼 보임
4. 한국어가 일부 화면에만 적용됨
5. 빠른 판정과 상세 분석이 같은 계산 경로를 사용함

추가 요구로 기본 화면의 정보량을 줄이고 고급 정보는 요청할 때만 열도록 변경했다.

## 정보 구조

기본 화면은 좌측 입력과 중앙 도형 미리보기만 사용한다. 우측 Inspector와 하단 로그를 상시 노출하지 않는다.

```text
상단: 도형 / 제작 과정 / 도구
좌측: 코드, 최대 층, 세 실행 버튼, 접힌 직접 편집기
중앙: 큰 도형 미리보기와 한 줄 결과
오버레이: 상세 분석, 선택 공정, 기록, 설정
고급 모드: 연구자 진단
```

연산 실험, 일괄 분석과 비교는 `도구` 메뉴에 묶어 기본 화면의 선택지를 줄였다.

## 실제 모드 경계

Worker message의 `mode`에 따라 데이터 로딩과 계산 경로를 나눈다.

```text
fast  : normalize → small target indexes → verdict
 type : normalize → full witness tables → classification
proof : normalize → full witness tables → classification → Half proof forest → graph
```

`fast` 결과에는 Proof가 존재할 수 없으며, `type`도 Proof를 생성하지 않는다. 해당 계약은 smoke test와 release audit에서 검사한다.

## 세부 제작 과정 복원

이전 웹판은 Claw/Hybrid 표의 최종 관계만 그려 중간 과정을 생략했다. 2.1은 다음을 추가한다.

- 2,760개 Half root
- 21,139개 고유 Half proof node
- primitive `SSSS`까지의 정확한 operation backpointer
- Rotate/Cut/Swap/Stack/Generate/Pin Push 연산 노드
- Cut/Swap의 사용하지 않은 두 번째 output ghost
- 회전된 Claw bottom lookup
- forward replay

인증 표에 세부 constructor가 없는 경우에는 완전 전개를 가장하지 않고 `CERTIFIED_MACRO`와 omission reason을 표시한다.

## DAG와 Tree

DAG는 graph node ID를 공유한다. Tree는 root부터 edge 사용 위치마다 node를 복제한다. 따라서 공유가 있는 공정에서는 node 수가 달라진다.

UI 문제 사례:

```text
target                         --PP:--Pc:SSSS:-SS-:cS-S
DAG 고유 연산                  181
Tree 연산 사용                 2,144
공유 node                      86
graph nodes / edges            429 / 506
primitive complete             true
replay                         passed
```

공유가 없는 공정에서는 두 보기가 같을 수 있으며 UI가 그 이유를 명시한다.

## 레거시 렌더러 대응

레거시 `QuadrantWidget`의 핵심 표현을 웹 격자로 옮겼다.

- 고정 사각 cell
- 층별 row와 4개 quadrant column
- empty dark gray
- Pin gray P
- normal part의 색상과 문자
- Crystal의 base/paint 대각 분할
- row/column header

편집기도 동일한 cell을 사용해 보기와 편집 사이의 표현 차이를 제거했다.

## 정보량 축소

- 상세 판정은 drawer로 이동
- 선택 노드 정보는 같은 drawer를 재사용
- 기록과 설정은 modal
- 연구 정보는 고급 모드 전용
- 직접 편집기는 기본 접힘
- 빠른 판정 결과는 verdict와 시간만 표시
- 유형과 근거는 분석 후 상세 보기에서 표시

## Main4 PP 엔진 이식

Focused UI의 화면 구성, 세 실행 모드, Half proof forest와 DAG/Tree 전개는 유지했다. PP 판정 코어만 Main4 구현으로 교체해 다음 경로를 추가했다.

- 유일한 no-overflow receipt predecessor chain 선형 압축
- 전층 Rank0 overflow frontier
- Swappable/Stackable predecessor 복원
- 각 Pin Push edge 정방향 replay
- 소진 음성 route `pp-closure-exhausted`

별도 완료 전제 플래그나 전제 배지는 결과 모델과 UI에 노출하지 않는다.
