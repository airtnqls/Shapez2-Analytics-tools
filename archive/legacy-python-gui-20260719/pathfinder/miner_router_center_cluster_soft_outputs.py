from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

Cell = Tuple[int, int]
Node = Tuple[int, int, int]


@dataclass(frozen=True)
class Miner:
    id: int
    cells: Tuple[Cell, ...]
    output: Cell
    demand: int
    port: Cell
    phase: str = "outer"  # "outer" = 1F shell miner, "inner" = elevator miner


def neighbors4(c: Cell):
    x, y = c
    yield x + 1, y
    yield x - 1, y
    yield x, y + 1
    yield x, y - 1


def neighbors8(c: Cell):
    x, y = c
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy


def in_bounds(c: Cell, w: int, h: int) -> bool:
    x, y = c
    return 0 <= x < w and 0 <= y < h


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# Final output behavior:
# - All top columns are legal final outputs; there is no hard 7-lane bank limit.
# - The router score strongly prefers a compact group around the grid center.
# - New lanes open near the existing output cluster only after opened lanes are near/full.
OUTPUT_TARGET_SPACING = 1


def make_sink_ports(w: int, count: int = 7, y: int = -1) -> List[Cell]:
    """Return every top column as a legal final output.

    This removes the previous hard 7-output limit.  Actual routing still uses a
    soft center preference through preferred_direct_ports() and output scoring, so
    used outputs gather near the middle instead of scattering across the edge.
    """
    return [(x, y) for x in range(max(1, w))]


