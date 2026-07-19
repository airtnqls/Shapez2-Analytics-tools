"""Exact four-column replay of the C1..C7 Corner IR.

Every state in this module is an actual structural quad shape and every edge is
one of the modelled game operations (Stack, Generator, Swapper, Cutter,
Pin-Pusher, Rotate).  This module records prefab boundaries compactly;
:mod:`proof_dag` recursively expands every prefab certificate until the sole
leaf is the raw one-layer ``SSSS`` input.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .corner_constructor import construct_corner, replay_event_exchange
from .corner_ir import CornerIRStep, CornerRule, compile_corner_ir
from .primitive_prefabs import (
    build_one_pin,
    build_pin_tower_helper,
    build_single_crystal_helper,
    build_single_layer_pattern,
)
from .structural_ops import cut, generate, rotate, stack, swap
from .structural_physics import EMPTY, code, column, is_stable, parse, push_pin


class FullReplayError(ValueError):
    pass


@dataclass(frozen=True)
class FullOperationStep:
    operation: str
    before: str
    operand: str
    after: str
    target_before: str
    target_after: str


@dataclass(frozen=True)
class CornerFullReplay:
    target: str
    cap: int
    operations: tuple[FullOperationStep, ...]
    final_full_shape: str
    final_target_column: str
    all_intermediate_stable: bool
    replay_ok: bool


def _rows_from_columns(columns: tuple[str, str, str, str], cap: int) -> list[list[str]]:
    return [
        [columns[q][l] if l < len(columns[q]) else EMPTY for q in range(4)]
        for l in range(cap)
    ]


def _tower(height: int) -> str:
    return "S" * max(0, height)


def _canonical(a: str, height: int, cap: int, audit: bool = True) -> list[list[str]]:
    t=_tower(height)
    rows=_rows_from_columns((a,t,t,t),cap)
    if audit and not is_stable(rows):
        raise FullReplayError(f"canonical support state is unstable: A={a!r}, T={t!r}")
    return rows


def _columns(rows, cap: int) -> tuple[str,str,str,str]:
    return tuple(column(rows,q) for q in range(4))  # type: ignore[return-value]


def _record(ops:list[FullOperationStep], name:str, before, operand, after, a_before:str, a_after:str, audit: bool = True):
    if audit and not is_stable(after):
        raise FullReplayError(f"{name} produced unstable shape: {code(after)}")
    if column(after,0) != a_after:
        raise FullReplayError(
            f"{name} target mismatch: expected {a_after!r}, got {column(after,0)!r}"
        )
    ops.append(FullOperationStep(name,code(before),code(operand) if operand is not None else "",code(after),a_before,a_after))


def _install_from_canonical(current, a:str, b:str, c:str, d:str, cap:int, ops:list[FullOperationStep], audit: bool = True):
    """Install B,C,D with two swaps, preserving A.

    A solid temporary C column prevents any desired D crystal from meeting the
    old C across the second cut boundary.
    """
    cols=_columns(current,cap)
    if cols[0] != a or not (set(cols[1])<=set('S') and cols[1]==cols[2]==cols[3]):
        raise FullReplayError(f"not canonical before helper install: {cols}")
    support=cols[1]
    temp_height=max(1,len(a),len(b),len(c),len(d),len(support))
    temp=_tower(min(cap,temp_height))
    prefab_td=_rows_from_columns(("","",temp,d),cap)
    if audit and not is_stable(prefab_td):
        raise FullReplayError("temporary-tower/D prefab unstable")
    first,_=swap(current,prefab_td,cap)
    expected_first=(a,support,temp,d)
    if _columns(first,cap)!=expected_first:
        raise FullReplayError(("first helper swap",_columns(first,cap),expected_first))
    _record(ops,"swap_install_tempC_D",current,prefab_td,first,a,a,audit)

    rotated=rotate(first,1)
    if audit and not is_stable(rotated):raise FullReplayError("rotation made state unstable")
    ops.append(FullOperationStep("rotate_cw",code(first),"",code(rotated),a,column(rotated,1)))
    prefab_bc=_rows_from_columns(("","",b,c),cap)
    if audit and not is_stable(prefab_bc):
        raise FullReplayError(f"B/C prefab unstable: {b!r},{c!r}")
    imported,_=swap(rotated,prefab_bc,cap)
    final=rotate(imported,3)
    if _columns(final,cap)!=(a,b,c,d):
        raise FullReplayError(("second helper swap",_columns(final,cap),(a,b,c,d)))
    # Record the combined swap+rotation as two primitive edges.  The target A
    # moves to q1 during the rotation, so target-column checks resume after it
    # is rotated back.
    ops.append(FullOperationStep("swap_install_B_C",code(rotated),code(prefab_bc),code(imported),a,a))
    if audit and not is_stable(final):raise FullReplayError("installed helper state unstable")
    ops.append(FullOperationStep("rotate_ccw",code(imported),"",code(final),a,a))
    return final


def _restore_from_east(east, a:str, height:int, cap:int, ops:list[FullOperationStep], audit: bool = True):
    """Restore [A,T,T,T] from a stable east half [A,B]."""
    t=_tower(height)
    before=east
    prefab_tt=_rows_from_columns(("","",t,t),cap)
    first,_=swap(before,prefab_tt,cap)
    if _columns(first,cap)[:2] != _columns(before,cap)[:2]:
        raise FullReplayError("east half changed during restore")
    if audit and not is_stable(first):raise FullReplayError("first restore state unstable")
    ops.append(FullOperationStep("swap_restore_west_towers",code(before),code(prefab_tt),code(first),a,a))

    rotated=rotate(first,1)  # [T,A,B,T], preserve T,A
    ops.append(FullOperationStep("rotate_cw_restore",code(first),"",code(rotated),a,a))
    imported,_=swap(rotated,prefab_tt,cap)
    final=rotate(imported,3)
    if _columns(final,cap)!=(a,t,t,t):
        raise FullReplayError(("restore canonical",_columns(final,cap),(a,t,t,t)))
    if audit and not is_stable(final):raise FullReplayError("restored canonical state unstable")
    ops.append(FullOperationStep("swap_restore_east_tower",code(rotated),code(prefab_tt),code(imported),a,a))
    ops.append(FullOperationStep("rotate_ccw_restore",code(imported),"",code(final),a,a))
    return final


def _restore_after_c7(current, a:str, height:int, cap:int, ops:list[FullOperationStep], audit: bool = True):
    """C7's anchored A cells are supported from D, not B; preserve D,A first."""
    t=_tower(height)
    rotated=rotate(current,1)  # [D,A,B,C]
    if audit and not is_stable(rotated):raise FullReplayError("C7 rotated state unstable")
    ops.append(FullOperationStep("rotate_cw_after_C7",code(current),"",code(rotated),a,a))
    prefab_tt=_rows_from_columns(("","",t,t),cap)
    first,_=swap(rotated,prefab_tt,cap)  # [D,A,T,T]
    back=rotate(first,3)                 # [A,T,T,D]
    if audit and not is_stable(back):raise FullReplayError("C7 first restore unstable")
    ops.append(FullOperationStep("swap_after_C7_preserve_DA",code(rotated),code(prefab_tt),code(first),a,a))
    ops.append(FullOperationStep("rotate_ccw_after_C7",code(first),"",code(back),a,a))
    final,_=swap(back,prefab_tt,cap)      # [A,T,T,T]
    if _columns(final,cap)!=(a,t,t,t):
        raise FullReplayError(("C7 restore",_columns(final,cap),(a,t,t,t)))
    if audit and not is_stable(final):raise FullReplayError("C7 canonical restore unstable")
    ops.append(FullOperationStep("swap_finish_C7_restore",code(back),code(prefab_tt),code(final),a,a))
    return final


