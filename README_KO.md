# Shapez2 TMAM Web Studio 2.1.0 — 집중형 UI

기본 화면에서 불필요한 분석 정보와 패널을 숨기고, **도형 입력 → 판정/분석/제작 과정**만 바로 사용할 수 있도록 다시 구성한 클라이언트 전용 Next.js 정적 앱입니다.

## 바로 실행

Windows:

1. ZIP을 완전히 압축 해제합니다.
2. `run.bat`을 실행합니다.
3. `http://127.0.0.1:4173`이 자동으로 열립니다.

실행만 할 때는 Node.js가 없어도 됩니다. Node.js가 있으면 내장 Node 정적 서버를 사용하고, 없으면 Windows PowerShell 서버로 대체합니다.

Linux/macOS:

```bash
./run.sh
```

재빌드에는 Node.js 20.9 이상이 필요합니다.

```bash
npm ci --no-audit --no-fund
npm run check
```

## 기본 화면

기본 화면에는 다음만 표시됩니다.

- 도형 코드와 최대 층
- `판정 · 빠름`, `분석`, `제작 과정`
- 큰 도형 미리보기
- 한 줄 결과

직접 격자 편집기, 상세 판정표, 기록, 설정, 연구 정보는 사용자가 열 때만 표시됩니다. 연산 실험·일괄 분석·비교는 상단의 `도구` 메뉴에 묶었습니다.

## 세 실행 모드는 실제로 다릅니다

### 판정 · 빠름

- 정상 입력에 대해 `POSSIBLE / IMPOSSIBLE`만 계산
- 유형 설명과 Proof graph를 만들지 않음
- 작은 Claw/Hybrid 목표 인덱스만 로드

### 분석

- 도형 유형, family, 판정 경로와 근거 계산
- Claw 40,171개 및 Hybrid 367개 witness 표 로드
- 제작 과정 graph는 만들지 않음

### 제작 과정

- 분석 결과에 더해 기본 입력까지의 공정 graph 생성
- 정확한 Half proof forest 로드
- 연산별 입력·출력과 사용하지 않은 두 번째 출력 표시

동일 프로세스에서 뒤 실행은 캐시 영향을 받으므로 단일 측정 시간만으로 속도 배율을 보장하지 않습니다. 다만 각 모드가 로드하는 데이터와 수행 단계가 분리됐는지는 Worker 감사로 검증합니다.

## 제작 DAG와 제작 Tree

- **공유 DAG**: 동일한 하위 제작 공정을 한 번만 표시합니다.
- **제작 Tree**: 같은 하위 공정을 사용한 횟수만큼 복제합니다.

UI의 문제 사례 `--PP:--Pc:SSSS:-SS-:cS-S`에서는:

- 고유 연산: 181
- Tree에서 사용되는 연산: 2,144
- 공유 노드: 86
- graph node/edge: 429 / 506
- 기본 입력까지 전개: 완료
- 정방향 replay: 통과

따라서 이 사례에서 두 보기는 실제 자료구조와 노드 수가 명확히 다릅니다.

## 레거시형 도형 시각화와 편집

웹의 원형 장식형 렌더러를 제거하고 레거시 `QuadrantWidget`과 같은 방식으로 바꿨습니다.

- 위에서 아래로 쌓인 층별 4칸 격자
- 회색 층/사분면 header
- 일반 조각, Pin, Crystal의 독립 표현
- Crystal은 레거시와 같은 대각 분할 표현
- 셀 클릭·드래그 brush
- 우클릭 지우기
- 층 채우기, 회전, 삭제, drag reorder
- Undo/Redo

## 한국어

기본 화면, 제작 과정, 상세 분석, Batch, 비교, 설정과 연구 화면의 사용자 표시문을 한국어로 정리했습니다. `DAG`, `CSV`, `ZIP`, `Worker`, `PP`처럼 기술적으로 통용되는 약어는 필요한 곳에만 유지합니다.

## 정확성 경계

현재 생산 Worker는 parser/physics, 전층 Corner/Half, Swappable, 목표 지향 Stack closure, 인증 Claw/Hybrid 표와 Main4 PP 정규형 엔진을 사용합니다.

PP 경로는 먼저 유일한 no-overflow receipt predecessor chain을 선형으로 압축한 뒤 Rank0 overflow frontier를 풉니다. 양성은 실제 predecessor와 각 Pin Push 출력을 정방향 replay하고, 음성은 Rank0 frontier와 receipt chain을 모두 소진한 `pp-closure-exhausted` certificate로 반환합니다. 정상적으로 완료된 분석에는 조건부/가정 표기를 붙이지 않습니다.

## 주요 보고서

- `reports/MAIN4_PP_PORT_VALIDATION.json`
- `reports/FOCUSED_UI_PROOF_AUDIT.json`
- `reports/VALIDATION_SUMMARY.json`
- `reports/FULL_CHECK.log`
- `reports/UI_FOCUSED_1440x900.png`
- `docs/FOCUSED_UI_2.1_KO.md`

## 이전 버전 화면이 섞이거나 프론트가 깨질 때

같은 주소(`127.0.0.1:4173`)에서 이전 릴리스를 실행했다면 브라우저 서비스 워커가 남아 있을 수 있습니다.
Chrome 개발자 도구(F12) → Application → Service Workers → Unregister 후
Application → Storage → Clear site data를 누르고 `run.bat`을 다시 실행하세요.
이 릴리스부터 문서 탐색은 network-first로 처리하여 이전 HTML과 새 JS가 섞이지 않도록 수정했습니다.