def centered_output_band(w: int, desired: int = 15) -> List[int]:
    """Preferred center band for direct exits/collector trunks. Not a hard output list."""
    w = max(1, w)
    desired = max(1, min(w, desired))
    start = max(0, (w - desired) // 2)
    return list(range(start, min(w, start + desired)))


def preferred_direct_ports(ports: List[Cell], w: int, desired: int = 31) -> List[Cell]:
    """Prefer direct final exits in a centered band while keeping all ports legal for fallback/metadata."""
    if not ports:
        return []
    band = set(centered_output_band(w, desired=max(9, min(w, desired))))
    preferred = [p for p in ports if p[0] in band]
    return preferred or ports

def make_blob_resources(w: int, h: int, seed: int = 12) -> Set[Cell]:
    rng = random.Random(seed)
    # The demo resource field is generated in a 30x32 "logical" area, then
    # shifted into the middle of the current grid.  The extra empty margin is
    # important for the two-stage routing model: local 4-way collector ring
    # around each cluster, then larger-space collector routes to the global top output.
    ox = max(0, (w - 30) // 2)
    oy = max(0, (h - 32) // 2)
    centers = [(10 + ox, 8 + oy, 5.7), (15 + ox, 14 + oy, 6.0), (9 + ox, 19 + oy, 5.2), (19 + ox, 22 + oy, 4.5), (22 + ox, 11 + oy, 3.3)]
    resources: Set[Cell] = set()
    for y in range(h):
        for x in range(w):
            score = 0.0
            for cx, cy, r in centers:
                d = math.hypot(x - cx, y - cy)
                score += max(0.0, 1.0 - d / r)
            score += rng.uniform(-0.16, 0.13)
            if score > 0.23:
                resources.add((x, y))
    for c in list(resources):
        if rng.random() < 0.06:
            resources.remove(c)
    return resources


BASE_SHAPES = [
    ((0,0),(1,0),(2,0),(3,0)),
    ((0,0),(0,1),(0,2),(0,3)),
    ((0,0),(1,0),(0,1),(1,1)),
    ((0,0),(0,1),(0,2),(1,2)),
    ((1,0),(1,1),(1,2),(0,2)),
    ((0,0),(1,0),(2,0),(0,1)),
    ((0,0),(1,0),(2,0),(2,1)),
    ((0,0),(1,0),(2,0),(1,1)),
    ((1,0),(0,1),(1,1),(2,1)),
    ((0,0),(1,0),(1,1),(2,1)),
    ((1,0),(2,0),(0,1),(1,1)),
    ((0,0),(1,0),(2,0)),
    ((0,0),(0,1),(0,2)),
    ((0,0),(1,0),(0,1)),
    ((0,0),(1,0),(1,1)),
    ((0,0),(0,1),(1,1)),
    ((1,0),(0,1),(1,1)),
    ((0,0),(1,0)),
    ((0,0),(0,1)),
    ((0,0),),
]


def normalize_shape(shape: Iterable[Cell]) -> Tuple[Cell, ...]:
    pts = list(shape)
    minx = min(x for x, y in pts)
    miny = min(y for x, y in pts)
    return tuple(sorted((x - minx, y - miny) for x, y in pts))


def transforms(shape: Tuple[Cell, ...]) -> Set[Tuple[Cell, ...]]:
    out: Set[Tuple[Cell, ...]] = set()
    for reflect in (1, -1):
        for rot in range(4):
            pts = []
            for x, y in shape:
                x *= reflect
                if rot == 0:
                    p = (x, y)
                elif rot == 1:
                    p = (-y, x)
                elif rot == 2:
                    p = (-x, -y)
                else:
                    p = (y, -x)
                pts.append(p)
            out.add(normalize_shape(pts))
    return out


SHAPES = sorted({s for base in BASE_SHAPES for s in transforms(tuple(base))}, key=lambda s: (-len(s), s))


def is_line_shape(cells: Set[Cell]) -> bool:
    if len(cells) <= 1:
        return True
    return len({x for x, y in cells}) == 1 or len({y for x, y in cells}) == 1


def connected_components(cells: Set[Cell]) -> List[Set[Cell]]:
    left = set(cells)
    comps: List[Set[Cell]] = []
    while left:
        start = left.pop()
        comp = {start}
        q = deque([start])
        while q:
            c = q.popleft()
            for n in neighbors4(c):
                if n in left:
                    left.remove(n)
                    comp.add(n)
                    q.append(n)
        comps.append(comp)
    comps.sort(key=lambda c: (-len(c), min(c)))
    return comps


def shell_depths(component: Set[Cell], w: int, h: int) -> Dict[Cell, int]:
    """0 = outer outline, larger = deeper inside the resource cluster."""
    q = deque()
    depth: Dict[Cell, int] = {}
    for c in component:
        boundary = any((not in_bounds(n, w, h)) or (n not in component) for n in neighbors4(c))
        if boundary:
            depth[c] = 0
            q.append(c)
    if not q:
        # Should not happen for finite grid components, but keep it safe.
        c = next(iter(component))
        depth[c] = 0
        q.append(c)
    while q:
        c = q.popleft()
        for n in neighbors4(c):
            if n in component and n not in depth:
                depth[n] = depth[c] + 1
                q.append(n)
    return depth


def exterior_shell_depths(component: Set[Cell], w: int, h: int) -> Dict[Cell, int]:
    """0 = true exterior outline only; enclosed holes do not count as the outer shell."""
    # Flood-fill empty space connected to outside the grid on an expanded rectangle.
    minx, maxx = -1, w
    miny, maxy = -1, h
    start = (-1, -1)
    outside_air: Set[Cell] = {start}
    q = deque([start])
    while q:
        c = q.popleft()
        for n in neighbors4(c):
            x, y = n
            if x < minx or x > maxx or y < miny or y > maxy:
                continue
            if n in outside_air or n in component:
                continue
            outside_air.add(n)
            q.append(n)

    depth: Dict[Cell, int] = {}
    q2 = deque()
    for c in component:
        if any(n in outside_air for n in neighbors4(c)):
            depth[c] = 0
            q2.append(c)

    if not q2:
        # Fallback to the older local-boundary definition.
        return shell_depths(component, w, h)

    while q2:
        c = q2.popleft()
        for n in neighbors4(c):
            if n in component and n not in depth:
                depth[n] = depth[c] + 1
                q2.append(n)
    return depth


def resource_neighbor_score(cells: Iterable[Cell], resource_space: Set[Cell]) -> int:
    return sum(1 for c in cells for n in neighbors8(c) if n in resource_space)


def road_cells_on_floor(road_load: Dict[Node, int], floor: int, include_outside: bool = False) -> Set[Cell]:
    return {(x, y) for (x, y, z) in road_load if z == floor and (include_outside or y >= 0)}


def successor_chain(start: Node, successor: Dict[Node, Node], limit: int = 5000) -> List[Node]:
    chain = [start]
    seen = {start}
    cur = start
    while cur in successor:
        cur = successor[cur]
        if cur in seen:
            break
        chain.append(cur)
        seen.add(cur)
        if len(chain) >= limit:
            break
    return chain


def downstream_has_capacity(target: Node, successor: Dict[Node, Node], road_load: Dict[Node, int], demand: int, cap: int) -> bool:
    return all(road_load.get(n, 0) + demand <= cap for n in successor_chain(target, successor))

def downstream_is_single_floor(target: Node, successor: Dict[Node, Node], floor: int) -> bool:
    return all(n[2] == floor for n in successor_chain(target, successor))


def downstream_output(target: Node, successor: Dict[Node, Node], ports: Set[Cell]) -> Optional[Tuple[Cell, int]]:
    for n in successor_chain(target, successor):
        c = (n[0], n[1])
        if c in ports:
            return c, n[2]
    return None


def output_floor_compatible(port: Cell, floor: int, output_floors: Dict[Cell, int]) -> bool:
    old = output_floors.get(port)
    return old is None or old == floor


def output_floor_from_path(path: List[Node], port: Cell) -> Optional[int]:
    for n in reversed(path):
        if (n[0], n[1]) == port:
            return n[2]
    return None

def output_cluster_penalty(port: Cell, out_used: Dict[Cell, int]) -> int:
    """Lower is better.  Soft-center, compact, 32-fill output scoring.

    Meaning of "outputs gather": actual used exits should sit near the center and
    next to each other, while each opened lane is filled toward cap=32 before
    another lane is opened.  All columns remain legal; this is not a hard bank.
    """
    cap = 32
    demand_hint = 4
    same = out_used.get(port, 0)
    all_xs = [p[0] for p in out_used] or [port[0]]
    grid_center = (min(all_xs) + max(all_xs)) / 2.0
    center_penalty = abs(port[0] - grid_center) * 1800

    used = [(p, load) for p, load in out_used.items() if load > 0]
    if not used:
        # First opened output: choose the middle column unless a path is vastly easier elsewhere.
        return int(center_penalty)

    used_xs = [p[0] for p, _ in used]
    active_center = sum(used_xs) / len(used_xs)
    nearest_used_dist = min(abs(port[0] - p[0]) + abs(port[1] - p[1]) for p, _ in used)
    active_cluster_penalty = abs(port[0] - active_center) * 900 + nearest_used_dist * 900

    if same > 0 and same < cap:
        # Always prefer continuing to fill an already-open lane.  The closer it is
        # to 32 after adding one miner, the lower the cost.
        fullness_reward = (cap - min(cap, same + demand_hint)) * 8
        return int(fullness_reward + center_penalty * 0.05)

    viable_existing = [(p, load) for p, load in used if load < cap]
    if viable_existing:
        # Opening a new lane while some active lane is still not full should be very
        # expensive, but not impossible if geometry absolutely demands it.
        nearest_open = min(abs(port[0] - p[0]) + abs(port[1] - p[1]) for p, _ in viable_existing)
        return int(90000 + nearest_open * 3000 + center_penalty * 0.4 + active_cluster_penalty)

    # All active lanes are full. Open the next lane adjacent to the existing center cluster,
    # not far away.  Adjacent center lanes are best; far edge lanes are strongly discouraged.
    nearest_full = min(abs(port[0] - p[0]) + abs(port[1] - p[1]) for p, _ in used)
    spacing_penalty = abs(nearest_full - OUTPUT_TARGET_SPACING) * 2500
    far_cluster_penalty = active_cluster_penalty * 2.0
    return int(spacing_penalty + center_penalty * 0.7 + far_cluster_penalty)


def target_output_cluster_penalty(
    target: Node,
    successor: Dict[Node, Node],
    ports: Set[Cell],
    out_used: Dict[Cell, int],
) -> int:
    c = (target[0], target[1])
    if c in ports:
        return output_cluster_penalty(c, out_used)
    out = downstream_output(target, successor, ports)
    if out is None:
        return 9999
    return output_cluster_penalty(out[0], out_used)


def can_commit_path(path: List[Node], successor: Dict[Node, Node]) -> bool:
    # One road cell may have many inputs, but only one output direction. This allows merge, forbids split/T-branch.
    for a, b in zip(path, path[1:]):
        old = successor.get(a)
        if old is not None and old != b:
            return False
    return True


def commit_path_successors(path: List[Node], successor: Dict[Node, Node]) -> None:
    for a, b in zip(path, path[1:]):
        successor.setdefault(a, b)


def append_chain_without_duplicate(path: List[Node], chain: List[Node]) -> List[Node]:
    if not chain:
        return path
    if path and path[-1] == chain[0]:
        return path + chain[1:]
    return path + chain


def route_1f_to_output(
    start_cell: Cell,
    ports: List[Cell],
    w: int,
    h: int,
    blocked_1f: Set[Cell],
    road_load: Dict[Node, int],
    successor: Dict[Node, Node],
    demand: int,
    cap: int,
    output_floors: Dict[Cell, int],
    out_used: Dict[Cell, int],
) -> Optional[Tuple[Cell, List[Node], List[Node], int]]:
    """Pure 1F router. Existing roads are final merge targets only; after merge, follow their successor."""
    port_set = set(ports)
    start = (start_cell[0], start_cell[1], 0)

    def direct_port_nodes() -> Set[Node]:
        out = set()
        for p in preferred_direct_ports(ports, w):
            if out_used.get(p, 0) + demand > cap:
                continue
            if not output_floor_compatible(p, 0, output_floors):
                continue
            n = (p[0], p[1], 0)
            if road_load.get(n, 0) + demand <= cap:
                out.add(n)
        return out

    direct_targets = direct_port_nodes()

    merge_targets: Set[Node] = set()
    for n in road_load:
        x, y, z = n
        if z != 0 or y < 0:
            continue
        if (x, y) in blocked_1f and (x, y) != start_cell:
            continue
        out = downstream_output(n, successor, port_set)
        if out is None:
            continue
        out_port, out_floor = out
        if out_used.get(out_port, 0) + demand > cap:
            continue
        if not output_floor_compatible(out_port, out_floor, output_floors):
            continue
        if not downstream_is_single_floor(n, successor, 0):
            continue
        if downstream_has_capacity(n, successor, road_load, demand, cap):
            merge_targets.add(n)

    targets = direct_targets | merge_targets
    if not targets:
        return None

    # If the miner output is already touching an existing road, simply merge and follow it if possible.
    if start in merge_targets:
        chain = successor_chain(start, successor)
        out = downstream_output(start, successor, port_set)
        if out is not None:
            port, floor = out
            full = chain
            if can_commit_path(full, successor):
                return port, full, full, floor

    def in_route_bounds(c: Cell) -> bool:
        x, y = c
        return 0 <= x < w and -1 <= y < h

    def valid(n: Node, as_target: bool = False) -> bool:
        x, y, z = n
        if z != 0:
            return False
        if not in_route_bounds((x, y)):
            return False
        if y == -1:
            return n in direct_targets and road_load.get(n, 0) + demand <= cap
        c = (x, y)
        if c in blocked_1f and c != start_cell:
            return False
        if road_load.get(n, 0) + demand > cap:
            return False
        # Same-floor roads cannot cross/pass-through. They can only be final merge targets.
        if n in road_load and n != start and not as_target:
            return False
        return True

    if not valid(start):
        return None

    target_penalty = {t: target_output_cluster_penalty(t, successor, port_set, out_used) for t in targets}

    def heuristic(n: Node) -> int:
        x, y, _ = n
        return min(abs(x - t[0]) + abs(y - t[1]) + pen for t, pen in target_penalty.items())

    pq: List[Tuple[int, int, Node]] = [(heuristic(start), 0, start)]
    came: Dict[Node, Optional[Node]] = {start: None}
    best: Dict[Node, int] = {start: 0}

    while pq:
        _, cost, cur = heapq.heappop(pq)
        if cost != best.get(cur):
            continue

        if cur in targets and cur != start:
            path: List[Node] = []
            p: Optional[Node] = cur
            while p is not None:
                path.append(p)
                p = came[p]
            path.reverse()

            if cur in merge_targets:
                chain = successor_chain(cur, successor)
                out = downstream_output(cur, successor, port_set)
                if out is None:
                    continue
                port, floor = out
                full = append_chain_without_duplicate(path, chain)
                if not can_commit_path(full, successor):
                    continue
                return port, full, full, floor

            port = (cur[0], cur[1])
            if port not in port_set:
                continue
            floor = cur[2]
            if not output_floor_compatible(port, floor, output_floors):
                continue
            if not can_commit_path(path, successor):
                continue
            return port, path, path, floor

        x, y, z = cur
        if y == -1:
            continue
        for nx, ny in neighbors4((x, y)):
            # Top pass row is only reachable from y=0 in the same x column.
            if ny < -1:
                continue
            nn = (nx, ny, 0)
            as_target = nn in targets
            if not valid(nn, as_target=as_target):
                continue
            step = 1
            if nn in merge_targets:
                step = 0
            if ny == -1:
                # Real cost, not just heuristic: center-clustered/full outputs are cheaper.
                step = max(0, 4 - min(4, out_used.get((nx, ny), 0) // 8))
            ng = cost + step
            if ng < best.get(nn, 10**9):
                best[nn] = ng
                came[nn] = cur
                heapq.heappush(pq, (ng + heuristic(nn), ng, nn))
    return None


def is_floor_switch_edge(a: Node, b: Node) -> bool:
    return a[0] == b[0] and a[1] == b[1] and a[2] != b[2]


def can_floor_switch_cell(
    c: Cell,
    w: int,
    h: int,
    resources: Set[Cell],
    blocked_1f: Set[Cell],
    elevator_cells: Set[Cell],
    own_elevator: Cell,
    road_load: Dict[Node, int],
) -> bool:
    if not in_bounds(c, w, h):
        return False
    # The miner's own elevator is only the initial 1F->2F lift.
    # Do not let the same node later drop back to 1F; that creates a split at the same node.
    if c == own_elevator:
        return False

    # CRITICAL SINGLE-LINE RULE:
    # A floor switch itself must never be a merge point with an already-built road.
    # In other words, (x,y,2F)->(x,y,1F) cannot land directly on an existing 1F road,
    # and (x,y,1F)->(x,y,2F) cannot land directly on an existing 2F road.
    # Switch first on a clean elevator cell, then move one cell and merge normally.
    if (c[0], c[1], 0) in road_load or (c[0], c[1], 1) in road_load:
        return False

    if c in elevator_cells:
        return False
    if c in resources:
        return False
    if c in blocked_1f:
        return False
    return True


def path_has_ramp_merge_violation(path: List[Node], preexisting_roads: Set[Node]) -> bool:
    """Hard ramp isolation rule.

    A floor switch is not just a graph edge; physically it is an elevator column.
    Therefore it must not be the same action as a merge, and it also needs a small
    same-floor clearance before touching an already-built road.  This catches the
    intermittent inner-miner cases where the path looked valid in the graph but
    rendered as a T-merge at the elevator.
    """
    if not preexisting_roads:
        return False
    switch_indices: Set[int] = set()
    switch_cells: Set[Cell] = set()
    for i, (a, b) in enumerate(zip(path, path[1:])):
        if is_floor_switch_edge(a, b):
            switch_indices.add(i)
            switch_indices.add(i + 1)
            switch_cells.add((a[0], a[1]))
    if not switch_indices:
        return False

    # Existing road on the elevator column itself is always illegal.
    for x, y, z in preexisting_roads:
        if (x, y) in switch_cells:
            return True

    # The first contact with existing road must not be too close to a floor switch.
    # Clearance 2 means: switch, move at least two nodes away, then merge.
    min_clear_nodes = 2
    for i, n in enumerate(path):
        if n not in preexisting_roads:
            continue
        if any(abs(i - si) <= min_clear_nodes for si in switch_indices):
            return True
    return False


def route_inner_elevator(
    elevator: Cell,
    ports: List[Cell],
    w: int,
    h: int,
    resources: Set[Cell],
    blocked_1f: Set[Cell],
    road_load: Dict[Node, int],
    successor: Dict[Node, Node],
    elevator_cells: Set[Cell],
    demand: int,
    cap: int,
    output_floors: Dict[Cell, int],
    out_used: Dict[Cell, int],
) -> Optional[Tuple[Cell, List[Node], List[Node], int, Set[Cell]]]:
    """
    Inner miner router:
    1) starts by mandatory elevator: 1F -> 2F at the miner output cell.
    2) strongly prefers leaving resource-covered cells.
    3) prefers dropping back to 1F and merging into the original 1F road tree, but can stay on 2F if needed.
    """
    port_set = set(ports)
    start2 = (elevator[0], elevator[1], 1)
    start0 = (elevator[0], elevator[1], 0)

    direct_targets: Set[Node] = set()
    for p in preferred_direct_ports(ports, w):
        if out_used.get(p, 0) + demand > cap:
            continue
        for floor in (0, 1):
            if not output_floor_compatible(p, floor, output_floors):
                continue
            n = (p[0], p[1], floor)
            if road_load.get(n, 0) + demand <= cap:
                direct_targets.add(n)

    merge_targets: Set[Node] = set()
    for n in road_load:
        x, y, z = n
        if y < 0:
            continue
        # Do not merge into 2F road that is still over a resource cell; first goal is escaping resources.
        if z == 1 and (x, y) in resources:
            continue
        # Never use someone else's elevator space.
        if (x, y) in elevator_cells and (x, y) != elevator:
            continue
        out = downstream_output(n, successor, port_set)
        if out is None:
            continue
        out_port, out_floor = out
        if out_used.get(out_port, 0) + demand > cap:
            continue
        if not output_floor_compatible(out_port, out_floor, output_floors):
            continue
        if downstream_has_capacity(n, successor, road_load, demand, cap):
            merge_targets.add(n)

    targets = direct_targets | merge_targets
    if not targets:
        return None

    def in_route_bounds(c: Cell) -> bool:
        x, y = c
        return 0 <= x < w and -1 <= y < h

    def valid(n: Node, as_target: bool = False) -> bool:
        x, y, z = n
        if not in_route_bounds((x, y)):
            return False
        if y == -1:
            return n in direct_targets and road_load.get(n, 0) + demand <= cap
        c = (x, y)
        if c in elevator_cells and c != elevator:
            return False
        if z == 0:
            if c in resources and c != elevator:
                return False
            if c in blocked_1f and c != elevator:
                return False
        else:
            # 2F may pass above resources/miners, but not through elevator columns.
            pass
        if road_load.get(n, 0) + demand > cap:
            return False
        # Same-floor road can only be the final merge target, never crossed.
        if n in road_load and n not in (start0, start2) and not as_target:
            return False
        return True

    if not valid(start2):
        return None

    def target_bias(t: Node) -> int:
        # Prefer 1F road merge, then 1F direct output, then 2F merge, then 2F direct output.
        if t in merge_targets and t[2] == 0:
            return 0
        if t in direct_targets and t[2] == 0:
            return 3
        if t in merge_targets and t[2] == 1:
            return 6
        return 12

    target_penalty = {t: target_bias(t) + target_output_cluster_penalty(t, successor, port_set, out_used) for t in targets}

    def heuristic(n: Node) -> int:
        x, y, z = n
        return min(abs(x - t[0]) + abs(y - t[1]) + pen for t, pen in target_penalty.items())

    pq: List[Tuple[int, int, Node]] = [(heuristic(start2), 0, start2)]
    came: Dict[Node, Optional[Node]] = {start2: None}
    best: Dict[Node, int] = {start2: 0}

    while pq:
        _, cost, cur = heapq.heappop(pq)
        if cost != best.get(cur):
            continue

        if cur in targets and cur != start2:
            path2: List[Node] = []
            p: Optional[Node] = cur
            while p is not None:
                path2.append(p)
                p = came[p]
            path2.reverse()
            path = [start0] + path2

            if cur in merge_targets:
                chain = successor_chain(cur, successor)
                out = downstream_output(cur, successor, port_set)
                if out is None:
                    continue
                port, floor = out
                full = append_chain_without_duplicate(path, chain)
                if path_has_ramp_merge_violation(full, set(road_load)):
                    continue
                if not can_commit_path(full, successor):
                    continue
                ramp_cells = {elevator}
                for a, b in zip(full, full[1:]):
                    if (a[0], a[1]) == (b[0], b[1]) and a[2] != b[2]:
                        ramp_cells.add((a[0], a[1]))
                return port, full, full, floor, ramp_cells

            port = (cur[0], cur[1])
            if port not in port_set:
                continue
            floor = cur[2]
            if not output_floor_compatible(port, floor, output_floors):
                continue
            if path_has_ramp_merge_violation(path, set(road_load)):
                continue
            if not can_commit_path(path, successor):
                continue
            ramp_cells = {elevator}
            for a, b in zip(path, path[1:]):
                if (a[0], a[1]) == (b[0], b[1]) and a[2] != b[2]:
                    ramp_cells.add((a[0], a[1]))
            return port, path, path, floor, ramp_cells

        x, y, z = cur
        if y == -1:
            continue

        nxt: List[Node] = []
        for nx, ny in neighbors4((x, y)):
            if ny < -1:
                continue
            nxt.append((nx, ny, z))

        # Optional 2F -> 1F return elevator. Rewarded when on non-resource/non-blocked cell.
        c = (x, y)
        if can_floor_switch_cell(c, w, h, resources, blocked_1f, elevator_cells, elevator, road_load):
            nxt.append((x, y, 1 - z))

        for nn in nxt:
            is_switch = is_floor_switch_edge(cur, nn)
            # A ramp/elevator cannot be the merge target itself.
            # The landing/takeoff coordinate must be clean; after landing, a normal same-floor move
            # may merge into an existing road on the next cell. This preserves the single-line rule.
            if is_switch and (nn in road_load or cur in road_load or nn in targets):
                continue
            as_target = nn in targets
            if not valid(nn, as_target=as_target):
                continue
            nx, ny, nz = nn
            step = 1
            if (nx, ny) == (x, y) and nz != z:
                step = 1 if z == 1 and nz == 0 else 5
            elif nz == 1:
                step = 2
                if ny >= 0 and (nx, ny) in resources:
                    step += 8  # escape resource-covered 2F cells ASAP
            else:
                step = 1
            if nn in merge_targets:
                step = 0 if nn[2] == 0 else 1
            if ny == -1:
                step += 0 if nz == 0 else 8
            ng = cost + max(0, step)
            if ng < best.get(nn, 10**9):
                best[nn] = ng
                came[nn] = cur
                heapq.heappush(pq, (ng + heuristic(nn), ng, nn))

    return None


def route_3d_to_output(
    start_cell: Cell,
    ports: List[Cell],
    w: int,
    h: int,
    resources: Set[Cell],
    blocked_1f: Set[Cell],
    road_load: Dict[Node, int],
    successor: Dict[Node, Node],
    elevator_cells: Set[Cell],
    demand: int,
    cap: int,
    output_floors: Dict[Cell, int],
    out_used: Dict[Cell, int],
    prefer_floor0: bool = True,
) -> Optional[Tuple[Cell, List[Node], List[Node], int, Set[Cell]]]:
    """General 3D router for any miner output.

    This is the important escape hatch for outer miners too:
    - Start on 1F at the miner output cell.
    - Prefer pure 1F routes, but if 1F is blocked, use clean elevator/ramp cells to go 1F<->2F.
    - 2F may pass above resources/miners, but ramp cells themselves must be clean on both floors.
    - Existing same-floor roads are merge targets only; after merging, the route follows their successor chain.
    - A floor switch cannot be the merge point itself.  Switch first on a clean cell, move, then merge.
    """
    port_set = set(ports)
    start = (start_cell[0], start_cell[1], 0)

    def in_route_bounds(c: Cell) -> bool:
        x, y = c
        return 0 <= x < w and -1 <= y < h

    def clean_switch_cell(c: Cell) -> bool:
        if not in_bounds(c, w, h):
            return False
        # A ramp occupies both floors and must not be an existing road, miner/resource cell,
        # or another elevator column.  This also prevents elevator-T merge by construction.
        if (c[0], c[1], 0) in road_load or (c[0], c[1], 1) in road_load:
            return False
        if c in elevator_cells:
            return False
        if c in resources:
            return False
        if c in blocked_1f and c != start_cell:
            return False
        return True

    # Direct final top outputs on either floor.  1F is cheaper, 2F is allowed only when the
    # output lane is not already locked to 1F.
    direct_targets: Set[Node] = set()
    for p in preferred_direct_ports(ports, w):
        if out_used.get(p, 0) + demand > cap:
            continue
        for floor in (0, 1):
            if not output_floor_compatible(p, floor, output_floors):
                continue
            n = (p[0], p[1], floor)
            if road_load.get(n, 0) + demand <= cap:
                direct_targets.add(n)

    # Merge into any legal existing single-output road, on either floor.
    merge_targets: Set[Node] = set()
    for n in road_load:
        x, y, z = n
        if y < 0:
            continue
        c = (x, y)
        if c in elevator_cells:
            continue
        if z == 0 and c in blocked_1f and c != start_cell:
            # 1F road through another miner/resource/elevator is not a legal new merge point.
            continue
        out = downstream_output(n, successor, port_set)
        if out is None:
            continue
        out_port, out_floor = out
        if out_used.get(out_port, 0) + demand > cap:
            continue
        if not output_floor_compatible(out_port, out_floor, output_floors):
            continue
        if downstream_has_capacity(n, successor, road_load, demand, cap):
            merge_targets.add(n)

    targets = direct_targets | merge_targets
    if not targets:
        return None

    # Immediate merge if the output cell is already a legal road node.
    if start in merge_targets:
        chain = successor_chain(start, successor)
        out = downstream_output(start, successor, port_set)
        if out is not None:
            port, floor = out
            if can_commit_path(chain, successor):
                return port, chain, chain, floor, set()

    def valid(n: Node, as_target: bool = False) -> bool:
        x, y, z = n
        if z not in (0, 1):
            return False
        if not in_route_bounds((x, y)):
            return False
        if y == -1:
            return n in direct_targets and road_load.get(n, 0) + demand <= cap
        c = (x, y)
        if c in elevator_cells:
            return False
        if z == 0:
            # 1F cannot pass through real occupied cells.  Existing 1F roads are only final merge targets.
            if c in blocked_1f and c != start_cell:
                return False
        else:
            # 2F may pass above resources/miners, but never through elevator columns.
            pass
        if road_load.get(n, 0) + demand > cap:
            return False
        if n in road_load and n != start and not as_target:
            return False
        return True

    if not valid(start):
        return None

    def target_bias(t: Node) -> int:
        # Prefer returning to the normal 1F collector/trunk, but allow 2F emergency routes.
        if t in merge_targets and t[2] == 0:
            return 0
        if t in direct_targets and t[2] == 0:
            return 5
        if t in merge_targets and t[2] == 1:
            return 12
        return 24

    target_penalty = {t: target_bias(t) + target_output_cluster_penalty(t, successor, port_set, out_used) for t in targets}

    def heuristic(n: Node) -> int:
        x, y, z = n
        return min(abs(x - t[0]) + abs(y - t[1]) + (0 if z == t[2] else 2) + pen for t, pen in target_penalty.items())

    pq: List[Tuple[int, int, Node]] = [(heuristic(start), 0, start)]
    came: Dict[Node, Optional[Node]] = {start: None}
    best: Dict[Node, int] = {start: 0}

    while pq:
        _, cost, cur = heapq.heappop(pq)
        if cost != best.get(cur):
            continue

        if cur in targets and cur != start:
            path: List[Node] = []
            p: Optional[Node] = cur
            while p is not None:
                path.append(p)
                p = came[p]
            path.reverse()

            if cur in merge_targets:
                chain = successor_chain(cur, successor)
                out = downstream_output(cur, successor, port_set)
                if out is None:
                    continue
                port, floor = out
                full = append_chain_without_duplicate(path, chain)
                if path_has_ramp_merge_violation(full, set(road_load)):
                    continue
                if not can_commit_path(full, successor):
                    continue
                ramp_cells = { (a[0], a[1]) for a, b in zip(full, full[1:]) if is_floor_switch_edge(a, b) }
                return port, full, full, floor, ramp_cells

            port = (cur[0], cur[1])
            if port not in port_set:
                continue
            floor = cur[2]
            if not output_floor_compatible(port, floor, output_floors):
                continue
            if path_has_ramp_merge_violation(path, set(road_load)):
                continue
            if not can_commit_path(path, successor):
                continue
            ramp_cells = { (a[0], a[1]) for a, b in zip(path, path[1:]) if is_floor_switch_edge(a, b) }
            return port, path, path, floor, ramp_cells

        x, y, z = cur
        if y == -1:
            continue

        nxt: List[Node] = []
        for nx, ny in neighbors4((x, y)):
            if ny < -1:
                continue
            nxt.append((nx, ny, z))

        c = (x, y)
        if clean_switch_cell(c):
            nxt.append((x, y, 1 - z))

        for nn in nxt:
            is_switch = is_floor_switch_edge(cur, nn)
            if is_switch:
                # Floor switch must be a clean elevator action, never the merge action itself.
                if cur in road_load or nn in road_load or cur in targets or nn in targets:
                    continue
            as_target = nn in targets
            if not valid(nn, as_target=as_target):
                continue

            nx, ny, nz = nn
            if is_switch:
                # Going up is a costlier escape; coming down is preferred once a clean landing exists.
                step = 8 if z == 0 and nz == 1 else 2
            elif nz == 1:
                step = 3
                if ny >= 0 and (nx, ny) in resources:
                    step += 2
                if ny >= 0 and (nx, ny) in blocked_1f:
                    step += 1
            else:
                step = 1

            if nn in merge_targets:
                step = 0 if nn[2] == 0 else 2
            if ny == -1:
                step += 0 if nz == 0 else 10
            if prefer_floor0 and nz == 1:
                step += 1

            ng = cost + max(0, step)
            if ng < best.get(nn, 10**9):
                best[nn] = ng
                came[nn] = cur
                heapq.heappush(pq, (ng + heuristic(nn), ng, nn))

    return None



def candidate_groups_for_anchor_no_output(
    anchor: Cell,
    available: Set[Cell],
    component: Set[Cell],
    depths: Dict[Cell, int],
    shell: int,
    occupied_1f: Set[Cell],
    w: int,
    h: int,
) -> List[Tuple[int, Tuple[Cell, ...], int]]:
    """Miner-cell candidates only. No road/output reservation here.

    This is the important ordering fix: shell miner cells are selected first, without
    letting already-routed roads block later shell miners. The output road is chosen later.
    """
    if anchor not in available or anchor in occupied_1f or depths.get(anchor) != shell:
        return []

    groups_seen: Set[Tuple[Cell, ...]] = set()
    out: List[Tuple[int, Tuple[Cell, ...], int]] = []

    for shape in SHAPES:
        # Align every shape cell to the anchor so the group definitely covers the shell cell.
        for sx, sy in shape:
            ox, oy = anchor[0] - sx, anchor[1] - sy
            g = tuple(sorted((ox + dx, oy + dy) for dx, dy in shape))
            if g in groups_seen:
                continue
            groups_seen.add(g)
            if not all(c in available and c not in occupied_1f for c in g):
                continue
            if not all(c in component for c in g):
                continue
            if anchor not in g:
                continue

            gs = set(g)
            demand = len(g)
            neigh = resource_neighbor_score(g, component)
            avg_depth = sum(depths.get(c, 0) for c in g) / max(1, demand)
            max_depth = max(depths.get(c, 0) for c in g)
            line = is_line_shape(gs)
            compact = sum(1 for c in gs for n in neighbors4(c) if n in gs)

            # The group must touch the current shell, but should extend inward when possible.
            # Surrounding-resource density and deeper included cells are rewarded.
            score = (
                demand * 100000
                + int(avg_depth * 3500)
                + max_depth * 1800
                + neigh * 700
                + compact * 120
                + (300 if line else 0)
            )
            out.append((score, g, demand))

    out.sort(reverse=True, key=lambda x: x[0])
    return out



def candidate_inner_groups_for_anchor_no_route(
    anchor: Cell,
    available: Set[Cell],
    component: Set[Cell],
    depths: Dict[Cell, int],
    occupied_1f: Set[Cell],
    w: int,
    h: int,
) -> List[Tuple[int, Tuple[Cell, ...], Cell, int]]:
    """Inner miner candidates with mandatory elevator, but no routing/road dependence.

    This is intentionally anchor-based and fast. It prevents the older behavior where
    inner placement repeatedly regenerated every candidate and then stopped after routing
    failures. Here we only reserve miner/elevator cells; roads come later.
    """
    if anchor not in available or anchor in occupied_1f:
        return []

    groups_seen: Set[Tuple[Cell, ...]] = set()
    out: List[Tuple[int, Tuple[Cell, ...], Cell, int]] = []

    for shape in SHAPES:
        for sx, sy in shape:
            ox, oy = anchor[0] - sx, anchor[1] - sy
            g = tuple(sorted((ox + dx, oy + dy) for dx, dy in shape))
            if g in groups_seen:
                continue
            groups_seen.add(g)
            if anchor not in g:
                continue
            if not all(c in available and c not in occupied_1f and c in component for c in g):
                continue

            gs = set(g)
            elevator_candidates: Set[Cell] = set()
            for c in gs:
                for n in neighbors4(c):
                    if not in_bounds(n, w, h):
                        continue
                    if n in gs or n in occupied_1f:
                        continue
                    # Elevator may be empty or may sacrifice one still-available resource.
                    elevator_candidates.add(n)

            if not elevator_candidates:
                continue

            demand = len(g)
            neigh = resource_neighbor_score(g, component)
            avg_depth = sum(depths.get(c, 0) for c in g) / max(1, demand)
            max_depth = max(depths.get(c, 0) for c in g)
            compact = sum(1 for c in gs for n in neighbors4(c) if n in gs)
            line = is_line_shape(gs)

            for elevator in elevator_candidates:
                sacrifice = 1 if elevator in available else 0
                # Deep and surrounded is preferred; sacrificing a resource for an elevator is allowed
                # but lower-scored so empty adjacent holes are used first when available.
                score = (
                    demand * 100000
                    + int(avg_depth * 4500)
                    + max_depth * 2500
                    + neigh * 750
                    + compact * 120
                    + (250 if line else 0)
                    - sacrifice * 3200
                )
                out.append((score, g, elevator, demand))

    out.sort(reverse=True, key=lambda x: x[0])
    return out

def output_candidates_for_group(
    group: Set[Cell],
    w: int,
    h: int,
    blocked_cells: Set[Cell],
    road_load: Dict[Node, int],
) -> List[Cell]:
    """Adjacent legal 1F start cells for a miner group, selected after all miner cells exist."""
    cands: Set[Cell] = set()
    for c in group:
        for n in neighbors4(c):
            if not in_bounds(n, w, h):
                continue
            if n in group:
                continue
            # A start may be an existing road merge cell, but never a resource/miner/elevator cell.
            if n in blocked_cells and (n[0], n[1], 0) not in road_load:
                continue
            cands.add(n)
    # Prefer cells closer to the top output row, then already-built roads for cheap merge.
    return sorted(cands, key=lambda c: (0 if (c[0], c[1], 0) in road_load else 1, c[1], c[0]))


def original_outer_shell(resources: Set[Cell], w: int, h: int) -> Set[Cell]:
    out: Set[Cell] = set()
    for comp in connected_components(resources):
        depths = exterior_shell_depths(comp, w, h)
        out.update(c for c, d in depths.items() if d == 0)
    return out


def outer_shell_stats(resources: Set[Cell], miners: List[Miner], w: int, h: int) -> Dict[str, int]:
    shell = original_outer_shell(resources, w, h)
    mined_cells = {c for m in miners for c in m.cells}
    mined_shell = shell & mined_cells
    return {
        "outer_shell_total": len(shell),
        "outer_shell_mined": len(mined_shell),
        "outer_shell_unmined": len(shell - mined_shell),
    }


def candidate_groups_from_shell(
    available: Set[Cell],
    component: Set[Cell],
    depths: Dict[Cell, int],
    shell: int,
    occupied_1f: Set[Cell],
    road_load: Dict[Node, int],
    w: int,
    h: int,
    inner: bool = False,
) -> List[Tuple[int, Tuple[Cell, ...], Cell, int]]:
    """Generate miner-cell groups and one output/elevator cell. Score only; routing decides final validity."""
    road_1f = road_cells_on_floor(road_load, 0)
    blocked_for_miner = occupied_1f | road_1f
    anchors = [c for c in component if c in available and depths.get(c, 0) == shell and c not in blocked_for_miner]
    groups_seen: Set[Tuple[Cell, ...]] = set()
    out: List[Tuple[int, Tuple[Cell, ...], Cell, int]] = []

    for anchor in anchors:
        for shape in SHAPES:
            # Align every shape cell to the current shell anchor so the group really touches this shell.
            for sx, sy in shape:
                ox, oy = anchor[0] - sx, anchor[1] - sy
                g = tuple(sorted((ox + dx, oy + dy) for dx, dy in shape))
                if g in groups_seen:
                    continue
                if not all(c in available and c not in blocked_for_miner for c in g):
                    continue
                if not any(depths.get(c, 10**9) == shell for c in g):
                    continue
                groups_seen.add(g)
                gs = set(g)

                output_candidates: Set[Cell] = set()
                for c in gs:
                    for n in neighbors4(c):
                        if not in_bounds(n, w, h):
                            continue
                        if n in gs:
                            continue
                        if n in occupied_1f:
                            continue
                        # Outer output must be empty/existing 1F road. Inner elevator may sacrifice a resource.
                        if inner:
                            if n in road_1f:
                                continue
                            output_candidates.add(n)
                        else:
                            if n in available:
                                continue
                            output_candidates.add(n)
                if not output_candidates:
                    continue

                demand = len(g)
                neigh = resource_neighbor_score(g, component)
                avg_depth = sum(depths.get(c, 0) for c in g) / max(1, demand)
                line = is_line_shape(gs)
                for out_cell in output_candidates:
                    existing_road = (out_cell[0], out_cell[1], 0) in road_load
                    sacrifice = 1 if inner and out_cell in available else 0
                    # Shell candidates must start outside, but shape expands inward if it has many resource neighbors.
                    if inner:
                        score = demand * 100000 + int(avg_depth * 3500) + neigh * 700 + (400 if line else 0) - sacrifice * 3500
                    else:
                        dist_top = out_cell[1]
                        score = demand * 100000 - int(avg_depth * 4000) + neigh * 550 + (200 if line else 0) + (6000 if existing_road else 0) - dist_top * 8
                    out.append((score, g, out_cell, demand))
    out.sort(reverse=True, key=lambda x: x[0])
    return out



def rect_perimeter_cells(x0: int, y0: int, x1: int, y1: int) -> List[Cell]:
    """Clockwise-ish unique cells on the perimeter of an inclusive rectangle."""
    cells: List[Cell] = []
    seen: Set[Cell] = set()
    if x0 > x1 or y0 > y1:
        return cells
    for x in range(x0, x1 + 1):
        c = (x, y0)
        if c not in seen:
            seen.add(c); cells.append(c)
    for y in range(y0 + 1, y1 + 1):
        c = (x1, y)
        if c not in seen:
            seen.add(c); cells.append(c)
    if y1 != y0:
        for x in range(x1 - 1, x0 - 1, -1):
            c = (x, y1)
            if c not in seen:
                seen.add(c); cells.append(c)
    if x1 != x0:
        for y in range(y1 - 1, y0, -1):
            c = (x0, y)
            if c not in seen:
                seen.add(c); cells.append(c)
    return cells


def safe_set_successor(successor: Dict[Node, Node], a: Node, b: Node) -> bool:
    if a == b:
        return False
    old = successor.get(a)
    if old is not None:
        return old == b
    cur = b
    seen: Set[Node] = set()
    for _ in range(10000):
        if cur == a:
            return False
        if cur in seen:
            return False
        seen.add(cur)
        nxt = successor.get(cur)
        if nxt is None:
            break
        cur = nxt
    successor[a] = b
    return True


def build_local_4way_collector_tree(
    resources: Set[Cell],
    w: int,
    h: int,
    sink_ports: List[Cell],
    road_load: Dict[Node, int],
    successor: Dict[Node, Node],
    margin: int = 3,
    component_padding: int = 1,
    gate_spacing: int = 6,
) -> Set[Node]:
    """Prebuild zero-load 1F collector trees around resource components.

    Two-stage routing model:
    1) Around each resource cluster, make a slightly larger 4-way local collector rectangle.
       Miners may merge into any side of this rectangle instead of all walking around the
       resource outline toward y=-1.
    2) The local rectangle is partitioned into several directed basins.  Each basin has a
       top-edge gate, and each gate goes straight to the final global top output row.

    This avoids the old failure mode where one huge road ring wrapped around the resource
    outline and blocked every shell miner output behind it.  The collector still preserves
    the single-line rule: every collector node has at most one successor.  Multiple miners
    may merge into it, but no node splits.
    """
    if not resources or not sink_ports:
        return set()

    collector_nodes: Set[Node] = set()
    top_ports = [p for p in sink_ports if p[1] == -1]
    if not top_ports:
        top_ports = sink_ports

    def add_node(c: Cell) -> Node:
        n = (c[0], c[1], 0)
        road_load.setdefault(n, 0)
        collector_nodes.add(n)
        return n

    def add_edge(a: Cell, b: Cell) -> None:
        na = add_node(a)
        nb = add_node(b)
        safe_set_successor(successor, na, nb)

    def component_box(comp: Set[Cell]) -> Tuple[int, int, int, int]:
        minx = min(x for x, y in comp)
        maxx = max(x for x, y in comp)
        miny = min(y for x, y in comp)
        maxy = max(y for x, y in comp)
        return (
            max(0, minx - margin),
            max(0, miny - margin),
            min(w - 1, maxx + margin),
            min(h - 1, maxy + margin),
        )

    def boxes_overlap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)

    # If two local collector rectangles overlap, build one collector around the union.
    # Otherwise their perimeter successor directions can fight each other. The cycle-safe
    # successor setter below already rejects bad edges, but merging avoids the broken
    # half-collector state in the first place.
    collector_groups: List[Set[Cell]] = [set(c) for c in connected_components(resources)]
    changed = True
    while changed:
        changed = False
        merged: List[Set[Cell]] = []
        used = [False] * len(collector_groups)
        for i, comp_i in enumerate(collector_groups):
            if used[i]:
                continue
            cur = set(comp_i)
            cur_box = component_box(cur)
            used[i] = True
            grew = True
            while grew:
                grew = False
                for j, comp_j in enumerate(collector_groups):
                    if used[j]:
                        continue
                    if boxes_overlap(cur_box, component_box(comp_j)):
                        cur.update(comp_j)
                        cur_box = component_box(cur)
                        used[j] = True
                        grew = True
                        changed = True
            merged.append(cur)
        collector_groups = merged

    for comp in collector_groups:
        minx = min(x for x, y in comp)
        maxx = max(x for x, y in comp)
        miny = min(y for x, y in comp)
        maxy = max(y for x, y in comp)

        x0 = max(0, minx - margin)
        x1 = min(w - 1, maxx + margin)
        y0 = max(0, miny - margin)
        y1 = min(h - 1, maxy + margin)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue

        # Try to expand if clipping made the rectangle touch any resource.
        for _ in range(component_padding + margin + 2):
            touched = [c for c in rect_perimeter_cells(x0, y0, x1, y1) if c in resources]
            if not touched:
                break
            if x0 > 0:
                x0 -= 1
            if x1 < w - 1:
                x1 += 1
            if y0 > 0:
                y0 -= 1
            if y1 < h - 1:
                y1 += 1

        perim = rect_perimeter_cells(x0, y0, x1, y1)
        if len(perim) < 4:
            continue
        idx = {c: i for i, c in enumerate(perim)}
        nper = len(perim)

        # Several gates on the top side.  Capacity is therefore distributed over many
        # global output columns instead of bottlenecking the whole cluster into one lane.
        gate_cells: List[Cell] = []
        top_width = x1 - x0 + 1
        if top_width <= 2:
            gate_cells = [(x0, y0)]
        else:
            first = x0 + 1
            last = x1 - 1
            for x in range(first, last + 1, max(1, gate_spacing)):
                gate_cells.append((x, y0))
            if (last, y0) not in gate_cells:
                gate_cells.append((last, y0))
            # Include corners too when the cluster is wide; they help side/bottom exits.
            if top_width >= 8:
                gate_cells.insert(0, (x0, y0))
                gate_cells.append((x1, y0))
        gate_cells = [g for g in dict.fromkeys(gate_cells) if g in idx]
        if not gate_cells:
            continue
        gate_indices = [idx[g] for g in gate_cells]

        # Every perimeter cell flows along the rectangle toward its nearest gate.
        # This partitions the 4-way local output rectangle into several no-split basins.
        for i, c in enumerate(perim):
            if c in gate_cells:
                continue
            best_gate = None
            best_dist = 10**9
            best_dir = 1
            for gi in gate_indices:
                cw = (gi - i) % nper
                ccw = (i - gi) % nper
                if cw <= ccw:
                    dist, direction = cw, 1
                else:
                    dist, direction = ccw, -1
                if dist < best_dist:
                    best_dist = dist
                    best_gate = gi
                    best_dir = direction
            if best_gate is None:
                continue
            nxt = perim[(i + best_dir) % nper]
            add_edge(c, nxt)

        # Each gate first reaches row 0, then drains horizontally into a SOFT
        # center band.  All final output columns remain legal, but prebuilt
        # collectors no longer scatter directly to their own gx column.
        preferred_xs = centered_output_band(w, desired=max(9, min(17, w // 2)))
        grid_center = (w - 1) / 2.0
        for gx, gy in gate_cells:
            add_node((gx, gy))
            if gy > 0:
                for y in range(gy, 0, -1):
                    add_edge((gx, y), (gx, y - 1))
                exit_base = (gx, 0)
            else:
                exit_base = (gx, 0)
                add_node(exit_base)
            if not preferred_xs:
                bx = gx
            else:
                # Gate target is pulled toward the center band, but not hard-limited
                # to seven fixed banks. This matches the desired visual: outputs bunch
                # near the middle while still allowing extra columns when needed.
                bx = min(preferred_xs, key=lambda x: (abs(x - gx), abs(x - grid_center), x))
            if gx < bx:
                for x in range(gx, bx):
                    add_edge((x, 0), (x + 1, 0))
            elif gx > bx:
                for x in range(gx, bx, -1):
                    add_edge((x, 0), (x - 1, 0))
            n0 = add_node((bx, 0))
            nout = (bx, -1, 0)
            road_load.setdefault(nout, 0)
            collector_nodes.add(nout)
            safe_set_successor(successor, n0, nout)

    return collector_nodes


def commit_route(
    miner: Miner,
    path: List[Node],
    load_nodes: List[Node],
    out_floor: int,
    road_load: Dict[Node, int],
    successor: Dict[Node, Node],
    out_used: Dict[Cell, int],
    output_floors: Dict[Cell, int],
    paths: List[Tuple[int, List[Node]]],
) -> None:
    out_used[miner.port] = out_used.get(miner.port, 0) + miner.demand
    output_floors[miner.port] = out_floor
    paths.append((miner.id, path))
    for n in load_nodes:
        road_load[n] = road_load.get(n, 0) + miner.demand
    commit_path_successors(path, successor)


def greedy_dynamic_optimize(
    resources: Set[Cell],
    w: int,
    h: int,
    sink_ports: List[Cell],
    cap: int = 32,
    max_per_miner: int = 4,
    max_candidates: int = 10000,
):
    """
    Cluster placement first, unified routing later.

    New order requested by user:
    1) Place outer-shell miner groups first. No roads are placed here.
    2) Place inner miner groups + mandatory elevator cells. No roads are placed here either.
    3) Freeze all miner/elevator cells, then route all miners as one integrated road-building phase.

    Consequence:
    - Roads can no longer block later miner placement.
    - Routing failure of one candidate does not stop inner placement.
    - Same-floor crossing, branch prohibition, output floor mixing, and ramp-merge prohibition remain hard rules.
    """
    original_resources: Set[Cell] = set(resources)
    remaining: Set[Cell] = set(resources)

    road_load: Dict[Node, int] = {}
    successor: Dict[Node, Node] = {}
    out_used: Dict[Cell, int] = {p: 0 for p in sink_ports}
    output_floors: Dict[Cell, int] = {}
    paths: List[Tuple[int, List[Node]]] = []
    miners: List[Miner] = []
    mid = 1

    output_capacity = len(sink_ports) * cap

    planned_outer: List[Tuple[int, Tuple[Cell, ...], int]] = []
    planned_inner: List[Tuple[int, Tuple[Cell, ...], Cell, int]] = []

    def planned_demand() -> int:
        return sum(d for _, _, d in planned_outer) + sum(d for _, _, _, d in planned_inner)

    # ------------------------------------------------------------------
    # Phase 1: outer-shell miner placement only. No path/road reservation.
    # ------------------------------------------------------------------
    planned_outer_cells: Set[Cell] = set()

    for comp in connected_components(original_resources):
        depths = exterior_shell_depths(comp, w, h)
        shell_cells = sorted((c for c in comp if depths.get(c, 0) == 0), key=lambda c: (c[1], c[0]))
        for anchor in shell_cells:
            if planned_demand() >= output_capacity:
                break
            if anchor not in remaining or anchor in planned_outer_cells:
                continue
            cands = candidate_groups_for_anchor_no_output(
                anchor=anchor,
                available=remaining,
                component=comp,
                depths=depths,
                shell=0,
                occupied_1f=planned_outer_cells,
                w=w,
                h=h,
            )
            if not cands:
                continue
            score, gt, demand = cands[0]
            planned_outer.append((score, gt, demand))
            planned_outer_cells.update(gt)
            remaining.difference_update(gt)

    # ------------------------------------------------------------------
    # Phase 2: inner miner + elevator placement only. Still no roads.
    # ------------------------------------------------------------------
    planned_inner_cells: Set[Cell] = set()
    planned_elevators: Set[Cell] = set()

    # Fast anchor walk: deepest cells first. This prevents the previous empty-inside bug
    # where route failures could stop placement. Routing is not consulted here at all.
    for _round in range(3):
        placed_this_round = False
        occupied_plan = planned_outer_cells | planned_inner_cells | planned_elevators
        comps = connected_components(remaining)

        for comp in comps:
            depths = shell_depths(comp, w, h)
            anchors = sorted(
                comp,
                key=lambda c: (
                    -depths.get(c, 0),
                    -sum(1 for n in neighbors8(c) if n in comp),
                    c[1],
                    c[0],
                ),
            )

            for anchor in anchors:
                if planned_demand() >= output_capacity:
                    break
                if anchor not in remaining or anchor in occupied_plan:
                    continue

                cands = candidate_inner_groups_for_anchor_no_route(
                    anchor=anchor,
                    available=remaining,
                    component=comp,
                    depths=depths,
                    occupied_1f=occupied_plan,
                    w=w,
                    h=h,
                )
                if not cands:
                    continue

                for score, gt, elevator, demand in cands[:20]:
                    g = set(gt)
                    if not g <= remaining:
                        continue
                    if g & occupied_plan:
                        continue
                    if elevator in occupied_plan or elevator in g:
                        continue
                    if not in_bounds(elevator, w, h):
                        continue
                    if all(manhattan(elevator, c) != 1 for c in g):
                        continue

                    planned_inner.append((score, tuple(sorted(g)), elevator, demand))
                    planned_inner_cells.update(g)
                    planned_elevators.add(elevator)
                    remaining.difference_update(g)
                    # Sacrificed elevator resource: removed from available, not counted as mined.
                    remaining.discard(elevator)
                    occupied_plan.update(g)
                    occupied_plan.add(elevator)
                    placed_this_round = True
                    break

        if not placed_this_round:
            break

    # ------------------------------------------------------------------
    # Phase 3: integrated routing. All planned miner/elevator cells are frozen.
    # ------------------------------------------------------------------
    all_planned_miner_cells: Set[Cell] = planned_outer_cells | planned_inner_cells
    elevator_cells: Set[Cell] = set(planned_elevators)
    sacrificed_elevator_resources = elevator_cells & original_resources
    unplanned_resources: Set[Cell] = original_resources - all_planned_miner_cells - sacrificed_elevator_resources

    # Every physical 1F cell already reserved by a miner, elevator, or unmined resource is blocked.
    # The current miner's own cells are removed from this set while routing it.
    global_blocked_1f: Set[Cell] = unplanned_resources | all_planned_miner_cells | elevator_cells

    # Prebuild a zero-load 4-way local collector tree around each resource cluster.
    # Default is intentionally generous (+3).  If some miners still fail later, we add
    # smaller rescue collectors (+2, then +1) without deleting the successful routes.
    # This matches the intended algorithm: big collector first, then shrink only for
    # the failed cases that could not reach the bigger collector without blocking exits.
    collector_nodes: Set[Node] = set()
    collector_margins_added: List[int] = []

    def add_collector_margin(
        margin: int,
        failed_tasks: Optional[List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]]] = None,
    ) -> int:
        """Add a local collector layer and return how many new nodes appeared.

        margin=3 is built around the full resource cluster.  Rescue margins 2/1 are
        built only around still-failed miner groups, so they create closer merge targets
        without filling the whole map with unnecessary collector rectangles.
        """
        before = len(collector_nodes)
        # Smaller rescue collectors need denser gates because they sit closer to the
        # failed miners and are meant to save local bottlenecks rather than make one long ring.
        spacing = 6 if margin >= 3 else 3

        if failed_tasks is None:
            collector_resources = set(original_resources)
        else:
            collector_resources: Set[Cell] = set()
            for phase, _score, gt, elevator, _demand in failed_tasks:
                collector_resources.update(gt)
                # For inner miners, adding the elevator to the rescue resource set makes
                # the local collector wrap the actual lift column too, giving the 2F route
                # a nearby legal drop/merge area after it exits the resource body.
                if phase == "inner" and elevator is not None:
                    collector_resources.add(elevator)
            if not collector_resources:
                return 0

        new_nodes = build_local_4way_collector_tree(
            resources=collector_resources,
            w=w,
            h=h,
            sink_ports=sink_ports,
            road_load=road_load,
            successor=successor,
            margin=margin,
            gate_spacing=spacing,
        )
        collector_nodes.update(new_nodes)
        if margin not in collector_margins_added:
            collector_margins_added.append(margin)
        return len(collector_nodes) - before

    add_collector_margin(3)

    # Route tasks are all together now. Outer paths also use the same 3D state-space router:
    # if 1F is blocked, they can pay for a clean elevator/ramp, bypass on 2F, then drop back.
    route_tasks: List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]] = []
    for score, gt, demand in planned_outer:
        route_tasks.append(("outer", score, gt, None, demand))
    for score, gt, elevator, demand in planned_inner:
        route_tasks.append(("inner", score, gt, elevator, demand))

    # Long/deep/larger miners first to reserve clean trunk routes; scoring of the route itself
    # prefers clustered outputs and filling each output lane toward cap=32.
    def task_sort_key(task: Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]):
        phase, score, gt, elevator, demand = task
        ys = [y for x, y in gt]
        xs = [x for x, y in gt]
        phase_rank = 0 if phase == "outer" else 1
        depthish = max(ys) if phase == "outer" else sum(ys) / max(1, len(ys))
        return (-demand, phase_rank, -depthish, min(xs), -score)

    # ------------------------------------------------------------------
    # Dynamic crisis-first routing order.
    # ------------------------------------------------------------------
    # The previous version sorted route_tasks once and then kept that order. That can let
    # an easy/early path consume the only corridor that a later miner needed. Here every
    # step re-evaluates all remaining miners against the *current* road tree, then commits
    # exactly one route:
    #   1) fewer feasible routes first  -> bottleneck / crisis first
    #   2) shorter best path next       -> output-near trunks appear early
    #   3) bigger demand next           -> fill 32-capacity output lanes efficiently
    #   4) clustered/filling output score as the final tie-breaker
    remaining_tasks = sorted(route_tasks, key=task_sort_key)

    def find_best_route_for_task(
        task: Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]
    ) -> Optional[dict]:
        phase, base_score, gt, elevator, demand = task
        g = set(gt)
        best = None
        best_score = 10**18
        feasible_count = 0
        tested_count = 0

        if phase == "outer":
            blocked_for_outputs = global_blocked_1f - g
            outputs = output_candidates_for_group(g, w, h, blocked_for_outputs, road_load)

            # Try many starts. The output candidate list already prefers nearby existing trunks,
            # so this remains fast but no longer gives up after only a few starts.
            for output in outputs[:72]:
                tested_count += 1
                blocked_1f = global_blocked_1f - g
                result = route_3d_to_output(
                    start_cell=output,
                    ports=sink_ports,
                    w=w,
                    h=h,
                    resources=unplanned_resources,
                    blocked_1f=blocked_1f,
                    road_load=road_load,
                    successor=successor,
                    elevator_cells=elevator_cells,
                    demand=demand,
                    cap=cap,
                    output_floors=output_floors,
                    out_used=out_used,
                    prefer_floor0=True,
                )
                if result is None:
                    continue
                port, path, load_nodes, out_floor, ramp_cells = result
                if out_used.get(port, 0) + demand > cap:
                    continue
                if not output_floor_compatible(port, out_floor, output_floors):
                    continue
                if not can_commit_path(path, successor):
                    continue

                feasible_count += 1
                cluster_penalty = output_cluster_penalty(port, out_used)
                fill_bonus = out_used.get(port, 0)
                same_lane_bonus = min(32, fill_bonus)
                # Stronger than before: keep outputs gathered and push used lanes toward 32.
                ramp_penalty = len(ramp_cells) * 120
                floor_penalty = 0 if out_floor == 0 else 120
                route_score = len(path) * 100 + cluster_penalty * 70 + ramp_penalty + floor_penalty - fill_bonus * 8 - same_lane_bonus * 3
                if route_score < best_score:
                    best_score = route_score
                    best = output, port, path, load_nodes, out_floor, ramp_cells, cluster_penalty

        else:
            assert elevator is not None
            if elevator not in elevator_cells:
                return None
            tested_count = 1
            blocked_1f = global_blocked_1f - g
            result = route_inner_elevator(
                elevator=elevator,
                ports=sink_ports,
                w=w,
                h=h,
                resources=unplanned_resources,
                blocked_1f=blocked_1f,
                road_load=road_load,
                successor=successor,
                elevator_cells=elevator_cells,
                demand=demand,
                cap=cap,
                output_floors=output_floors,
                out_used=out_used,
            )
            if result is not None:
                port, path, load_nodes, out_floor, ramp_cells = result
                if out_used.get(port, 0) + demand <= cap and output_floor_compatible(port, out_floor, output_floors) and can_commit_path(path, successor):
                    feasible_count = 1
                    cluster_penalty = output_cluster_penalty(port, out_used)
                    fill_bonus = out_used.get(port, 0)
                    # Inner routes may need to stay 2F, but prefer returning to 1F when score is close.
                    floor_penalty = 0 if out_floor == 0 else 80
                    route_score = len(path) * 100 + cluster_penalty * 70 + floor_penalty - fill_bonus * 8
                    best_score = route_score
                    best = elevator, port, path, load_nodes, out_floor, ramp_cells, cluster_penalty

        if best is None:
            return None

        output, port, path, load_nodes, out_floor, ramp_cells, cluster_penalty = best
        return {
            "task": task,
            "phase": phase,
            "base_score": base_score,
            "gt": gt,
            "elevator": elevator,
            "demand": demand,
            "output": output,
            "port": port,
            "path": path,
            "load_nodes": load_nodes,
            "out_floor": out_floor,
            "ramp_cells": ramp_cells,
            "route_score": best_score,
            "feasible_count": feasible_count,
            "tested_count": tested_count,
            "path_len": len(path),
            "cluster_penalty": cluster_penalty,
        }

    def dynamic_route_priority(e: dict):
        # Lower tuple is committed first.
        # feasible_count==1 means "only one currently viable way out" and should be protected
        # before an easy miner consumes that corridor. For ties, shorter/output-nearer paths
        # are committed first to create clean trunks near the exits.
        phase_rank = 0 if e["phase"] == "outer" else 1
        return (
            phase_rank,                 # protect outer-shell 1F miners first
            e["feasible_count"],       # bottleneck first inside each phase
            e["path_len"],             # then output-near / short trunk first
            -e["demand"],              # fill output cap faster
            e["cluster_penalty"],       # gather outputs
            e["route_score"],
            -e["base_score"],
        )


    def clone_state_after_candidate(
        port: Cell,
        path: List[Node],
        load_nodes: List[Node],
        out_floor: int,
        demand: int,
    ) -> Tuple[Dict[Node, int], Dict[Node, Node], Dict[Cell, int], Dict[Cell, int]]:
        """Return simulated state after committing one route, without mutating the real map."""
        next_road_load = dict(road_load)
        for n in load_nodes:
            next_road_load[n] = next_road_load.get(n, 0) + demand

        next_successor = dict(successor)
        commit_path_successors(path, next_successor)

        next_out_used = dict(out_used)
        next_out_used[port] = next_out_used.get(port, 0) + demand

        next_output_floors = dict(output_floors)
        next_output_floors[port] = out_floor
        return next_road_load, next_successor, next_out_used, next_output_floors

    def task_has_legal_exit_in_state(
        task: Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int],
        road_load_state: Dict[Node, int],
        successor_state: Dict[Node, Node],
        out_used_state: Dict[Cell, int],
        output_floors_state: Dict[Cell, int],
        max_starts: int = 96,
    ) -> bool:
        """Check whether a not-yet-routed miner still has at least one legal way out.

        This is the important anti-steal test.  Existing roads are not automatically treated as
        blocked, because a future miner is allowed to merge into an existing single-line road.
        A future outer miner is considered killed only when no adjacent start can legally route or
        merge under the simulated road tree/capacity/output-floor state.
        """
        phase, _base_score, gt, elevator, demand = task

        # Inner miners own a pre-reserved elevator cell.  global_blocked_1f already protects all
        # planned elevator cells from 1F road use, so the classic "exit stolen by a road" failure is
        # mostly an outer-miner problem.  Still, require its elevator to remain a clean legal ramp.
        if phase == "inner":
            if elevator is None:
                return False
            return ((elevator[0], elevator[1], 0) not in road_load_state and
                    (elevator[0], elevator[1], 1) not in road_load_state and
                    elevator in elevator_cells)

        g = set(gt)
        blocked_for_outputs = global_blocked_1f - g
        outputs = output_candidates_for_group(g, w, h, blocked_for_outputs, road_load_state)
        if not outputs:
            return False

        # A pure 1F future miner survives if at least one adjacent start can route to output or
        # legally merge into the current tree with enough downstream capacity.
        for output in outputs[:max_starts]:
            result = route_3d_to_output(
                start_cell=output,
                ports=sink_ports,
                w=w,
                h=h,
                resources=unplanned_resources,
                blocked_1f=blocked_for_outputs,
                road_load=road_load_state,
                successor=successor_state,
                elevator_cells=elevator_cells,
                demand=demand,
                cap=cap,
                output_floors=output_floors_state,
                out_used=out_used_state,
                prefer_floor0=True,
            )
            if result is None:
                continue
            port2, path2, load_nodes2, out_floor2, ramp_cells2 = result
            if out_used_state.get(port2, 0) + demand > cap:
                continue
            if not output_floor_compatible(port2, out_floor2, output_floors_state):
                continue
            if not can_commit_path(path2, successor_state):
                continue
            if any(road_load_state.get(n, 0) + demand > cap for n in load_nodes2):
                continue
            if path_has_ramp_merge_violation(path2, set(road_load_state)):
                continue
            return True
        return False

    def candidate_steals_future_exit(
        current_task: Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int],
        future_tasks: List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]],
        port: Cell,
        path: List[Node],
        load_nodes: List[Node],
        out_floor: int,
        demand: int,
    ) -> bool:
        """Reject a candidate route if it steals the last practical exit of a future miner.

        Fast prefilter:
        - Only outer miners have flexible adjacent 1F exits.
        - Only future miners whose current exit candidates physically overlap this candidate's
          new 1F path are expensive-checked.
        - Existing roads are still allowed as merge targets, so overlap alone is not illegal;
          it becomes illegal only if the simulated state leaves the future miner with no route.
        """
        # Ignore the prebuilt local/global collector tree in the anti-steal test.
        # Those cells are intentionally shared merge/trunk cells; treating them as
        # stolen adjacent exits makes the reservation logic far too conservative.
        path_1f_cells = {(x, y) for x, y, z in path if z == 0 and y >= 0 and (x, y, z) not in collector_nodes}
        if not path_1f_cells:
            return False

        # Do not spend time protecting routes beyond the global output capacity.
        if sum(m.demand for m in miners) + demand >= output_capacity:
            return False

        risky_tasks: List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]] = []
        for task in future_tasks:
            if task == current_task:
                continue
            phase, _base_score, gt, _elevator, _future_demand = task
            if phase != "outer":
                continue
            g = set(gt)
            blocked_for_outputs = global_blocked_1f - g
            starts = output_candidates_for_group(g, w, h, blocked_for_outputs, road_load)
            if not starts:
                continue
            if path_1f_cells & set(starts):
                risky_tasks.append(task)

        if not risky_tasks:
            return False

        next_road_load, next_successor, next_out_used, next_output_floors = clone_state_after_candidate(
            port=port,
            path=path,
            load_nodes=load_nodes,
            out_floor=out_floor,
            demand=demand,
        )

        # Sort by fewest current starts first: protect the actual bottleneck exits first.
        risky_tasks.sort(key=lambda task: len(output_candidates_for_group(
            set(task[2]), w, h, global_blocked_1f - set(task[2]), road_load
        )))

        # Default maps have only a few risky tasks per candidate.  The cap prevents GUI stalls on
        # hand-painted pathological maps; deferred candidates will be rechecked next wave anyway.
        for task in risky_tasks[:24]:
            alive_after = task_has_legal_exit_in_state(
                task,
                next_road_load,
                next_successor,
                next_out_used,
                next_output_floors,
                max_starts=48,
            )
            if not alive_after:
                return True
        return False

    # Wave routing: evaluate every remaining miner once, sort by crisis priority, then commit
    # in that order.  If the +3 collector cannot reach some miners, add smaller rescue
    # collectors (+2, then +1) and retry only the remaining failed tasks.
    rescue_margins = [3, 2, 1]
    stage_index = 0
    waves_in_stage = 0
    max_waves_per_stage = 8

    while remaining_tasks and sum(m.demand for m in miners) < output_capacity:
        evaluated: List[dict] = []
        unroutable_now: List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]] = []
        for task in remaining_tasks:
            ev = find_best_route_for_task(task)
            if ev is None:
                unroutable_now.append(task)
            else:
                evaluated.append(ev)

        if not evaluated:
            # No current route can reach the active collector layer.  Shrink the
            # collector rectangle for only the still-failed tasks and retry.
            stage_index += 1
            if stage_index >= len(rescue_margins):
                break
            add_collector_margin(rescue_margins[stage_index], remaining_tasks)
            waves_in_stage = 0
            continue

        evaluated.sort(key=dynamic_route_priority)
        committed_tasks: Set[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]] = set()
        deferred_tasks: List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]] = []
        progress = False

        for ev in evaluated:
            if sum(m.demand for m in miners) >= output_capacity:
                break

            task = ev["task"]
            phase = ev["phase"]
            gt = ev["gt"]
            demand = ev["demand"]
            output = ev["output"]
            port = ev["port"]
            path = ev["path"]
            load_nodes = ev["load_nodes"]
            out_floor = ev["out_floor"]
            ramp_cells = ev["ramp_cells"]

            # Since earlier routes in this wave may have changed the road tree/capacity,
            # re-check all hard constraints before committing. If stale, defer to next wave
            # where it will be re-routed against the new map.
            if out_used.get(port, 0) + demand > cap:
                deferred_tasks.append(task)
                continue
            if not output_floor_compatible(port, out_floor, output_floors):
                deferred_tasks.append(task)
                continue
            if not can_commit_path(path, successor):
                deferred_tasks.append(task)
                continue
            if any(road_load.get(n, 0) + demand > cap for n in load_nodes):
                deferred_tasks.append(task)
                continue
            if path_has_ramp_merge_violation(path, set(road_load)):
                deferred_tasks.append(task)
                continue

            future_tasks = [t for t in remaining_tasks if t != task and t not in committed_tasks]
            if candidate_steals_future_exit(
                current_task=task,
                future_tasks=future_tasks,
                port=port,
                path=path,
                load_nodes=load_nodes,
                out_floor=out_floor,
                demand=demand,
            ):
                # Do not let this path eat the last legal output/start of a not-yet-routed miner.
                # It will be retried in the next wave after other bottleneck miners are routed.
                deferred_tasks.append(task)
                continue

            m = Miner(mid, tuple(sorted(gt)), output, demand, port, phase)
            mid += 1
            miners.append(m)
            commit_route(m, path, load_nodes, out_floor, road_load, successor, out_used, output_floors, paths)
            # Any route, outer or inner, may now create temporary elevator/ramp cells.
            # A ramp physically occupies the column on both floors, so reserve it for later routes.
            if ramp_cells:
                elevator_cells.update(ramp_cells)
                global_blocked_1f.update(ramp_cells)
            committed_tasks.add(task)
            progress = True

        # Anything not committed gets another chance after the newly-created trunks exist.
        next_remaining: List[Tuple[str, int, Tuple[Cell, ...], Optional[Cell], int]] = []
        next_remaining.extend(unroutable_now)
        next_remaining.extend(deferred_tasks)
        for ev in evaluated:
            task = ev["task"]
            if task not in committed_tasks and task not in deferred_tasks:
                next_remaining.append(task)
        remaining_tasks = next_remaining

        if progress:
            waves_in_stage += 1
            # After a few waves with the current collector size, give the failed tail a
            # closer collector.  Successful routes stay untouched.
            if remaining_tasks and waves_in_stage >= max_waves_per_stage and stage_index + 1 < len(rescue_margins):
                stage_index += 1
                add_collector_margin(rescue_margins[stage_index], remaining_tasks)
                waves_in_stage = 0
            continue

        # We found candidate routes, but all were stale/deferred/exit-stealing.  Add the
        # next smaller collector layer to create closer merge targets, then retry.
        stage_index += 1
        if stage_index >= len(rescue_margins):
            break
        add_collector_margin(rescue_margins[stage_index], remaining_tasks)
        waves_in_stage = 0

    miners.sort(key=lambda m: m.id)
    paths.sort(key=lambda x: x[0])
    # Final hard guard.  No output compaction or tail rewriting happens after this.
    return hard_rebuild_validated(miners, paths, sink_ports, cap)

