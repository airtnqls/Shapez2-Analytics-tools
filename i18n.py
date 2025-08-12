import json
import locale
import os
from typing import Any, Dict

_current_lang = None
_translations: Dict[str, Dict[str, str]] = {}
_fallback_lang = "en"

# Optional: map raw UI strings to stable keys (useful to localize existing literals without large code edits)
_ALIASES: Dict[str, str] = {
    # Groups / sections
    "건물 작동": "ui.groups.buildings",
    "데이터 처리": "ui.groups.data_process",
    "기원 역추적": "ui.groups.reverse_tracing",
    "파일 선택": "ui.groups.file_select",
    "데이터": "ui.groups.data",
    "공정 트리 분석": "ui.groups.process_tree_analysis",
    "공정 트리": "ui.groups.process_tree",
    "출력": "ui.groups.output",
    # Tabs
    "분석 도구": "ui.tabs.analysis_tools",
    "대량처리": "ui.tabs.batch",
    "공정트리": "ui.tabs.process_tree",
    "테스트 편집기": "ui.tabs.test_editor",
    # Common labels/buttons
    "자동 적용": "ui.auto_apply",
    "Undo (Ctrl+Z)": "ui.undo.tooltip",
    "Redo (Ctrl+Y)": "ui.redo.tooltip",
    "선택된 파일 없음": "ui.file.selected_none",
    "파일:": "ui.file.file",
    "찾아보기": "ui.file.browse",
    "+ 새 탭": "ui.btn.add_tab",
    # Buildings buttons
    "절반 파괴기": "ui.btn.destroy_half",
    "스태커 (A가 아래)": "ui.btn.stack",
    "핀 푸셔": "ui.btn.push_pin",
    "물리 적용": "ui.btn.apply_physics",
    "스와퍼 (A, B)": "ui.btn.swap",
    "커터": "ui.btn.cutter",
    "90 회전": "ui.btn.rotate90",
    "180 회전": "ui.btn.rotate180",
    "270 회전": "ui.btn.rotate270",
    "심플 커터": "ui.btn.simple_cutter",
    "쿼드 커터": "ui.btn.quad_cutter",
    "페인터:": "ui.painter.label",
    "칠하기": "ui.btn.paint",
    "크리스탈 생성:": "ui.crystal.label",
    "생성": "ui.btn.generate",
    "분류기": "ui.btn.classifier",
    # Data processing buttons
    "단순화": "ui.btn.simplify",
    "구체화": "ui.btn.detail",
    "1사분면 코너": "ui.btn.corner1",
    "불가능 제거": "ui.btn.remove_impossible",
    "역순": "ui.btn.reverse",
    "미러": "ui.btn.mirror",
    "코너화": "ui.btn.cornerize",
    "하이브리드": "ui.btn.hybrid",
    # Reverse tracing area
    "목표 도형:": "ui.reverse.target_shape",
    "기원 찾기 (규칙)": "ui.btn.find_origin_rules",
    "전체 복사": "ui.btn.copy_all",
    "발견된 모든 후보:": "ui.reverse.found_candidates",
    # Log header
    "<b>로그</b>": "ui.log.header.html",
    "상세 로그 보기": "ui.log.show_verbose",
    "지우기": "ui.log.clear",
    "자동 테스트": "ui.groups.auto_test",
    "전체 테스트 실행": "ui.btn.run_all_tests",
    "역연산 테스트 실행": "ui.btn.run_reverse_tests",
    "출력": "ui.groups.outputs",
    "샘플": "ui.sample",
    "공정 트리 생성": "ui.btn.process_tree_generate",
    "스태커 (A+B)": "ui.btn.stack_a_plus_b",
    "스태커": "ui.btn.stack_forall_plus_b",
    "스와퍼 (A↔B)": "ui.btn.swap_a_b",
    "스와퍼": "ui.btn.swap_forall_b",
    "출력 A": "ui.output.a",
    "출력 B": "ui.output.b",
    "출력 C": "ui.output.c",
    "출력 D": "ui.output.d",
    # ShapeType enum values
    "빈_도형": "enum.shape_type.empty",
    "단순_모서리": "enum.shape_type.simple_corner",
    "스택_모서리": "enum.shape_type.stack_corner",
    "스왑_모서리": "enum.shape_type.swap_corner",
    "클로_모서리": "enum.shape_type.claw_corner",
    "단순_기하형": "enum.shape_type.simple_geometric",
    "스왑가능형": "enum.shape_type.swapable",
    "하이브리드": "enum.shape_type.hybrid",
    "복합_하이브리드": "enum.shape_type.complex_hybrid",
    "클로": "enum.shape_type.claw",
    "클로_하이브리드": "enum.shape_type.claw_hybrid",
    "클로_복합_하이브리드": "enum.shape_type.claw_complex_hybrid",
    "불가능형": "enum.shape_type.impossible"
}


def detect_system_language() -> str:
    # Windows locale like ('ko_KR', 'cp949') -> 'ko'
    lang, _ = locale.getdefaultlocale() or (None, None)
    if not lang:
        return _fallback_lang
    return lang.split("_")[0].lower()


def set_language(lang: str):
    global _current_lang
    _current_lang = lang


def get_language() -> str:
    return _current_lang or detect_system_language()


def load_locales(locales_dir: str):
    global _translations
    _translations.clear()
    for fname in os.listdir(locales_dir):
        if not fname.endswith('.json'):
            continue
        lang = os.path.splitext(fname)[0]
        path = os.path.join(locales_dir, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _translations[lang] = json.load(f)
        except Exception:
            _translations[lang] = {}


def translate(key: str, **vars: Any) -> str:
    # Allow raw-Korean (or other) strings as keys via alias mapping
    key_to_lookup = _ALIASES.get(key, key)

    lang = get_language()
    entry = None

    if lang in _translations:
        entry = _translations[lang].get(key_to_lookup)
    if entry is None and _fallback_lang in _translations:
        entry = _translations[_fallback_lang].get(key_to_lookup)

    if entry is None:
        # Fallback to original key or alias
        entry = key

    try:
        return entry.format(**vars)
    except Exception:
        # If formatting fails due to missing vars, return raw entry
        return entry


# Convenience alias
_ = translate
