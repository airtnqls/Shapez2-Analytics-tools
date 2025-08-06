# Shapez2 설치 가이드

## 🚀 빠른 시작

### Windows 사용자

1. **Python 설치 확인**
```bash
python --version
# Python 3.8 이상이어야 합니다
```

2. **프로젝트 다운로드**
```bash
git clone https://github.com/your-username/Shapez2.git
cd Shapez2
```

3. **의존성 설치**
```bash
pip install PyQt6 numpy
pip install pyqtgraph  # 그래프 기능 사용시
```

4. **실행**
```bash
python gui.py
```

### macOS 사용자

1. **Homebrew로 Python 설치** (필요시)
```bash
brew install python
```

2. **프로젝트 다운로드**
```bash
git clone https://github.com/your-username/Shapez2.git
cd Shapez2
```

3. **의존성 설치**
```bash
pip3 install PyQt6 numpy
pip3 install pyqtgraph  # 그래프 기능 사용시
```

4. **실행**
```bash
python3 gui.py
```

### Linux 사용자

1. **시스템 패키지 설치**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-pyqt6

# CentOS/RHEL
sudo yum install python3 python3-pip
sudo yum install python3-qt6  # 또는 해당 배포판의 PyQt6 패키지
```

2. **프로젝트 다운로드**
```bash
git clone https://github.com/your-username/Shapez2.git
cd Shapez2
```

3. **의존성 설치**
```bash
pip3 install PyQt6 numpy
pip3 install pyqtgraph  # 그래프 기능 사용시
```

4. **실행**
```bash
python3 gui.py
```

## 🔧 상세 설치 가이드

### Python 설치

#### Windows
1. [Python 공식 사이트](https://www.python.org/downloads/)에서 최신 버전 다운로드
2. 설치 시 "Add Python to PATH" 옵션 체크
3. 설치 완료 후 명령 프롬프트에서 확인:
```bash
python --version
```

#### macOS
```bash
# Homebrew 사용
brew install python

# 또는 공식 설치 프로그램 사용
# https://www.python.org/downloads/macos/
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### PyQt6 설치

#### Windows
```bash
pip install PyQt6
```

#### macOS
```bash
pip3 install PyQt6
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt install python3-pyqt6
# 또는
pip3 install PyQt6

# CentOS/RHEL
sudo yum install python3-qt6
# 또는
pip3 install PyQt6
```

### 추가 의존성 설치

#### NumPy
```bash
pip install numpy
```

#### PyQtGraph (선택사항)
```bash
pip install pyqtgraph
```

## 🐛 문제 해결

### 일반적인 문제들

#### 1. "ModuleNotFoundError: No module named 'PyQt6'"

**해결 방법:**
```bash
# PyQt6 재설치
pip uninstall PyQt6
pip install PyQt6

# 또는 pip 업그레이드 후 설치
pip install --upgrade pip
pip install PyQt6
```

#### 2. "ImportError: DLL load failed" (Windows)

**해결 방법:**
1. Visual C++ 재배포 가능 패키지 설치
2. Python 재설치
3. PyQt6 재설치

#### 3. "QApplication: could not connect to display" (Linux)

**해결 방법:**
```bash
# X11 포워딩 설정 (SSH 사용시)
ssh -X username@server

# 또는 DISPLAY 환경변수 설정
export DISPLAY=:0
```

#### 4. "Permission denied" (Linux/macOS)

**해결 방법:**
```bash
# 권한 문제 해결
sudo pip3 install PyQt6

# 또는 사용자 설치
pip3 install --user PyQt6
```

#### 5. "Python not found" (Windows)

**해결 방법:**
1. Python이 PATH에 추가되었는지 확인
2. 시스템 환경변수에서 Python 경로 확인
3. Python 재설치 시 "Add to PATH" 옵션 체크

### 성능 문제

#### 1. 느린 실행 속도

**해결 방법:**
- 가상환경 사용
- 불필요한 백그라운드 프로그램 종료
- 메모리 사용량 확인

#### 2. 메모리 부족

**해결 방법:**
- 대용량 데이터는 청크 단위로 처리
- 가상 메모리 증가
- 불필요한 탭 닫기

### GUI 문제

#### 1. 창이 표시되지 않음

**해결 방법:**
```python
# gui.py에서 디버그 모드 활성화
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ShapezGUI()
    window.show()  # 이 줄이 있는지 확인
    sys.exit(app.exec())
```

#### 2. 버튼이 작동하지 않음

**해결 방법:**
- 이벤트 핸들러 연결 확인
- 시그널-슬롯 연결 확인
- 로그 확인

## 🔍 디버깅 도구

### 로그 활성화

```python
# gui.py에서 로그 레벨 설정
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 메모리 사용량 확인

```python
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

print(f"메모리 사용량: {get_memory_usage():.2f} MB")
```

### 성능 프로파일링

```python
import cProfile
import pstats

def profile_function(func):
    profiler = cProfile.Profile()
    profiler.enable()
    result = func()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats()
    return result
```

## 📦 가상환경 사용

### 가상환경 생성

```bash
# Windows
python -m venv shapez2_env
shapez2_env\Scripts\activate

# macOS/Linux
python3 -m venv shapez2_env
source shapez2_env/bin/activate
```

### 가상환경에서 설치

```bash
# 가상환경 활성화 후
pip install PyQt6 numpy
pip install pyqtgraph  # 선택사항
```

### 가상환경 비활성화

```bash
deactivate
```

## 🚀 개발 환경 설정

### IDE 설정

#### VS Code
1. Python 확장 설치
2. 가상환경 선택
3. 디버그 설정 추가

#### PyCharm
1. 프로젝트 생성
2. 인터프리터 설정
3. 실행 구성 설정

### Git 설정

```bash
# Git 초기화
git init
git add .
git commit -m "Initial commit"

# .gitignore 파일 생성
echo "*.pyc" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.log" >> .gitignore
```

## 📋 시스템 요구사항

### 최소 요구사항

- **OS**: Windows 10, macOS 10.14+, Ubuntu 18.04+
- **Python**: 3.8 이상
- **RAM**: 4GB 이상
- **저장공간**: 1GB 이상

### 권장 사양

- **OS**: Windows 11, macOS 12+, Ubuntu 20.04+
- **Python**: 3.9 이상
- **RAM**: 8GB 이상
- **저장공간**: 2GB 이상
- **CPU**: 멀티코어 프로세서

## 🔄 업데이트

### 프로젝트 업데이트

```bash
# Git 저장소 업데이트
git pull origin main

# 의존성 업데이트
pip install --upgrade PyQt6 numpy
```

### Python 업데이트

```bash
# Windows
# Python 공식 사이트에서 새 버전 다운로드

# macOS
brew upgrade python

# Linux
sudo apt update
sudo apt upgrade python3
```

## 📞 지원

문제가 발생하면 다음을 확인해주세요:

1. **로그 확인**: GUI의 로그 탭에서 오류 메시지 확인
2. **버전 확인**: Python과 PyQt6 버전 확인
3. **시스템 정보**: OS 버전과 시스템 사양 확인
4. **GitHub Issues**: 기존 이슈 확인 후 새 이슈 생성

---

이 가이드를 따라해도 문제가 해결되지 않으면, GitHub Issues에 상세한 오류 메시지와 함께 이슈를 생성해주세요.
