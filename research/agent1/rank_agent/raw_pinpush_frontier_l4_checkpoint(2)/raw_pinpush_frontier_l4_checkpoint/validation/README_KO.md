# 검증 코드 실행

## L=3 전체 구조 eager-column 검사

```bash
g++ -O3 -std=c++20 eager_exhaustive_l3.cpp -o eager_l3
./eager_l3
```

## 40,171 predecessor 검사

이 검사는 target뿐 아니라 원본 `claw_process`가 생성한 predecessor 파일이 필요하다.

```bash
python check_eager_column.py \
  --targets ../data/all40171clawsnohybrid.txt \
  --predecessors /path/to/original_predecessors_40171.txt
```