@lru_cache(maxsize=200_000)
def replay_corner_full(column_value: str, cap: int | None = None, audit_stability: bool = True) -> CornerFullReplay:
    program=compile_corner_ir(column_value,cap)
    cap=program.cap
    certificate=construct_corner(program.target,cap)
    ops:list[FullOperationStep]=[]
    current=_canonical('',1,cap,audit_stability)
    current_a=''

    for ir in program.steps:
        if ir.before != current_a:
            raise FullReplayError(("IR continuity",ir.before,current_a,ir))

        if ir.rule in (CornerRule.C1_TOP_DEPOSIT,CornerRule.C2_ANCHORED_DEPOSIT):
            assert ir.layer is not None
            support_height=max(1,len(current_a),ir.layer)
            current=_restore_from_east(current,current_a,support_height,cap,ops,audit_stability)
            if ir.rule is CornerRule.C1_TOP_DEPOSIT:
                cell=ir.after[ir.layer]
                if cell=='P':
                    pin=build_one_pin(cap,0)
                    if not pin.replay_ok:raise FullReplayError("one-pin prefab failed")
                    top=parse(pin.result,cap)
                else:
                    piece=build_single_layer_pattern(0b0001)
                    if not piece.replay_ok:raise FullReplayError("one-S prefab failed")
                    top=parse(piece.result,cap)
            else:
                piece=build_single_layer_pattern(0b0011)
                if not piece.replay_ok:raise FullReplayError("SS anchor prefab failed")
                top=parse(piece.result,cap)
            out=stack(current,top,cap)
            _record(ops,ir.rule.value,current,top,out,current_a,ir.after,audit_stability)
            current_a=ir.after
            current=_restore_from_east(out,current_a,max(1,len(current_a)),cap,ops,audit_stability)

        elif ir.rule is CornerRule.C3_GENERATE:
            current=_restore_from_east(current,current_a,max(1,len(ir.after)),cap,ops,audit_stability)
            out=generate(current,cap)
            _record(ops,ir.rule.value,current,None,out,current_a,ir.after,audit_stability)
            current=out;current_a=ir.after

        elif ir.rule is CornerRule.C4_SHATTER:
            assert ir.layer is not None
            h=max(1,len(current_a),ir.layer+1)
            current=_restore_from_east(current,current_a,h,cap,ops,audit_stability)
            helper=build_single_crystal_helper(cap,h,ir.layer,3)
            if not helper.replay_ok:raise FullReplayError("C4 helper failed")
            helper_rows=parse(helper.result,cap)
            b=_tower(h);c=_tower(h);d=column(helper_rows,3)
            installed=_install_from_canonical(current,current_a,b,c,d,cap,ops,audit_stability)
            east,_=cut(installed,cap)
            _record(ops,ir.rule.value,installed,None,east,current_a,ir.after,audit_stability)
            current_a=ir.after
            current=_restore_from_east(east,current_a,max(1,len(current_a)),cap,ops)

        elif ir.rule is CornerRule.C5_DESCEND:
            assert ir.layer is not None
            h=max(1,len(current_a),ir.layer+1)
            current=_restore_from_east(current,current_a,h,cap,ops,audit_stability)
            helper=build_pin_tower_helper(cap,h,ir.layer,1)
            if not helper.replay_ok:raise FullReplayError("C5 pin tower failed")
            helper_rows=parse(helper.result,cap)
            b=column(helper_rows,1);t=_tower(h)
            installed=_install_from_canonical(current,current_a,b,t,t,cap,ops,audit_stability)
            east,_=cut(installed,cap)
            _record(ops,ir.rule.value,installed,None,east,current_a,ir.after,audit_stability)
            current_a=ir.after
            current=_restore_from_east(east,current_a,max(1,len(current_a)),cap,ops)

        elif ir.rule is CornerRule.C6_PUSH:
            h=max(1,len(current_a))
            current=_restore_from_east(current,current_a,h,cap,ops,audit_stability)
            out=push_pin(current,cap)
            _record(ops,ir.rule.value,current,None,out,current_a,ir.after,audit_stability)
            current_a=ir.after
            current=_restore_from_east(out,current_a,max(1,len(current_a)),cap,ops,audit_stability)

        elif ir.rule is CornerRule.C7_EVENT:
            assert certificate.event is not None
            # C7's predecessor is assembled as a fresh proof-tree branch from
            # the two independently stable natural halves (B,C) and (D,A).
            # Its A column equals the natural pre-event column just constructed.
            exchange=replay_event_exchange(certificate.event)
            if not exchange.ok:
                raise FullReplayError(("C7 predecessor assembly",exchange))
            predecessor=parse(exchange.final,cap)
            if column(predecessor,0) != current_a:
                raise FullReplayError(("C7 predecessor A",column(predecessor,0),current_a))
            ops.append(FullOperationStep(
                "C7_assemble_from_BC_DA",code(current),
                exchange.prefab_bc+" | "+exchange.prefab_da,
                code(predecessor),current_a,current_a,
            ))
            out=push_pin(predecessor,cap)
            _record(ops,ir.rule.value,predecessor,None,out,current_a,ir.after,audit_stability)
            current_a=ir.after
            current=_restore_from_east(out,current_a,max(1,len(current_a)),cap,ops,audit_stability)
        else:
            raise FullReplayError(f"unsupported rule {ir.rule}")

    final_col=column(current,0)
    stable=(all(is_stable(parse(step.after,cap)) for step in ops if step.after) if audit_stability else True)
    ok=program.replay_ok and stable and final_col==program.target
    return CornerFullReplay(program.target,cap,tuple(ops),code(current),final_col,stable,ok)


__all__=["FullOperationStep","CornerFullReplay","FullReplayError","replay_corner_full"]
