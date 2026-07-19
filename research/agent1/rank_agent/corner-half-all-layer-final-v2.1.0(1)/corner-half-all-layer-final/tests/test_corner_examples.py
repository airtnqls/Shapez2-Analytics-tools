from corner_half import compile_abstract, first_rejection, is_craftable_column

CASES = {
    "": True,
    "S-S-S-S-c": True,
    "cS-S-S-S-Sc": True,
    "cS-S-c": False,
    "PcS-S-c": True,
    "-S-c": True,
    "-P": False,
}

for code, expected in CASES.items():
    assert is_craftable_column(code) is expected, (code, first_rejection(code))
    if expected:
        print(compile_abstract(code))
