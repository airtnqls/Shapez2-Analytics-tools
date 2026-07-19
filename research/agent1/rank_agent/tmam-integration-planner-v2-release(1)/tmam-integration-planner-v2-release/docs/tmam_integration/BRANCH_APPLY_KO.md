# 브랜치 적용 방법

## 새 브랜치에서 patch 적용

```bash
git switch -c tmam-integration
git am /path/to/tmam-integration.patch
python run_tmam_integration_tests.py
```

patch는 새 파일만 추가하며 현재 단계에서는 기존 `shape.py`, `shape_classifier.py`, tracer를 수정하지 않는다.

## ZIP 복사 방식

ZIP의 다음 항목을 저장소 루트에 복사한다.

```text
tmam/
tests/tmam_integration/
docs/tmam_integration/
examples/tmam_integration/
tools/
run_tmam_integration_tests.py
README_TMAM_INTEGRATION.md
STATUS_TMAM_INTEGRATION_KO.md
CHANGELOG_TMAM_INTEGRATION.md
```

이름이 겹치는 ## 병합 전 확인

```bash
python -m compileall -q tmam tests/tmam_integration examples/tmam_integration tools
python run_tmam_integration_tests.py
PYTHONPATH=. python tools/check_legacy_shape_types.py shape_classifier.py
```