def path_hits_final_machine(path: List[Node], miner: Miner, machine_cells: Set[Cell]) -> bool:
    """True if a 1F road physically cuts through any committed miner/elevator cell."""
    allowed: Set[Cell] = set()
    # Inner miner owns its elevator/output column; its path must start there.
    if getattr(miner, "phase", "outer") == "inner":
        allowed.add(miner.output)
    for x, y, z in path:
        if z != 0 or y < 0:
            continue
        c = (x, y)
        if c in machine_cells and c not in allowed:
            return True
    return False


def hard_rebuild_validated(
    miners: List[Miner],
    paths: List[Tuple[int, List[Node]]],
    ports: List[Cell],
    cap: int,
) -> Tuple[List[Miner], Dict[Node, int], List[Tuple[int, List[Node]]], Set[Tuple[Node, Node]]]:
    """Final hard guard.

    This intentionally does not try to repair geometry after the fact.  It rebuilds
    the committed road tree from scratch and simply refuses any path that would
    violate physics: branching, output-floor mixing, ramp T-merge, capacity, or
    1F road through final machine cells.
    """
    miner_by_id = {m.id: m for m in miners}
    # Treat all planned machines as physical blockers.  This is conservative but
    # prevents the visual 'road pierces a miner' cases that happened when only
    # already-accepted miners were considered.
    machine_cells: Set[Cell] = set()
    for m in miners:
        machine_cells.update(m.cells)
        if getattr(m, "phase", "outer") == "inner":
            machine_cells.add(m.output)

    road_load: Dict[Node, int] = {}
    successor: Dict[Node, Node] = {}
    out_used: Dict[Cell, int] = {p: 0 for p in ports}
    output_floors: Dict[Cell, int] = {}
    clean_miners: List[Miner] = []
    clean_paths: List[Tuple[int, List[Node]]] = []

    # Bigger miners and paths that fill already-open banks tend to be more valuable.
    ordered = sorted(paths, key=lambda mp: (miner_by_id.get(mp[0], Miner(0,(),(0,0),0,(0,0))).id))
    for mid, path in ordered:
        m = miner_by_id.get(mid)
        if m is None or not path:
            continue
        if path_hits_final_machine(path, m, machine_cells):
            continue
        floor = output_floor_from_path(path, m.port)
        if floor is None:
            continue
        if out_used.get(m.port, 0) + m.demand > cap:
            continue
        if not output_floor_compatible(m.port, floor, output_floors):
            continue
        if any(road_load.get(n, 0) + m.demand > cap for n in path):
            continue
        if not can_commit_path(path, successor):
            continue
        if path_has_ramp_merge_violation(path, set(road_load)):
            continue
        out_used[m.port] = out_used.get(m.port, 0) + m.demand
        output_floors[m.port] = floor
        clean_miners.append(m)
        clean_paths.append((mid, path))
        for n in path:
            road_load[n] = road_load.get(n, 0) + m.demand
        commit_path_successors(path, successor)

    directed_edges = {(a, b) for _, path in clean_paths for a, b in zip(path, path[1:])}
    return clean_miners, road_load, clean_paths, directed_edges


