# Shapez2 TMAM Studio

첨부 ZIP의 Worker 엔진과 전 레이어 Corner/Half raw proof DAG를 공유하는 두 개의 GUI입니다.

- `run-desktop.bat`: 아카이브에서 복원한 원본 전체 기능 PyQt6 GUI
- `run-web.bat`: 레거시 화면 언어를 재해석한 Next.js App Router GUI와 로컬 API
- `public/solver.worker.js`: 두 GUI가 공유하는 ZIP 판정·witness 엔진
- `backend/corner_half`: `CERTIFIED_MACRO`를 실제 RAW_INPUT/ROTATE/CUT/SWAP/STACK/GENERATE/PIN_PUSH DAG로 전개하는 constructor

## 제작 과정 모델

판정 결과의 `proof`는 도형과 연산을 분리한 공유 DAG입니다. `processRecipe`는 이 DAG에서
CPCP 검색의 parent backpointer와 같은 정보를 뽑아 다음을 보장합니다.

- 연산 입력, 전체 출력, 실제 선택 출력의 명시적 구분
- 부모 공정 의존성을 위상 정렬한 안정적인 재생 순서
- 공유 하위 도형과 미사용 Cut/Swap 출력 보존
- 모든 positive constructor를 primitive까지 전개하고 독립 재실행 검증

## 실행

```powershell
npm ci --no-audit --no-fund
npm run check
npm run build
run-web.bat
```

원본 전체 기능 PyQt 실행:

```powershell
run-desktop.bat
```

PyQt 실행본은 `legacy_desktop/`, 공통 backend는 `backend/`입니다. 수정 전 Python GUI 전체는
`archive/legacy-python-gui-20260719/`에 원상태로 보관되어 있습니다. 바탕화면의
`Shapez2 TMAM Studio`는 PyQt, `Shapez2 TMAM Web Studio`는 Web GUI를 실행합니다.

세부 계약은 `docs/CPCP_PROCESS_RECIPE_KO.md`를 참고하세요.
