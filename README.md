# Shapez2 - 도형 시뮬레이터 및 분석 도구

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📖 프로젝트 소개

Shapez2는 복잡한 도형 조작과 분석을 위한 강력한 시뮬레이터입니다. 이 프로젝트는 Shapez 게임의 메커니즘을 기반으로 하여, 다양한 도형 조작 연산을 시뮬레이션하고 분석할 수 있는 도구를 제공합니다.

### ✨ 주요 기능

- **🎯 실시간 도형 시뮬레이션**: 복잡한 도형 조작을 실시간으로 시뮬레이션
- **🔍 역연산 분석**: 목표 도형을 만들기 위한 원본 도형을 찾는 역추적 기능
- **📊 도형 분류 시스템**: 도형을 자동으로 분류하고 분석
- **🎨 직관적인 GUI**: PyQt6 기반의 사용자 친화적 인터페이스
- **🌳 공정 트리 시각화**: 도형 제작 과정을 트리 형태로 시각화
- **📈 배치 처리**: 대량의 도형 데이터를 효율적으로 처리
- **🔧 고급 분석 도구**: 클로, 코너, 하이브리드 등 특수 도형 분석

## 🚀 설치 및 실행

### 필수 요구사항

```bash
Python 3.8 이상
PyQt6
numpy
pyqtgraph (선택사항 - 그래프 기능용)
```

### 설치 방법

1. **저장소 클론**

```bash
git clone https://github.com/your-username/Shapez2.git
cd Shapez2
```

2. **의존성 설치**

```bash
pip install PyQt6 numpy
pip install pyqtgraph  # 그래프 기능 사용시
```

3. **실행**

```bash
python gui.py
```

## 🎮 사용법

### 기본 사용법

1. **도형 입력**: 입력 필드에 도형 코드를 입력합니다

   - 예: `ScSc:ScSc` (2층 도형)
   - 예: `P---:ScSc:----` (3층 도형)
2. **연산 실행**: 버튼을 클릭하여 다양한 연산을 수행

   - **Stack**: 두 도형을 쌓기
   - **Swap**: 두 도형의 위치 교환
   - **Rotate**: 도형 회전
   - **Paint**: 도형 색상 변경
   - **Crystal Generator**: 크리스탈 생성
   - **Physics**: 물리 법칙 적용
3. **역연산**: "Find Origin" 버튼으로 목표 도형의 원본 찾기

### 도형 코드 규칙

| 문자  | 의미      | 설명                 |
| ----- | --------- | -------------------- |
| `S` | 일반 도형 | 기본 도형 조각       |
| `c` | 크리스탈  | 특별한 크리스탈 조각 |
| `P` | 핀        | 고정 핀 조각         |
| `-` | 빈 공간   | 아무것도 없는 공간   |
| `:` | 층 구분자 | 여러 층을 구분       |

### 색상 코드

| 문자  | 색상   |
| ----- | ------ |
| `r` | 빨강   |
| `g` | 초록   |
| `b` | 파랑   |
| `m` | 마젠타 |
| `c` | 시안   |
| `y` | 노랑   |
| `u` | 무색   |
| `w` | 흰색   |

## 🎯 고급 기능

### 1. 역연산 시스템 (Reverse Engineering)

목표 도형을 만들기 위해 필요한 원본 도형을 찾는 강력한 기능입니다.

```python
# 예시: 목표 도형에서 원본 찾기
target_shape = Shape.from_string("ScSc:ScSc")
candidates = ReverseTracer.inverse_apply_physics(target_shape, depth=3)
```

**사용 시나리오:**

- 커스텀 도형을 만들고 기능을 시뮬레이션 할 때
- 복잡한 도형의 제작 방법을 찾고 싶을 때
- 대량 데이터를 처리할 때

### 2. 도형 분류 시스템

도형을 자동으로 분류하여 분석합니다:

- **불가능형**: 물리적으로 불가능한 도형
- **클로**: 클로 연산이 가능한 도형
- **하이브리드**: 복합적인 특성을 가진 도형
- **단순형**: 기본적인 도형
- **코너형**: 코너 연산이 가능한 도형

### 3. 공정 트리 시각화

도형 제작 과정을 트리 형태로 시각화하여 제작 단계를 명확히 보여줍니다.

### 4. 배치 처리

대량의 도형 데이터를 효율적으로 처리할 수 있습니다:

## 📁 프로젝트 구조

```
Shapez2/
├── gui.py                 # 메인 GUI 애플리케이션
├── shape.py               # 핵심 도형 클래스 및 연산
├── shape_analyzer.py      # 도형 분석 및 분류 시스템
├── process_tree_solver.py # 공정 트리 생성 및 해결
├── corner_tracer.py       # 코너 추적 알고리즘
├── claw_tracer.py         # 클로 추적 알고리즘
├── combination_generator.py # 유효한 조합 생성
├── run_analysis.py        # 배치 분석 스크립트
├── data/                  # 데이터 파일들
│   ├── sample_shapes.txt  # 샘플 도형 데이터
│   ├── all40171clawsnohybrid.txt # 클로 분석 데이터
│   └── ...
└── README.md             # 이 파일
```

## 🔧 주요 모듈 설명

### 1. `gui.py` - 메인 GUI

- **ShapezGUI**: 메인 윈도우 클래스
- **OriginFinderThread**: 백그라운드 역연산 처리
- **ShapeWidget**: 도형 시각화 위젯
- **DataTabWidget**: 데이터 탭 관리

### 2. `shape.py` - 핵심 도형 시스템

- **Shape**: 메인 도형 클래스
- **Layer**: 도형의 층을 나타내는 클래스
- **Quadrant**: 개별 사분면 조각
- **ReverseTracer**: 역연산 추적 시스템

### 3. `shape_analyzer.py` - 도형 분석

- **ShapeType**: 도형 분류 타입 열거형
- **analyze_shape()**: 도형 분석 메인 함수
- 다양한 분류 알고리즘 구현

### 4. `process_tree_solver.py` - 공정 트리

- **ProcessNode**: 트리 노드 클래스
- **ProcessTreeSolver**: 공정 트리 해결기
- 도형 제작 과정 시각화

## 🎮 사용 예시

### 예시 1: 기본 도형 조작

```python
# 도형 생성
shape1 = Shape.from_string("ScSc")
shape2 = Shape.from_string("----:ScSc")

# 스택 연산
result = Shape.stack(shape1, shape2)
print(result)  # 출력: ScSc:ScSc

# 회전 연산
rotated = shape1.rotate(clockwise=True)
```

### 예시 2: 역연산 사용

```python
# 목표 도형
target = Shape.from_string("ScSc:ScSc")

# 역연산으로 원본 찾기
candidates = ReverseTracer.inverse_apply_physics(target, depth=2)
for candidate in candidates:
    print(f"후보: {candidate}")
```

### 예시 3: 도형 분석

```python
# 도형 분석
shape_code = "ScSc:ScSc"
shape_obj = Shape.from_string(shape_code)
classification, reason = analyze_shape(shape_code, shape_obj)
print(f"분류: {classification}")
print(f"사유: {reason}")
```

## 디버깅 팁

- **로그 레벨 조정**: GUI에서 로그 레벨을 변경하여 상세한 정보 확인
- **단계별 실행**: 복잡한 연산을 단계별로 실행하여 중간 결과 확인
- **데이터 탭 활용**: 대량 데이터 처리를 위해 데이터 탭 기능 활용