def validate_no_branch_and_output_mix(paths: List[Tuple[int, List[Node]]], ports: List[Cell]) -> dict:
    edge_successors: Dict[Node, Set[Node]] = {}
    output_floors_seen: Dict[Cell, Set[int]] = {p: set() for p in ports}
    port_set = set(ports)

    # Reconstruct build order to detect the new critical rule:
    # floor-switch edges must not touch preexisting road nodes.
    # A path may merge after switching, but the switch cell itself must be clean.
    committed_roads: Set[Node] = set()
    ramp_merge_details: List[Tuple[int, Node, Node]] = []

    for mid, path in sorted(paths, key=lambda x: x[0]):
        first_existing = None
        for i, n in enumerate(path):
            if n in committed_roads:
                first_existing = i
                break

        for a, b in zip(path, path[1:]):
            edge_successors.setdefault(a, set()).add(b)

        if first_existing is not None:
            i = first_existing
            if i > 0 and is_floor_switch_edge(path[i - 1], path[i]):
                ramp_merge_details.append((mid, path[i - 1], path[i]))
            if i + 1 < len(path) and is_floor_switch_edge(path[i], path[i + 1]):
                ramp_merge_details.append((mid, path[i], path[i + 1]))

        for n in path:
            committed_roads.add(n)
            c = (n[0], n[1])
            if c in port_set:
                output_floors_seen.setdefault(c, set()).add(n[2])

    branch_nodes = {n: nxt for n, nxt in edge_successors.items() if len(nxt) > 1}
    mixed_outputs = {p: floors for p, floors in output_floors_seen.items() if len(floors) > 1}
    return {
        "branch_nodes": len(branch_nodes),
        "mixed_floor_outputs": len(mixed_outputs),
        "ramp_merge_violations": len(ramp_merge_details),
        "machine_hits": 0,
        "branch_node_details": branch_nodes,
        "mixed_output_details": mixed_outputs,
        "ramp_merge_details": ramp_merge_details,
    }


