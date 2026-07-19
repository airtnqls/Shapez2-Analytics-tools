# 레거시 GUI UX 실측 대응표

기준 저장소: `airtnqls/Shapez2-Analytics-tools`의 PyQt6 `gui.py`, `process_tree_solver.py` 및 기존 병합 문서.

## 확인된 레거시 기능과 웹 대응

| 레거시 기능 | Next.js 대응 | 상태 |
|---|---|---|
| ShapeWidget / QuadrantWidget | `ShapeEditor`, `ShapeRenderer` | 완료 |
| 사분면 brush | `-/S/P/c` brush palette | 완료 |
| Undo / Redo | 편집 history 50단계 | 완료 |
| 층 추가·삭제·회전 | Layer toolbar | 완료 |
| 행/층 drag/drop | HTML drag layer reorder | 완료 |
| 동적 A/B/C… 입력 | Operations Lab 최대 6입력 | 완료 |
| 정방향 연산 버튼 | Rotate/Mirror/Gravity/PinPush/Generator/Cut/Swap/Stack | 완료 |
| 출력 도형 영역 | 실제 SVG renderer + 목표/입력 재사용 | 완료 |
| 빠른 존재성 | Worker `fast` mode | 완료 |
| 분류 | Worker `type` mode | 완료 |
| ProcessTree | interactive React Flow DAG/Tree | 완료 |
| 생략 노드 확장 | Tree/DAG, input collapse, node inspector | 완료 |
| 줌/팬 | mouse/touch zoom, pan, controls | 완료 |
| 미니맵 | React Flow MiniMap | 완료 |
| 단계 재생 | previous/play/pause/next controller | 완료 |
| Batch 탭 | 파일·paste·regex·worker pool | 완료 |
| 검색 pagination | 가상/scroll 결과 테이블, filter | 완료 |
| 결과 저장 | CSV, JSON, ZIP | 완료 |
| QSettings | IndexedDB + Zustand | 완료 |
| 로그 패널 | bottom worker log + Research tab | 완료 |
| 진행/취소 | Worker progress event, cancel, terminate | 완료 |
| 테스트 편집기 | Operations Lab + Compare + Research diagnostics | 현대화 대체 |
| 다국어 | 한국어 기본, schema 분리 | 기반 마련 |
| PyInstaller icons | bundled SVG/PNG + Lucide UI icons | 완료 |

## 변경한 UX 원칙

레거시의 기능 범위는 유지하되, 각각의 inverse provider를 GUI가 직접 호출하던 구조는 제거했습니다. 웹 UI는 `analyze(code, cap, mode)` 한 경로만 사용하며 worker가 반환하는 불변 결과 schema를 소비합니다. 따라서 같은 target을 ProcessTree, 분류, 상세 정보에서 반복 계산하지 않습니다.

ProcessTree는 정적 이미지를 보여주는 대신 도형과 연산을 별도 노드로 표현하는 DAG가 기본입니다. 같은 중간 도형은 공유되며, 레거시 중복 트리가 필요할 때 Tree 보기를 선택합니다.
