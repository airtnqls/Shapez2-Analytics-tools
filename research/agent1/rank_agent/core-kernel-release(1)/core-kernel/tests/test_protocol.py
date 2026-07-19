from shapez2_core import CompactShape, ForwardCall, Operation, replay, stack


def test_forward_call_replay_contract():
    a = CompactShape.parse("SS--", cap=5)
    b = CompactShape.parse("--SS", cap=5)
    call = ForwardCall(Operation.STACK, (a, b), {})
    assert replay(call) == (stack(a, b),)