def output_loads(paths: List[Tuple[int, List[Node]]], miners: List[Miner], sink_ports: List[Cell]) -> Dict[Cell, int]:
    loads = {p: 0 for p in sink_ports}
    for m in miners:
        loads[m.port] = loads.get(m.port, 0) + m.demand
    return loads


def run_demo(seed: int = 12):
    w, h, cap = 40, 42, 32
    ports = make_sink_ports(w, 7, y=-1)
    resources = make_blob_resources(w, h, seed)
    miners, road_load, paths, _ = greedy_dynamic_optimize(resources, w, h, ports, cap, max_candidates=2500)
    mined = sum(m.demand for m in miners)
    level2 = {(x, y) for (x, y, z), v in road_load.items() if z == 1}
    ground_resource_road = {(x, y) for (x, y, z), v in road_load.items() if z == 0 and y >= 0} & resources
    return {
        "resources": len(resources),
        "miners": len(miners),
        "outer_miners": sum(1 for m in miners if getattr(m, "phase", "outer") == "outer"),
        "inner_miners": sum(1 for m in miners if getattr(m, "phase", "outer") == "inner"),
        "mined_resources": mined,
        "unmined_resources": len(resources) - mined,
        "road_cells_3d": len(road_load),
        "ground_resource_cells_used_as_road": len(ground_resource_road),
        "level2_road_cells": len(level2),
        "max_road_load": max(road_load.values()) if road_load else 0,
        "cap": cap,
        "output_loads": output_loads(paths, miners, ports),
        "validation": validate_no_branch_and_output_mix(paths, ports),
        "outer_shell": outer_shell_stats(resources, miners, w, h),
    }



