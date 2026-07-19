# Source audit

Generator 의미를 고정할 때 비교한 기준:

```text
user repository: airtnqls/Shapez2-Analytics-tools
observed HEAD:    07aded68640faf9e86f3891ba2ed6f92d342e509
shape.py blob:    272a6fc9fde3ae0911a6997e21461c6cfff5bea8

reference repo:   cpcp1998/shapez2-solver
observed HEAD:    4a53244ce4333dd16bf5f93b14a38793cf8b4a2f
shape.cpp blob:   0bc7a30b7ccf5de609eab3eeb67de05988647d9f
shape tests blob: 79be9239418df242b67ebd855e23177425594680
```

중요한 차이:

- 기준 구현은 global occupied height 아래만 변환한다.
- 빈 입력은 빈 출력이다.
- Generator 뒤 중력을 호출하지 않는다.
- 현재 사용자 `Shape.py`는 빈 입력에 한 층을 만들어 채우고, 내부 `layers` 전체를 순회하며,
  마지막에 `apply_physics()`를 호출한다.

`patches/shape_py_crystal_generator.patch`는 기준 의미에 맞춘다.