# ===================== UI =====================

import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen, QBrush, QPolygon
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

algo = sys.modules[__name__]
IMPORT_ERROR = None


Cell = Tuple[int, int]
Node = Tuple[int, int, int]


class GridCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.w = 40
        self.h = 42
        self.cell = 20
        self.margin_left = 42
        self.margin_top = 90

        self.resources: Set[Cell] = set()
        self.sink_ports: List[Cell] = self.make_ports()

        self.miners = []
        self.paths: List[Tuple[int, List[Node]]] = []
        self.road_load: Dict[Node, int] = {}
        self.directed_edges = set()

        self.cap = 32
        self.paint_mode: Optional[bool] = None
        self.show_second_floor = True

        self.setMinimumSize(
            self.w * self.cell + self.margin_left * 2,
            self.h * self.cell + self.margin_top + 42,
        )
        self.setMouseTracking(True)

    def make_ports(self) -> List[Cell]:
        # CRITICAL:
        # The router treats the top pass/output row as y=-1.
        # The previous GUI used y=-2 here, so every direct output target was
        # outside route bounds and the optimizer could return 0 routed miners.
        if algo is not None:
            return algo.make_sink_ports(self.w, 7, y=-1)
        return [(x, -1) for x in range(max(1, self.w))]

    def reset_result(self):
        self.miners = []
        self.paths = []
        self.road_load = {}
        self.directed_edges = set()
        self.update()

    def load_demo_resources(self, seed: int = 12):
        if algo is None:
            raise RuntimeError(f"miner_router_top_pass_core_fixed.py import 실패: {IMPORT_ERROR}")
        self.sink_ports = self.make_ports()
        self.resources = set(algo.make_blob_resources(self.w, self.h, seed=seed))
        self.reset_result()

    def run_optimizer(self):
        if algo is None:
            raise RuntimeError(f"miner_router_top_pass_core_fixed.py import 실패: {IMPORT_ERROR}")
        self.sink_ports = self.make_ports()

        # Output sanity check: route_2f_escape_resources() and route_leftover_mixed()
        # both use y=-1 as the single legal upward pass/output row.
        if not self.sink_ports:
            raise RuntimeError("출력 포트가 0개입니다. make_ports()/make_sink_ports()를 확인하세요.")
        bad_ports = [p for p in self.sink_ports if p[1] != -1]
        if bad_ports:
            raise RuntimeError(f"출력 포트 y값 오류: {bad_ports[:5]} ... 모든 출력 포트는 y=-1이어야 합니다.")

        self.miners, self.road_load, self.paths, self.directed_edges = algo.greedy_dynamic_optimize(
            resources=set(self.resources),
            w=self.w,
            h=self.h,
            sink_ports=self.sink_ports,
            cap=self.cap,
            max_per_miner=4,
            max_candidates=2500,
        )
        self.update()

    def output_loads(self) -> Dict[Cell, int]:
        if algo is None:
            return {p: 0 for p in self.sink_ports}
        return algo.output_loads(self.paths, self.miners, self.sink_ports)

    def summary(self) -> dict:
        mined = sum(m.demand for m in self.miners)
        level2 = {(x, y) for (x, y, z), load in self.road_load.items() if z == 1}
        ground_resource_road = {(x, y) for (x, y, z), load in self.road_load.items() if z == 0 and y >= 0} & self.resources
        validation = {"branch_nodes": 0, "mixed_floor_outputs": 0, "ramp_merge_violations": 0}
        outer_stats = {"outer_shell_total": 0, "outer_shell_mined": 0, "outer_shell_unmined": 0}
        if algo is not None and self.paths:
            validation = algo.validate_no_branch_and_output_mix(self.paths, self.sink_ports)
            outer_stats = algo.outer_shell_stats(self.resources, self.miners, self.w, self.h)
        return {
            "resources": len(self.resources),
            "miners": len(self.miners),
            "mined": mined,
            "unmined": len(self.resources) - mined,
            "road_cells_3d": len(self.road_load),
            "ground_resource_road": len(ground_resource_road),
            "level2_cells": len(level2),
            "max_load": max(self.road_load.values()) if self.road_load else 0,
            "cap": self.cap,
            "branch_nodes": validation.get("branch_nodes", 0),
            "mixed_outputs": validation.get("mixed_floor_outputs", 0),
            "ramp_merge": validation.get("ramp_merge_violations", 0),
            "outer_shell_total": outer_stats.get("outer_shell_total", 0),
            "outer_shell_mined": outer_stats.get("outer_shell_mined", 0),
            "outer_shell_unmined": outer_stats.get("outer_shell_unmined", 0),
        }

    def save_map(self, path: str):
        lines = [f"{self.w},{self.h}"]
        for x, y in sorted(self.resources):
            lines.append(f"{x},{y}")
        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def load_map(self, path: str):
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        if not lines:
            return
        w, h = map(int, lines[0].split(","))
        self.w, self.h = w, h
        self.setMinimumSize(
            self.w * self.cell + self.margin_left * 2,
            self.h * self.cell + self.margin_top + 42,
        )
        self.sink_ports = self.make_ports()
        self.resources = set()
        for line in lines[1:]:
            if not line.strip():
                continue
            x, y = map(int, line.split(","))
            if 0 <= x < self.w and 0 <= y < self.h:
                self.resources.add((x, y))
        self.reset_result()

    def cell_at_pos(self, pos: QPoint) -> Optional[Cell]:
        x = (pos.x() - self.margin_left) // self.cell
        y = (pos.y() - self.margin_top) // self.cell
        if 0 <= x < self.w and 0 <= y < self.h:
            return int(x), int(y)
        return None

    def edit_cell(self, c: Optional[Cell]):
        if c is None:
            return
        if self.paint_mode is True:
            self.resources.add(c)
        elif self.paint_mode is False:
            self.resources.discard(c)
        self.reset_result()

    def mousePressEvent(self, event):
        c = self.cell_at_pos(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            self.paint_mode = True
            self.edit_cell(c)
        elif event.button() == Qt.MouseButton.RightButton:
            self.paint_mode = False
            self.edit_cell(c)
        elif event.button() == Qt.MouseButton.MiddleButton:
            if c is not None:
                if c in self.resources:
                    self.resources.remove(c)
                else:
                    self.resources.add(c)
                self.reset_result()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.paint_mode = True
            self.edit_cell(self.cell_at_pos(event.pos()))
        elif event.buttons() & Qt.MouseButton.RightButton:
            self.paint_mode = False
            self.edit_cell(self.cell_at_pos(event.pos()))

    def mouseReleaseEvent(self, event):
        self.paint_mode = None

    def cell_rect(self, c: Cell, shrink: int = 2) -> QRect:
        x, y = c
        return QRect(
            self.margin_left + x * self.cell + shrink,
            self.margin_top + y * self.cell + shrink,
            self.cell - shrink * 2,
            self.cell - shrink * 2,
        )

    def cell_center(self, c: Cell) -> QPoint:
        x, y = c
        return QPoint(
            self.margin_left + x * self.cell + self.cell // 2,
            self.margin_top + y * self.cell + self.cell // 2,
        )

    def node_center(self, n: Node) -> QPoint:
        x, y, z = n
        if y < 0:
            return QPoint(
                self.margin_left + x * self.cell + self.cell // 2,
                self.margin_top + y * self.cell + self.cell // 2,
            )
        return self.cell_center((x, y))

    def draw_arrow(self, p: QPainter, a: QPoint, b: QPoint, color: QColor, width: int = 2, dashed: bool = False):
        pen = QPen(color, width)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(a, b)

        dx = b.x() - a.x()
        dy = b.y() - a.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        size = 4
        tip = QPoint(int(a.x() + dx * 0.66), int(a.y() + dy * 0.66))
        left = QPoint(int(tip.x() - ux * size - uy * size * 0.65), int(tip.y() - uy * size + ux * size * 0.65))
        right = QPoint(int(tip.x() - ux * size + uy * size * 0.65), int(tip.y() - uy * size - ux * size * 0.65))
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygon([tip, left, right]))

    def draw_grid(self, p: QPainter):
        p.fillRect(self.rect(), QColor(8, 13, 28))
        minor = QPen(QColor(34, 43, 70), 1)
        major = QPen(QColor(50, 62, 95), 1)
        for x in range(self.w + 1):
            p.setPen(major if x % 5 == 0 else minor)
            px = self.margin_left + x * self.cell
            p.drawLine(px, self.margin_top, px, self.margin_top + self.h * self.cell)
        for y in range(self.h + 1):
            p.setPen(major if y % 5 == 0 else minor)
            py = self.margin_top + y * self.cell
            p.drawLine(self.margin_left, py, self.margin_left + self.w * self.cell, py)

    def draw_resources(self, p: QPainter):
        mined_cells = {c for m in self.miners for c in m.cells}
        road_1f = {(x, y) for (x, y, z), load in self.road_load.items() if z == 0 and y >= 0} & self.resources
        for c in self.resources:
            if c in mined_cells:
                color = QColor(20, 118, 110)
            elif c in road_1f:
                color = QColor(38, 70, 110)
            else:
                color = QColor(22, 72, 108)
            p.setPen(QPen(QColor(14, 25, 40), 1))
            p.setBrush(QBrush(color))
            p.drawRect(self.cell_rect(c, 2))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(160, 220, 215, 150))
            p.drawEllipse(self.cell_center(c), 2, 2)

    def draw_roads_1f(self, p: QPainter):
        drawn = set()
        for _, path in self.paths:
            for a, b in zip(path, path[1:]):
                if a[2] != 0 or b[2] != 0:
                    continue
                if (a, b) in drawn:
                    continue
                drawn.add((a, b))
                self.draw_arrow(p, self.node_center(a), self.node_center(b), QColor(230, 55, 60), 2, False)

    def draw_miners(self, p: QPainter):
        for m in self.miners:
            cells = set(m.cells)
            line_shape = algo.is_line_shape(cells) if algo is not None else False
            miner_color = QColor(255, 242, 160) if line_shape else QColor(230, 245, 250)

            p.setPen(QPen(miner_color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)

            # Inset outlines so adjacent clusters do not draw over each other.
            inset = 3
            for x, y in cells:
                left = self.margin_left + x * self.cell + inset
                top = self.margin_top + y * self.cell + inset
                right = left + self.cell - inset * 2
                bottom = top + self.cell - inset * 2

                if (x, y - 1) not in cells:
                    p.drawLine(left, top, right, top)
                if (x, y + 1) not in cells:
                    p.drawLine(left, bottom, right, bottom)
                if (x - 1, y) not in cells:
                    p.drawLine(left, top, left, bottom)
                if (x + 1, y) not in cells:
                    p.drawLine(right, top, right, bottom)

            # Output direction is red now, no white output square.
            adj = None
            ox, oy = m.output
            for c in cells:
                if abs(c[0] - ox) + abs(c[1] - oy) == 1:
                    adj = c
                    break
            if adj is not None:
                self.draw_arrow(p, self.cell_center(adj), self.cell_center((ox, oy)), QColor(230, 55, 60), 2, False)

    def draw_roads_2f(self, p: QPainter):
        if not self.show_second_floor:
            return
        drawn = set()
        for _, path in self.paths:
            for a, b in zip(path, path[1:]):
                if not (a[2] == 1 or b[2] == 1):
                    continue
                if (a, b) in drawn:
                    continue
                drawn.add((a, b))
                if a[2] != b[2]:
                    self.draw_arrow(p, self.node_center(a), self.node_center(b), QColor(255, 145, 70), 2, True)
                else:
                    self.draw_arrow(p, self.node_center(a), self.node_center(b), QColor(255, 120, 70), 2, True)

    def draw_sinks(self, p: QPainter):
        # Top pass lanes: every column above the grid is a valid output pass.
        # Draw faint ticks for all lanes, and load numbers for used lanes.
        loads = self.output_loads()
        p.setFont(QFont("Arial", 7))
        for c in self.sink_ports:
            center = self.node_center((c[0], c[1], 0))
            r = QRect(center.x() - self.cell // 2 + 2, center.y() - self.cell // 2 + 2, self.cell - 4, self.cell - 4)
            load = loads.get(c, 0)
            if load > 0:
                p.setPen(QPen(QColor(255, 90, 90), 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r)
                p.setPen(QColor(255, 210, 170))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(load))
            else:
                p.setPen(QPen(QColor(95, 65, 75), 1, Qt.PenStyle.DotLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawLine(r.left(), r.center().y(), r.right(), r.center().y())

    def draw_legend(self, p: QPainter):
        s = self.summary()
        txt = f"resources={s['resources']}  mined={s['mined']}  unmined={s['unmined']}  miners={s['miners']}  2F={s['level2_cells']}  max_load={s['max_load']}/{s['cap']}  branch={s['branch_nodes']}  mixed_out={s['mixed_outputs']}  ramp_merge={s['ramp_merge']}  outer_unmined={s['outer_shell_unmined']}"
        p.setFont(QFont("Arial", 10))
        p.setPen(QColor(220, 230, 245))
        p.drawText(12, 22, txt)
        p.setFont(QFont("Arial", 8))
        p.setPen(QColor(150, 165, 195))
        p.drawText(12, self.height() - 12, "Left add | Right erase | Middle toggle | red=1F/output | dashed orange=2F | 2F drawn on top")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_grid(p)
        self.draw_resources(p)
        self.draw_roads_1f(p)
        self.draw_miners(p)
        self.draw_sinks(p)
        # 2F is intentionally drawn last / top depth.
        self.draw_roads_2f(p)
        self.draw_legend(p)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Miner Router Cluster Placement First + Unified Routing")
        self.canvas = GridCanvas()
        self.status = QLabel("Ready")
        self.status.setMinimumWidth(700)

        btn_demo = QPushButton("Demo Resource")
        btn_run = QPushButton("Run Optimize")
        btn_toggle_2f = QPushButton("Hide 2F")
        btn_clear_result = QPushButton("Clear Result")
        btn_clear_all = QPushButton("Clear All")
        btn_save = QPushButton("Save Map")
        btn_load = QPushButton("Load Map")
        self.btn_toggle_2f = btn_toggle_2f

        self.seed_box = QSpinBox()
        self.seed_box.setRange(0, 999999)
        self.seed_box.setValue(12)
        self.cap_box = QSpinBox()
        self.cap_box.setRange(1, 999)
        self.cap_box.setValue(32)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("seed"))
        toolbar.addWidget(self.seed_box)
        toolbar.addWidget(QLabel("cap"))
        toolbar.addWidget(self.cap_box)
        toolbar.addWidget(btn_demo)
        toolbar.addWidget(btn_run)
        toolbar.addWidget(btn_toggle_2f)
        toolbar.addWidget(btn_clear_result)
        toolbar.addWidget(btn_clear_all)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_load)
        toolbar.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.status)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        btn_demo.clicked.connect(self.load_demo)
        btn_run.clicked.connect(self.run_optimize)
        btn_toggle_2f.clicked.connect(self.toggle_second_floor)
        btn_clear_result.clicked.connect(self.clear_result)
        btn_clear_all.clicked.connect(self.clear_all)
        btn_save.clicked.connect(self.save_map)
        btn_load.clicked.connect(self.load_map)

        run_action = QAction("Run", self)
        run_action.setShortcut("Ctrl+R")
        run_action.triggered.connect(self.run_optimize)
        self.addAction(run_action)

        toggle_action = QAction("Toggle 2F", self)
        toggle_action.setShortcut("Ctrl+2")
        toggle_action.triggered.connect(self.toggle_second_floor)
        self.addAction(toggle_action)

        # Do not auto-optimize during window construction.
        # Startup stays fast; press Run Optimize to calculate placement.
        try:
            self.canvas.cap = self.cap_box.value()
            self.canvas.load_demo_resources(seed=self.seed_box.value())
            self.set_status_summary()
            self.status.setText("Demo resources loaded. Press Run Optimize. Output row is y=-1.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def set_status_summary(self):
        s = self.canvas.summary()
        self.status.setText(
            f"resources={s['resources']} | mined={s['mined']} | unmined={s['unmined']} | "
            f"miners={s['miners']} | road3d={s['road_cells_3d']} | 2F={s['level2_cells']} | "
            f"max_load={s['max_load']}/{s['cap']} | branch={s['branch_nodes']} | "
            f"mixed_out={s['mixed_outputs']} | ramp_merge={s['ramp_merge']} | outer_unmined={s['outer_shell_unmined']}"
        )

    def load_demo(self):
        try:
            self.status.setText("Loading demo and optimizing dynamic crisis-first routes...")
            QApplication.processEvents()
            self.canvas.cap = self.cap_box.value()
            self.canvas.load_demo_resources(seed=self.seed_box.value())
            self.canvas.run_optimizer()
            self.set_status_summary()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_optimize(self):
        try:
            self.status.setText("Optimizing dynamic crisis-first routes...")
            QApplication.processEvents()
            self.canvas.cap = self.cap_box.value()
            self.canvas.run_optimizer()
            self.set_status_summary()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def toggle_second_floor(self):
        self.canvas.show_second_floor = not self.canvas.show_second_floor
        self.btn_toggle_2f.setText("Hide 2F" if self.canvas.show_second_floor else "Show 2F")
        self.canvas.update()

    def clear_result(self):
        self.canvas.reset_result()
        self.set_status_summary()

    def clear_all(self):
        self.canvas.resources.clear()
        self.canvas.reset_result()
        self.set_status_summary()

    def save_map(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save resource map", "resource_map.csv", "CSV (*.csv);;Text (*.txt)")
        if path:
            self.canvas.save_map(path)
            self.status.setText(f"Saved: {path}")

    def load_map(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load resource map", "", "CSV (*.csv);;Text (*.txt);;All Files (*)")
        if path:
            try:
                self.canvas.load_map(path)
                self.set_status_summary()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(780, 880)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
