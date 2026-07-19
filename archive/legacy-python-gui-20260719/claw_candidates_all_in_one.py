"""All-candidate Shapez 2 Claw immediate-predecessor enumerator.

This is a single-file wrapper.  It embeds and compiles the C++20 fixed-width
frontier backend on first use, then exposes:

    claw_process(...)             -> first deterministic candidate
    claw_candidates(...)          -> lazy iterator over all distinct structural candidates
    claw_candidate_count(...)     -> number of distinct candidates
    claw_process_minimal(...)     -> minimum candidate under a selectable score

Important contract
------------------
The input is assumed to have already been classified as a *true Claw* by the
surrounding project (Pin Pusher is the only possible final non-rotation
operation).  This file enumerates immediate Pin-Pusher predecessor structures accepted by
the current project-SWAPABLE predecessor relation and returns one canonically
color-repaired exact representative for each structure.  It does not itself prove or
check the Swapper/Stacker exclusivity part of Claw classification.

Runtime dependency: the project's existing ``shape.py`` must be importable and
``g++`` (or ``$CXX``) must support C++20.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal, Optional
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

try:
    from shape import Shape
except ImportError as exc:  # pragma: no cover - environment-specific
    raise ImportError(
        "claw_candidates_all_in_one.py must be placed where the project's "
        "shape.py is importable"
    ) from exc


class NoClawPredecessor(RuntimeError):
    """No candidate exists in the enumerated predecessor relation."""


class ClawEnumeratorInternalError(RuntimeError):
    """Compiler, backend protocol, or independent-certificate failure."""


@dataclass(frozen=True)
class CandidateResult:
    predecessor: str
    structural: str
    axis: int
    bottom_mask: int
    index: int


@dataclass(frozen=True)
class EnumerationStats:
    unique_structural: int
    transitions: int
    max_failed_states: int


_CPP_SOURCE = r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <future>
#include <functional>
#include <iostream>
#include <numeric>
#include <optional>
#include <queue>
#include <sstream>
#include <string>
#include <tuple>
#include <unordered_set>
#include <utility>
#include <vector>

namespace shapez2_claw {

constexpr int kColumns = 4;
constexpr int kDfaStates = 19;

enum class Cell : std::uint8_t { Empty = 0, Ordinary = 1, Pin = 2, Crystal = 3 };
using Row = std::uint8_t;  // Four cells, two bits per cell.

int Left(int q) { return (q + 3) & 3; }
int Right(int q) { return (q + 1) & 3; }

Cell DecodeCell(char ch) {
  if (ch == '-') return Cell::Empty;
  if (ch == 'P') return Cell::Pin;
  if (ch == 'c') return Cell::Crystal;
  // C, R, S and W are physically identical ordinary non-pin pieces.
  return Cell::Ordinary;
}
char EncodeCell(Cell c) {
  if (c == Cell::Ordinary) return 'S';
  if (c == Cell::Pin) return 'P';
  if (c == Cell::Crystal) return 'c';
  return '-';
}
Cell Get(Row row, int q) { return static_cast<Cell>((row >> (2 * q)) & 3u); }
Row Set(Row row, int q, Cell c) {
  return static_cast<Row>((row & ~(3u << (2 * q))) |
                          (static_cast<std::uint8_t>(c) << (2 * q)));
}
bool Occupied(Cell c) { return c != Cell::Empty; }
bool NonPin(Cell c) { return c == Cell::Ordinary || c == Cell::Crystal; }
int OccupiedMask(Row row) {
  int mask = 0;
  for (int q = 0; q < kColumns; ++q) if (Occupied(Get(row, q))) mask |= 1 << q;
  return mask;
}
int CrystalMask(Row row) {
  int mask = 0;
  for (int q = 0; q < kColumns; ++q) if (Get(row, q) == Cell::Crystal) mask |= 1 << q;
  return mask;
}
std::string RowString(Row row) {
  std::string out(kColumns, '-');
  for (int q = 0; q < kColumns; ++q) out[q] = EncodeCell(Get(row, q));
  return out;
}

// ---------------------------------------------------------------------------
// Exact width-four support automaton.
// ---------------------------------------------------------------------------
// A support relation is graph reachability from the ground.  The automaton
// eliminates finalized rows while retaining exactly the reachability relation
// among the current four cells and the ground, plus positive/negative future
// obligations.  Its state space is finite because the width is fixed at four.

struct SupportState {
  Row row = 0;
  std::uint8_t desired = 0;
  std::uint32_t closure = 0;  // 5x5 Boolean transitive-closure matrix.
  std::uint16_t positive = 0; // Bit m: a future cell from mask m must reach root.
  std::uint8_t negative = 0;  // Future cells that must not reach root.
  bool operator==(const SupportState& o) const {
    return row == o.row && desired == o.desired && closure == o.closure &&
           positive == o.positive && negative == o.negative;
  }
};

struct SupportHash {
  std::size_t operator()(const SupportState& s) const noexcept {
    std::uint64_t x = s.closure ^ (std::uint64_t(s.positive) << 32) ^
                      (std::uint64_t(s.negative) << 40) ^
                      (std::uint64_t(s.row) << 48) ^
                      (std::uint64_t(s.desired) << 56);
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    return static_cast<std::size_t>(x);
  }
};

bool MatrixGet(std::uint32_t matrix, int i, int j) {
  return (matrix >> (i * 5 + j)) & 1u;
}
void TransitiveClosure(std::array<std::uint16_t, 9>& graph, int n) {
  for (int k = 0; k < n; ++k)
    for (int i = 0; i < n; ++i)
      if (graph[i] & (1u << k)) graph[i] |= graph[k];
}
std::uint16_t MinimalAntichain(std::uint16_t bits) {
  std::uint16_t out = 0;
  for (int population = 1; population <= 4; ++population) {
    for (int mask = 1; mask < 16; ++mask) {
      if (__builtin_popcount(static_cast<unsigned>(mask)) != population ||
          !(bits & (1u << mask))) continue;
      bool dominated = false;
      for (int prior = 1; prior < 16; ++prior) {
        if ((out & (1u << prior)) && ((prior & mask) == prior)) {
          dominated = true;
          break;
        }
      }
      if (!dominated) out |= 1u << mask;
    }
  }
  return out;
}

SupportState SupportStart(Row row, std::uint8_t desired) {
  constexpr int root = 4;
  std::array<std::uint16_t, 9> graph{};
  graph[root] |= 1u << root;
  for (int q = 0; q < kColumns; ++q) {
    if (!Occupied(Get(row, q))) continue;
    graph[q] |= 1u << q;
    graph[root] |= 1u << q;  // Bottom row is grounded.
  }
  for (int q = 0; q < kColumns; ++q) {
    const int n = Right(q);
    if (NonPin(Get(row, q)) && NonPin(Get(row, n))) {
      graph[q] |= 1u << n;
      graph[n] |= 1u << q;
    }
  }
  TransitiveClosure(graph, 5);
  std::uint32_t closure = 0;
  for (int i = 0; i < 5; ++i)
    for (int j = 0; j < 5; ++j)
      if (graph[i] & (1u << j)) closure |= 1u << (i * 5 + j);
  return {row, desired, closure, 0, 0};
}

std::optional<SupportState> SupportStep(const SupportState& old, Row next_row,
                                        std::uint8_t next_desired) {
  constexpr int root = 4;
  std::array<std::uint16_t, 9> graph{};
  for (int i = 0; i < 5; ++i)
    for (int j = 0; j < 5; ++j)
      if (MatrixGet(old.closure, i, j)) graph[i] |= 1u << j;

  for (int q = 0; q < kColumns; ++q)
    if (Occupied(Get(next_row, q))) graph[5 + q] |= 1u << (5 + q);

  for (int q = 0; q < kColumns; ++q) {
    if (!Occupied(Get(old.row, q)) || !Occupied(Get(next_row, q))) continue;
    graph[q] |= 1u << (5 + q);  // Lower occupied cell supports upper cell.
    if (Get(old.row, q) == Cell::Crystal && Get(next_row, q) == Cell::Crystal)
      graph[5 + q] |= 1u << q;  // Crystal hanging is bidirectional.
  }
  for (int q = 0; q < kColumns; ++q) {
    const int n = Right(q);
    if (NonPin(Get(next_row, q)) && NonPin(Get(next_row, n))) {
      graph[5 + q] |= 1u << (5 + n);
      graph[5 + n] |= 1u << (5 + q);
    }
  }
  TransitiveClosure(graph, 9);

  std::uint16_t positive = 0;
  for (int obligation = 1; obligation < 16; ++obligation) {
    if (!(old.positive & (1u << obligation))) continue;
    bool already_satisfied = false;
    for (int q = 0; q < kColumns; ++q)
      if ((obligation >> q & 1) && (graph[root] & (1u << q))) {
        already_satisfied = true;
        break;
      }
    if (already_satisfied) continue;
    int incoming = 0;
    for (int v = 0; v < kColumns; ++v)
      for (int q = 0; q < kColumns; ++q)
        if ((obligation >> q & 1) && (graph[5 + v] & (1u << q))) {
          incoming |= 1 << v;
          break;
        }
    if (!incoming) return std::nullopt;
    positive |= 1u << incoming;
  }

  for (int q = 0; q < kColumns; ++q)
    if ((old.negative >> q & 1) && (graph[root] & (1u << q)))
      return std::nullopt;

  int negative = 0;
  for (int v = 0; v < kColumns; ++v)
    for (int q = 0; q < kColumns; ++q)
      if ((old.negative >> q & 1) && (graph[5 + v] & (1u << q))) {
        negative |= 1 << v;
        break;
      }

  // Finalize the old row exactly.
  for (int q = 0; q < kColumns; ++q) {
    if (!Occupied(Get(old.row, q))) continue;
    const bool reached = graph[root] & (1u << q);
    int incoming = 0;
    for (int v = 0; v < kColumns; ++v)
      if (graph[5 + v] & (1u << q)) incoming |= 1 << v;
    const bool wanted = old.desired >> q & 1;
    if (wanted) {
      if (!reached) {
        if (!incoming) return std::nullopt;
        positive |= 1u << incoming;
      }
    } else {
      if (reached) return std::nullopt;
      negative |= incoming;
    }
  }

  for (int v = 0; v < kColumns; ++v)
    if ((negative >> v & 1) && (graph[root] & (1u << (5 + v))))
      return std::nullopt;

  std::uint16_t filtered = 0;
  for (int obligation = 1; obligation < 16; ++obligation) {
    if (!(positive & (1u << obligation))) continue;
    bool satisfied = false;
    for (int v = 0; v < kColumns; ++v)
      if ((obligation >> v & 1) && (graph[root] & (1u << (5 + v)))) {
        satisfied = true;
        break;
      }
    if (!satisfied) filtered |= 1u << obligation;
  }
  filtered = MinimalAntichain(filtered);

  const int keep[5] = {5, 6, 7, 8, root};
  std::uint32_t closure = 0;
  for (int i = 0; i < 5; ++i)
    for (int j = 0; j < 5; ++j)
      if (graph[keep[i]] & (1u << keep[j])) closure |= 1u << (i * 5 + j);

  return SupportState{next_row, next_desired, closure, filtered,
                      static_cast<std::uint8_t>(negative)};
}

bool SupportFinish(const SupportState& state) {
  const auto closed = SupportStep(state, 0, 0);
  return closed && closed->positive == 0 && closed->negative == 0;
}

// ---------------------------------------------------------------------------
// Frontier connectivity automaton for the crystal set D destroyed by trim.
// ---------------------------------------------------------------------------

std::uint16_t DestroyPack(int mask, const std::array<int, 4>& labels) {
  std::uint16_t out = mask & 15;
  for (int q = 0; q < 4; ++q)
    out |= static_cast<std::uint16_t>(labels[q] + 1) << (4 + 3 * q);
  return out;
}
int DestroyMask(std::uint16_t state) { return state & 15; }
std::array<int, 4> DestroyLabels(std::uint16_t state) {
  std::array<int, 4> out{};
  for (int q = 0; q < 4; ++q) out[q] = ((state >> (4 + 3 * q)) & 7) - 1;
  return out;
}
std::uint16_t DestroyStart(int mask) {
  std::array<int, 4> labels;
  labels.fill(-1);
  int id = 0;
  for (int q = 0; q < 4; ++q) {
    if (!(mask >> q & 1) || labels[q] >= 0) continue;
    std::queue<int> pending;
    pending.push(q);
    labels[q] = id;
    while (!pending.empty()) {
      const int a = pending.front();
      pending.pop();
      for (int n : {Left(a), Right(a)}) {
        if ((mask >> n & 1) && labels[n] < 0) {
          labels[n] = id;
          pending.push(n);
        }
      }
    }
    ++id;
  }
  return DestroyPack(mask, labels);
}

std::optional<std::uint16_t> DestroyStep(std::uint16_t old_state, int next_mask) {
  const auto old_labels = DestroyLabels(old_state);
  const int old_mask = DestroyMask(old_state);
  int old_count = 0;
  for (int q = 0; q < 4; ++q)
    if (old_labels[q] >= 0) old_count = std::max(old_count, old_labels[q] + 1);

  const int n = old_count + 4;
  int parent[8];
  for (int i = 0; i < n; ++i) parent[i] = i;
  auto find = [&](int a) {
    while (parent[a] != a) {
      parent[a] = parent[parent[a]];
      a = parent[a];
    }
    return a;
  };
  auto unite = [&](int a, int b) {
    a = find(a);
    b = find(b);
    if (a != b) parent[std::max(a, b)] = std::min(a, b);
  };

  for (int q = 0; q < 4; ++q) {
    const int right = Right(q);
    if ((next_mask >> q & 1) && (next_mask >> right & 1))
      unite(old_count + q, old_count + right);
    if ((old_mask >> q & 1) && (next_mask >> q & 1))
      unite(old_labels[q], old_count + q);
  }

  bool continues[8]{};
  for (int q = 0; q < 4; ++q)
    if (next_mask >> q & 1) continues[find(old_count + q)] = true;

  bool existed[4]{};
  for (int q = 0; q < 4; ++q)
    if (old_labels[q] >= 0) existed[old_labels[q]] = true;
  for (int label = 0; label < 4; ++label)
    if (existed[label] && !continues[find(label)]) return std::nullopt;

  std::vector<std::pair<int, int>> roots;
  for (int root = 0; root < n; ++root) {
    if (!continues[root]) continue;
    int first_q = 9;
    for (int q = 0; q < 4; ++q)
      if ((next_mask >> q & 1) && find(old_count + q) == root)
        first_q = std::min(first_q, q);
    roots.push_back({first_q, root});
  }
  std::sort(roots.begin(), roots.end());
  int canonical[8];
  std::fill(std::begin(canonical), std::end(canonical), -1);
  for (int i = 0; i < static_cast<int>(roots.size()); ++i)
    canonical[roots[i].second] = i;

  std::array<int, 4> labels;
  labels.fill(-1);
  for (int q = 0; q < 4; ++q)
    if (next_mask >> q & 1)
      labels[q] = canonical[find(old_count + q)];
  return DestroyPack(next_mask, labels);
}

// ---------------------------------------------------------------------------
// Project-level SWAPABLE contract.
// ---------------------------------------------------------------------------

constexpr int kCornerDfa[kDfaStates][4] = {
    {1,2,3,4},{1,5,6,4},{7,8,18,18},{9,8,3,10},{11,12,6,4},
    {7,13,18,4},{6,12,6,18},{7,13,6,4},{9,8,18,18},{9,13,6,10},
    {14,12,6,10},{15,16,6,4},{6,12,18,18},{9,13,18,10},
    {9,8,6,10},{15,17,6,4},{11,16,18,18},{15,17,18,4},
    {18,18,18,18}};

int CornerSymbol(Cell c) {
  if (c == Cell::Ordinary) return 0;
  if (c == Cell::Empty) return 1;
  if (c == Cell::Pin) return 2;
  return 3;
}

// Code = committed_state * 19 + pending_state.  pending includes trailing
// gaps; committed stops at the last occupied cell, matching rstrip('-').
std::uint16_t PillarStep(std::uint16_t code, Cell c) {
  const int committed = code / 19;
  const int pending = code % 19;
  const int next = kCornerDfa[pending][CornerSymbol(c)];
  if (c == Cell::Empty) return static_cast<std::uint16_t>(committed * 19 + next);
  return static_cast<std::uint16_t>(next * 19 + next);
}
bool PillarAccept(std::uint16_t code) { return code / 19 != 18; }

int AxisMaskA(int axis) { return axis == 0 ? 0b0011 : 0b1001; }
int AxisMaskB(int axis) { return axis == 0 ? 0b1100 : 0b0110; }
Row MaskRow(Row row, int mask) {
  Row out = 0;
  for (int q = 0; q < 4; ++q) if (mask >> q & 1) out = Set(out, q, Get(row, q));
  return out;
}

struct ProjectState {
  std::array<std::uint16_t, 4> pillar{};
  SupportState half_a{};
  SupportState half_b{};
  std::uint8_t occupied_columns = 0;
  bool operator==(const ProjectState& o) const {
    return pillar == o.pillar && half_a == o.half_a && half_b == o.half_b &&
           occupied_columns == o.occupied_columns;
  }
};

ProjectState ProjectStart(Row row, int axis) {
  ProjectState out;
  for (int q = 0; q < 4; ++q) out.pillar[q] = PillarStep(0, Get(row, q));
  const Row a = MaskRow(row, AxisMaskA(axis));
  const Row b = MaskRow(row, AxisMaskB(axis));
  out.half_a = SupportStart(a, OccupiedMask(a));
  out.half_b = SupportStart(b, OccupiedMask(b));
  out.occupied_columns = OccupiedMask(row);
  return out;
}

std::optional<ProjectState> ProjectStep(const ProjectState& old, Row row,
                                        int axis) {
  ProjectState next = old;
  for (int q = 0; q < 4; ++q)
    next.pillar[q] = PillarStep(old.pillar[q], Get(row, q));
  const Row a = MaskRow(row, AxisMaskA(axis));
  const Row b = MaskRow(row, AxisMaskB(axis));
  const auto half_a = SupportStep(old.half_a, a, OccupiedMask(a));
  const auto half_b = SupportStep(old.half_b, b, OccupiedMask(b));
  if (!half_a || !half_b) return std::nullopt;
  next.half_a = *half_a;
  next.half_b = *half_b;
  next.occupied_columns |= OccupiedMask(row);
  return next;
}

bool ProjectFinish(const ProjectState& state, int layers) {
  for (const auto pillar : state.pillar) if (!PillarAccept(pillar)) return false;
  if (!SupportFinish(state.half_a) || !SupportFinish(state.half_b)) return false;
  // Legacy classifier's multi-layer q1-only branch exclusion.
  if (layers > 1 && state.occupied_columns == 1) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Target-guided exact inverse.
// ---------------------------------------------------------------------------

void HashCombine(std::size_t& h, std::uint64_t x) {
  x ^= x >> 33;
  x *= 0xff51afd7ed558ccdULL;
  x ^= x >> 33;
  h ^= static_cast<std::size_t>(x) + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
}

struct Key {
  std::array<std::uint16_t, 4> consumed{};
  SupportState post{};  // Exact support immediately after D removal.
  SupportState pre{};   // Exact support of the predecessor.
  std::uint16_t destroy = 0;
  ProjectState project{};
  std::uint8_t seen_unsupported = 0;
  bool operator==(const Key& o) const {
    return consumed == o.consumed && post == o.post && pre == o.pre &&
           destroy == o.destroy && project == o.project &&
           seen_unsupported == o.seen_unsupported;
  }
};
struct KeyHash {
  std::size_t operator()(const Key& key) const noexcept {
    std::size_t h = 0;
    for (auto x : key.consumed) HashCombine(h, x);
    SupportHash support_hash;
    HashCombine(h, support_hash(key.post));
    HashCombine(h, support_hash(key.pre));
    HashCombine(h, key.destroy);
    for (auto x : key.project.pillar) HashCombine(h, x);
    HashCombine(h, support_hash(key.project.half_a));
    HashCombine(h, support_hash(key.project.half_b));
    HashCombine(h, key.project.occupied_columns);
    HashCombine(h, key.seen_unsupported);
    return h;
  }
};

struct Decision {
  Row fixed = 0;  // K crystals plus S/P pieces.
  std::uint8_t destroy = 0;
  std::uint8_t unsupported = 0;
};
struct Token {
  int target_layer = 0;
  Cell kind = Cell::Empty;
};
struct Result {
  bool ok = false;
  std::vector<Row> rows;
  std::uint64_t transitions = 0;
  std::uint64_t max_failed_states = 0;
  int bottom_mask = 0;
  int axis = -1;
};

std::vector<std::vector<int>> OrdinaryComponents(int mask) {
  std::vector<std::vector<int>> out;
  bool seen[4]{};
  for (int q = 0; q < 4; ++q) {
    if (!(mask >> q & 1) || seen[q]) continue;
    std::vector<int> component;
    std::queue<int> pending;
    pending.push(q);
    seen[q] = true;
    while (!pending.empty()) {
      const int a = pending.front();
      pending.pop();
      component.push_back(a);
      for (int n : {Left(a), Right(a)}) {
        if ((mask >> n & 1) && !seen[n]) {
          seen[n] = true;
          pending.push(n);
        }
      }
    }
    out.push_back(component);
  }
  return out;
}

int BlockerHeight(
    const std::array<std::vector<int>, 4>& highest_crystal_below,
    const std::array<std::vector<Token>, 4>& sequences,
    const std::array<std::uint16_t, 4>& consumed_before,
    int bottom_mask, int q, int source_result_layer) {
  int highest = (bottom_mask >> q & 1) ? 0 : -1;
  highest = std::max(highest, highest_crystal_below[q][source_result_layer]);
  if (consumed_before[q] > 0)
    highest = std::max(
        highest, sequences[q][consumed_before[q] - 1].target_layer);
  return highest;
}

std::vector<Row> TopRows() {
  std::vector<Row> rows;
  for (int row = 0; row < 256; ++row)
    if (CrystalMask(static_cast<Row>(row))) rows.push_back(static_cast<Row>(row));
  std::sort(rows.begin(), rows.end(), [](int a, int b) {
    auto score = [](int row) {
      int occupied = 0;
      int noncrystal = 0;
      for (int q = 0; q < 4; ++q) {
        const Cell c = Get(static_cast<Row>(row), q);
        occupied += c != Cell::Empty;
        noncrystal += c == Cell::Ordinary || c == Cell::Pin;
      }
      return std::tuple<int, int, int>(occupied, noncrystal, row);
    };
    return score(a) < score(b);
  });
  return rows;
}


std::string RowsCode(const std::vector<Row>& rows);

struct EnumerationSink {
  std::unordered_set<std::string> seen;
  std::function<void(const std::string&, int, int)> callback;
  std::uint64_t emitted = 0;
  std::uint64_t limit = 0;  // 0 = unlimited
  bool stop = false;

  void Emit(const std::vector<Row>& rows, int axis, int bottom_mask) {
    if (stop) return;
    const std::string code = RowsCode(rows);
    if (!seen.insert(code).second) return;
    ++emitted;
    if (callback) callback(code, axis, bottom_mask);
    if (limit && emitted >= limit) stop = true;
  }
};

Result SolveAxis(const std::vector<Row>& target, int axis, bool allow_unsupported,
                 bool require_unsupported, bool prefer_unsupported,
                 std::atomic<bool>* cancel) {
  const int layers = static_cast<int>(target.size());
  Result result;
  result.axis = axis;
  if (layers < 2) return result;
  for (int q = 0; q < 4; ++q)
    if (Get(target[0], q) == Cell::Crystal) return result;

  std::array<std::vector<Token>, 4> raw_sequences;
  std::vector<int> bottom_pin_columns;
  for (int q = 0; q < 4; ++q) {
    for (int layer = 0; layer < layers; ++layer) {
      const Cell c = Get(target[layer], q);
      if (c == Cell::Ordinary || c == Cell::Pin)
        raw_sequences[q].push_back({layer, c});
    }
    if (Get(target[0], q) == Cell::Pin) bottom_pin_columns.push_back(q);
  }

  // A surviving source crystal at row s appears at target row s+1.
  std::vector<int> surviving_crystals(layers - 1, 0);
  for (int source = 0; source < layers - 1; ++source) {
    int mask = 0;
    for (int q = 0; q < 4; ++q)
      if (Get(target[source + 1], q) == Cell::Crystal) mask |= 1 << q;
    surviving_crystals[source] = mask;
  }

  // O(1) blocker queries: highest target crystal strictly below each row.
  std::array<std::vector<int>, 4> highest_crystal_below;
  for (int q = 0; q < 4; ++q) {
    highest_crystal_below[q].assign(layers + 1, -1);
    int highest = -1;
    for (int row = 0; row <= layers; ++row) {
      highest_crystal_below[q][row] = highest;
      if (row < layers && Get(target[row], q) == Cell::Crystal) highest = row;
    }
  }

  static const std::vector<Row> top_rows = TopRows();

  std::vector<int> bottom_subsets(1 << bottom_pin_columns.size());
  std::iota(bottom_subsets.begin(), bottom_subsets.end(), 0);
  std::sort(bottom_subsets.begin(), bottom_subsets.end(), [](int a, int b) {
    const int pa = __builtin_popcount(static_cast<unsigned>(a));
    const int pb = __builtin_popcount(static_cast<unsigned>(b));
    return pa != pb ? pa > pb : a > b;
  });

  std::vector<int> base_choose_order(16);
  std::iota(base_choose_order.begin(), base_choose_order.end(), 0);
  std::sort(base_choose_order.begin(), base_choose_order.end(), [](int a, int b) {
    const int pa = __builtin_popcount(static_cast<unsigned>(a));
    const int pb = __builtin_popcount(static_cast<unsigned>(b));
    return pa != pb ? pa < pb : a < b;
  });

  std::array<std::vector<int>, 16> destroy_orders;
  std::array<std::vector<int>, 16> unsupported_orders;
  for (int free = 0; free < 16; ++free) {
    for (int subset = free;; subset = (subset - 1) & free) {
      destroy_orders[free].push_back(subset);
      if (subset == 0) break;
    }
    std::sort(destroy_orders[free].begin(), destroy_orders[free].end(),
              [free](int a, int b) {
                if (a == 0 || b == 0) return a == 0;
                if (a == free || b == free) return a == free;
                const int pa = __builtin_popcount(static_cast<unsigned>(a));
                const int pb = __builtin_popcount(static_cast<unsigned>(b));
                return pa != pb ? pa > pb : a > b;
              });
    unsupported_orders[free].push_back(0);
    std::vector<int> rest;
    for (int subset = free; subset; subset = (subset - 1) & free)
      rest.push_back(subset);
    std::sort(rest.begin(), rest.end(), [](int a, int b) {
      const int pa = __builtin_popcount(static_cast<unsigned>(a));
      const int pb = __builtin_popcount(static_cast<unsigned>(b));
      return pa != pb ? pa < pb : a < b;
    });
    unsupported_orders[free].insert(unsupported_orders[free].end(), rest.begin(),
                                    rest.end());
  }

  for (int bottom_subset : bottom_subsets) {
    if (cancel && cancel->load(std::memory_order_relaxed)) return result;

    int bottom_mask = 0;
    for (int j = 0; j < static_cast<int>(bottom_pin_columns.size()); ++j)
      if (bottom_subset >> j & 1) bottom_mask |= 1 << bottom_pin_columns[j];

    auto sequences = raw_sequences;
    bool valid = true;
    for (int q = 0; q < 4; ++q) {
      if (!(bottom_mask >> q & 1)) continue;
      if (sequences[q].empty() || sequences[q][0].target_layer != 0 ||
          sequences[q][0].kind != Cell::Pin) {
        valid = false;
        break;
      }
      sequences[q].erase(sequences[q].begin());
    }
    if (!valid) continue;

    std::array<std::uint16_t, 4> goal{};
    for (int q = 0; q < 4; ++q) goal[q] = sequences[q].size();

    std::vector<std::unordered_set<Key, KeyHash>> failed(layers);
    std::vector<Decision> path(layers - 1);
    Row final_top = 0;

    std::function<bool(int, const std::optional<Key>&)> dfs =
        [&](int source, const std::optional<Key>& old_key) -> bool {
      if (cancel && cancel->load(std::memory_order_relaxed)) return false;

      if (source == layers - 1) {
        if (!old_key) return false;
        const Key& key = *old_key;
        if (key.consumed != goal || !SupportFinish(key.post)) return false;
        if (require_unsupported && !key.seen_unsupported) return false;
        const int previous_nondestroyed_crystals = CrystalMask(key.post.row);

        for (Row top : top_rows) {
          const int destroy = CrystalMask(top);
          if (destroy & previous_nondestroyed_crystals) continue;
          const auto destroy_state = DestroyStep(key.destroy, destroy);
          if (!destroy_state) continue;
          const auto pre = SupportStep(key.pre, top, OccupiedMask(top));
          if (!pre || !SupportFinish(*pre)) continue;
          const auto project = ProjectStep(key.project, top, axis);
          if (!project || !ProjectFinish(*project, layers)) continue;
          final_top = top;
          if (cancel) cancel->store(true, std::memory_order_relaxed);
          return true;
        }
        return false;
      }

      if (old_key && failed[source].count(*old_key)) return false;

      const int result_layer = source + 1;
      const int keep_crystals = surviving_crystals[source];
      std::array<std::uint16_t, 4> consumed{};
      if (old_key) consumed = old_key->consumed;

      bool eligible[4]{};
      int immediately_static = 0;
      for (int q = 0; q < 4; ++q) {
        eligible[q] = !(keep_crystals >> q & 1) &&
                      consumed[q] < sequences[q].size() &&
                      sequences[q][consumed[q]].target_layer <= result_layer;
        if (eligible[q] &&
            sequences[q][consumed[q]].target_layer == result_layer)
          immediately_static |= 1 << q;
      }

      auto choose_order = base_choose_order;
      std::sort(choose_order.begin(), choose_order.end(),
                [immediately_static](int a, int b) {
                  const int da = __builtin_popcount(
                      static_cast<unsigned>(a ^ immediately_static));
                  const int db = __builtin_popcount(
                      static_cast<unsigned>(b ^ immediately_static));
                  if (da != db) return da < db;
                  const int ma = __builtin_popcount(
                      static_cast<unsigned>(a & immediately_static));
                  const int mb = __builtin_popcount(
                      static_cast<unsigned>(b & immediately_static));
                  if (ma != mb) return ma > mb;
                  return __builtin_popcount(static_cast<unsigned>(a)) <
                         __builtin_popcount(static_cast<unsigned>(b));
                });

      for (int choose : choose_order) {
        if (choose & keep_crystals) continue;
        bool bad = false;
        for (int q = 0; q < 4; ++q)
          if ((choose >> q & 1) && !eligible[q]) {
            bad = true;
            break;
          }
        if (bad) continue;

        Row fixed = 0;
        std::array<int, 4> target_layers;
        target_layers.fill(-1);
        auto next_consumed = consumed;
        int desired_support = keep_crystals;
        for (int q = 0; q < 4; ++q) {
          if (keep_crystals >> q & 1) {
            fixed = Set(fixed, q, Cell::Crystal);
          } else if (choose >> q & 1) {
            const Token token = sequences[q][consumed[q]];
            fixed = Set(fixed, q, token.kind);
            target_layers[q] = token.target_layer;
            ++next_consumed[q];
            if (token.target_layer == result_layer) desired_support |= 1 << q;
          }
        }

        const int fixed_occupied = OccupiedMask(fixed);
        int falling_ordinary = 0;
        for (int q = 0; q < 4; ++q)
          if (Get(fixed, q) == Cell::Ordinary && !(desired_support >> q & 1))
            falling_ordinary |= 1 << q;

        bool landing_ok = true;
        for (const auto& component : OrdinaryComponents(falling_ordinary)) {
          int target_layer = -2;
          for (int q : component) {
            if (target_layer == -2) target_layer = target_layers[q];
            else if (target_layer != target_layers[q]) {
              landing_ok = false;
              break;
            }
          }
          if (!landing_ok) break;
          if (target_layer < 0 || target_layer >= result_layer) {
            landing_ok = false;
            break;
          }
          int highest = -1;
          for (int q : component)
            highest = std::max(highest,
                BlockerHeight(highest_crystal_below, sequences, consumed,
                              bottom_mask, q, result_layer));
          if (highest + 1 != target_layer) {
            landing_ok = false;
            break;
          }
        }
        if (!landing_ok) continue;

        for (int q = 0; q < 4; ++q) {
          if (Get(fixed, q) != Cell::Pin || (desired_support >> q & 1)) continue;
          const int target_layer = target_layers[q];
          if (target_layer < 0 || target_layer >= result_layer ||
              BlockerHeight(highest_crystal_below, sequences, consumed,
                            bottom_mask, q, result_layer) + 1 != target_layer) {
            landing_ok = false;
            break;
          }
        }
        if (!landing_ok) continue;

        const int free = (~fixed_occupied) & 15;
        for (int destroy : destroy_orders[free]) {
          const int remaining = free & ~destroy;
          std::vector<int> local_unsupported = unsupported_orders[remaining];
          if (prefer_unsupported) {
            std::stable_sort(local_unsupported.begin(), local_unsupported.end(),
                             [](int a, int b) { return (a == 0) < (b == 0); });
          }
          for (int unsupported : local_unsupported) {
            if (!allow_unsupported && unsupported) continue;
            ++result.transitions;

            if (source == 0 &&
                (fixed_occupied | destroy | unsupported) != bottom_mask)
              continue;

            const int nondestroyed = keep_crystals | unsupported;
            if (destroy & nondestroyed) continue;
            bool adjacent_mixed_crystal = false;
            for (int q = 0; q < 4; ++q) {
              if ((destroy >> q & 1) &&
                  (((nondestroyed >> Left(q)) & 1) ||
                   ((nondestroyed >> Right(q)) & 1))) {
                adjacent_mixed_crystal = true;
                break;
              }
            }
            if (adjacent_mixed_crystal) continue;

            if (source > 0) {
              const int prior_destroy = DestroyMask(old_key->destroy);
              const int prior_nondestroyed = CrystalMask(old_key->post.row);
              if ((prior_destroy & nondestroyed) ||
                  (destroy & prior_nondestroyed))
                continue;
            }

            Row post_row = fixed;
            for (int q = 0; q < 4; ++q)
              if (unsupported >> q & 1)
                post_row = Set(post_row, q, Cell::Crystal);

            std::optional<SupportState> post;
            if (source == 0) {
              Row generated = 0;
              for (int q = 0; q < 4; ++q)
                if (bottom_mask >> q & 1)
                  generated = Set(generated, q, Cell::Pin);
              post = SupportStep(SupportStart(generated, bottom_mask), post_row,
                                 desired_support);
            } else {
              post = SupportStep(old_key->post, post_row, desired_support);
            }
            if (!post) continue;

            Row source_row = post_row;
            for (int q = 0; q < 4; ++q)
              if (destroy >> q & 1)
                source_row = Set(source_row, q, Cell::Crystal);

            const auto pre = source == 0
                ? std::optional<SupportState>(
                      SupportStart(source_row, OccupiedMask(source_row)))
                : SupportStep(old_key->pre, source_row,
                              OccupiedMask(source_row));
            if (!pre) continue;

            const auto destroy_state = source == 0
                ? std::optional<std::uint16_t>(DestroyStart(destroy))
                : DestroyStep(old_key->destroy, destroy);
            if (!destroy_state) continue;

            std::optional<ProjectState> project = source == 0
                ? std::optional<ProjectState>(ProjectStart(source_row, axis))
                : ProjectStep(old_key->project, source_row, axis);
            if (!project) continue;

            Key next{next_consumed, *post, *pre, *destroy_state, *project,
                     static_cast<std::uint8_t>((old_key && old_key->seen_unsupported) ||
                                               unsupported != 0)};
            path[source] = {fixed, static_cast<std::uint8_t>(destroy),
                            static_cast<std::uint8_t>(unsupported)};
            if (dfs(source + 1, next)) return true;
          }
        }
      }

      if (old_key) {
        failed[source].insert(*old_key);
        result.max_failed_states =
            std::max<std::uint64_t>(result.max_failed_states,
                                    failed[source].size());
      }
      return false;
    };

    if (dfs(0, std::nullopt)) {
      result.ok = true;
      result.bottom_mask = bottom_mask;
      result.rows.resize(layers);
      for (int source = 0; source < layers - 1; ++source) {
        Row row = path[source].fixed;
        for (int q = 0; q < 4; ++q)
          if ((path[source].destroy | path[source].unsupported) >> q & 1)
            row = Set(row, q, Cell::Crystal);
        result.rows[source] = row;
      }
      result.rows[layers - 1] = final_top;
      return result;
    }
  }

  return result;
}


Result EnumerateAxis(const std::vector<Row>& target, int axis, bool allow_unsupported,
                     bool require_unsupported, bool prefer_unsupported,
                     struct EnumerationSink* sink) {
  const int layers = static_cast<int>(target.size());
  Result result;
  result.axis = axis;
  if (layers < 2) return result;
  for (int q = 0; q < 4; ++q)
    if (Get(target[0], q) == Cell::Crystal) return result;

  std::array<std::vector<Token>, 4> raw_sequences;
  std::vector<int> bottom_pin_columns;
  for (int q = 0; q < 4; ++q) {
    for (int layer = 0; layer < layers; ++layer) {
      const Cell c = Get(target[layer], q);
      if (c == Cell::Ordinary || c == Cell::Pin)
        raw_sequences[q].push_back({layer, c});
    }
    if (Get(target[0], q) == Cell::Pin) bottom_pin_columns.push_back(q);
  }

  // A surviving source crystal at row s appears at target row s+1.
  std::vector<int> surviving_crystals(layers - 1, 0);
  for (int source = 0; source < layers - 1; ++source) {
    int mask = 0;
    for (int q = 0; q < 4; ++q)
      if (Get(target[source + 1], q) == Cell::Crystal) mask |= 1 << q;
    surviving_crystals[source] = mask;
  }

  // O(1) blocker queries: highest target crystal strictly below each row.
  std::array<std::vector<int>, 4> highest_crystal_below;
  for (int q = 0; q < 4; ++q) {
    highest_crystal_below[q].assign(layers + 1, -1);
    int highest = -1;
    for (int row = 0; row <= layers; ++row) {
      highest_crystal_below[q][row] = highest;
      if (row < layers && Get(target[row], q) == Cell::Crystal) highest = row;
    }
  }

  static const std::vector<Row> top_rows = TopRows();

  std::vector<int> bottom_subsets(1 << bottom_pin_columns.size());
  std::iota(bottom_subsets.begin(), bottom_subsets.end(), 0);
  std::sort(bottom_subsets.begin(), bottom_subsets.end(), [](int a, int b) {
    const int pa = __builtin_popcount(static_cast<unsigned>(a));
    const int pb = __builtin_popcount(static_cast<unsigned>(b));
    return pa != pb ? pa > pb : a > b;
  });

  std::vector<int> base_choose_order(16);
  std::iota(base_choose_order.begin(), base_choose_order.end(), 0);
  std::sort(base_choose_order.begin(), base_choose_order.end(), [](int a, int b) {
    const int pa = __builtin_popcount(static_cast<unsigned>(a));
    const int pb = __builtin_popcount(static_cast<unsigned>(b));
    return pa != pb ? pa < pb : a < b;
  });

  std::array<std::vector<int>, 16> destroy_orders;
  std::array<std::vector<int>, 16> unsupported_orders;
  for (int free = 0; free < 16; ++free) {
    for (int subset = free;; subset = (subset - 1) & free) {
      destroy_orders[free].push_back(subset);
      if (subset == 0) break;
    }
    std::sort(destroy_orders[free].begin(), destroy_orders[free].end(),
              [free](int a, int b) {
                if (a == 0 || b == 0) return a == 0;
                if (a == free || b == free) return a == free;
                const int pa = __builtin_popcount(static_cast<unsigned>(a));
                const int pb = __builtin_popcount(static_cast<unsigned>(b));
                return pa != pb ? pa > pb : a > b;
              });
    unsupported_orders[free].push_back(0);
    std::vector<int> rest;
    for (int subset = free; subset; subset = (subset - 1) & free)
      rest.push_back(subset);
    std::sort(rest.begin(), rest.end(), [](int a, int b) {
      const int pa = __builtin_popcount(static_cast<unsigned>(a));
      const int pb = __builtin_popcount(static_cast<unsigned>(b));
      return pa != pb ? pa < pb : a < b;
    });
    unsupported_orders[free].insert(unsupported_orders[free].end(), rest.begin(),
                                    rest.end());
  }

  for (int bottom_subset : bottom_subsets) {
    if (sink && sink->stop) return result;

    int bottom_mask = 0;
    for (int j = 0; j < static_cast<int>(bottom_pin_columns.size()); ++j)
      if (bottom_subset >> j & 1) bottom_mask |= 1 << bottom_pin_columns[j];

    auto sequences = raw_sequences;
    bool valid = true;
    for (int q = 0; q < 4; ++q) {
      if (!(bottom_mask >> q & 1)) continue;
      if (sequences[q].empty() || sequences[q][0].target_layer != 0 ||
          sequences[q][0].kind != Cell::Pin) {
        valid = false;
        break;
      }
      sequences[q].erase(sequences[q].begin());
    }
    if (!valid) continue;

    std::array<std::uint16_t, 4> goal{};
    for (int q = 0; q < 4; ++q) goal[q] = sequences[q].size();

    std::vector<std::unordered_set<Key, KeyHash>> failed(layers);
    std::vector<Decision> path(layers - 1);

    std::function<bool(int, const std::optional<Key>&)> dfs =
        [&](int source, const std::optional<Key>& old_key) -> bool {
      if (sink && sink->stop) return false;

      if (source == layers - 1) {
        if (!old_key) return false;
        const Key& key = *old_key;
        if (key.consumed != goal || !SupportFinish(key.post)) return false;
        if (require_unsupported && !key.seen_unsupported) return false;
        const int previous_nondestroyed_crystals = CrystalMask(key.post.row);

        bool any_terminal = false;
        for (Row top : top_rows) {
          const int destroy = CrystalMask(top);
          if (destroy & previous_nondestroyed_crystals) continue;
          const auto destroy_state = DestroyStep(key.destroy, destroy);
          if (!destroy_state) continue;
          const auto pre = SupportStep(key.pre, top, OccupiedMask(top));
          if (!pre || !SupportFinish(*pre)) continue;
          const auto project = ProjectStep(key.project, top, axis);
          if (!project || !ProjectFinish(*project, layers)) continue;
          std::vector<Row> candidate_rows(layers);
          for (int r = 0; r < layers - 1; ++r) {
            Row row = path[r].fixed;
            for (int q = 0; q < 4; ++q)
              if ((path[r].destroy | path[r].unsupported) >> q & 1)
                row = Set(row, q, Cell::Crystal);
            candidate_rows[r] = row;
          }
          candidate_rows[layers - 1] = top;
          any_terminal = true;
          sink->Emit(candidate_rows, axis, bottom_mask);
          if (sink->stop) return true;
        }
        return any_terminal;
      }

      if (old_key && failed[source].count(*old_key)) return false;

      bool any_solution = false;
      const int result_layer = source + 1;
      const int keep_crystals = surviving_crystals[source];
      std::array<std::uint16_t, 4> consumed{};
      if (old_key) consumed = old_key->consumed;

      bool eligible[4]{};
      int immediately_static = 0;
      for (int q = 0; q < 4; ++q) {
        eligible[q] = !(keep_crystals >> q & 1) &&
                      consumed[q] < sequences[q].size() &&
                      sequences[q][consumed[q]].target_layer <= result_layer;
        if (eligible[q] &&
            sequences[q][consumed[q]].target_layer == result_layer)
          immediately_static |= 1 << q;
      }

      auto choose_order = base_choose_order;
      std::sort(choose_order.begin(), choose_order.end(),
                [immediately_static](int a, int b) {
                  const int da = __builtin_popcount(
                      static_cast<unsigned>(a ^ immediately_static));
                  const int db = __builtin_popcount(
                      static_cast<unsigned>(b ^ immediately_static));
                  if (da != db) return da < db;
                  const int ma = __builtin_popcount(
                      static_cast<unsigned>(a & immediately_static));
                  const int mb = __builtin_popcount(
                      static_cast<unsigned>(b & immediately_static));
                  if (ma != mb) return ma > mb;
                  return __builtin_popcount(static_cast<unsigned>(a)) <
                         __builtin_popcount(static_cast<unsigned>(b));
                });

      for (int choose : choose_order) {
        if (choose & keep_crystals) continue;
        bool bad = false;
        for (int q = 0; q < 4; ++q)
          if ((choose >> q & 1) && !eligible[q]) {
            bad = true;
            break;
          }
        if (bad) continue;

        Row fixed = 0;
        std::array<int, 4> target_layers;
        target_layers.fill(-1);
        auto next_consumed = consumed;
        int desired_support = keep_crystals;
        for (int q = 0; q < 4; ++q) {
          if (keep_crystals >> q & 1) {
            fixed = Set(fixed, q, Cell::Crystal);
          } else if (choose >> q & 1) {
            const Token token = sequences[q][consumed[q]];
            fixed = Set(fixed, q, token.kind);
            target_layers[q] = token.target_layer;
            ++next_consumed[q];
            if (token.target_layer == result_layer) desired_support |= 1 << q;
          }
        }

        const int fixed_occupied = OccupiedMask(fixed);
        int falling_ordinary = 0;
        for (int q = 0; q < 4; ++q)
          if (Get(fixed, q) == Cell::Ordinary && !(desired_support >> q & 1))
            falling_ordinary |= 1 << q;

        bool landing_ok = true;
        for (const auto& component : OrdinaryComponents(falling_ordinary)) {
          int target_layer = -2;
          for (int q : component) {
            if (target_layer == -2) target_layer = target_layers[q];
            else if (target_layer != target_layers[q]) {
              landing_ok = false;
              break;
            }
          }
          if (!landing_ok) break;
          if (target_layer < 0 || target_layer >= result_layer) {
            landing_ok = false;
            break;
          }
          int highest = -1;
          for (int q : component)
            highest = std::max(highest,
                BlockerHeight(highest_crystal_below, sequences, consumed,
                              bottom_mask, q, result_layer));
          if (highest + 1 != target_layer) {
            landing_ok = false;
            break;
          }
        }
        if (!landing_ok) continue;

        for (int q = 0; q < 4; ++q) {
          if (Get(fixed, q) != Cell::Pin || (desired_support >> q & 1)) continue;
          const int target_layer = target_layers[q];
          if (target_layer < 0 || target_layer >= result_layer ||
              BlockerHeight(highest_crystal_below, sequences, consumed,
                            bottom_mask, q, result_layer) + 1 != target_layer) {
            landing_ok = false;
            break;
          }
        }
        if (!landing_ok) continue;

        const int free = (~fixed_occupied) & 15;
        for (int destroy : destroy_orders[free]) {
          const int remaining = free & ~destroy;
          std::vector<int> local_unsupported = unsupported_orders[remaining];
          if (prefer_unsupported) {
            std::stable_sort(local_unsupported.begin(), local_unsupported.end(),
                             [](int a, int b) { return (a == 0) < (b == 0); });
          }
          for (int unsupported : local_unsupported) {
            if (!allow_unsupported && unsupported) continue;
            ++result.transitions;

            if (source == 0 &&
                (fixed_occupied | destroy | unsupported) != bottom_mask)
              continue;

            const int nondestroyed = keep_crystals | unsupported;
            if (destroy & nondestroyed) continue;
            bool adjacent_mixed_crystal = false;
            for (int q = 0; q < 4; ++q) {
              if ((destroy >> q & 1) &&
                  (((nondestroyed >> Left(q)) & 1) ||
                   ((nondestroyed >> Right(q)) & 1))) {
                adjacent_mixed_crystal = true;
                break;
              }
            }
            if (adjacent_mixed_crystal) continue;

            if (source > 0) {
              const int prior_destroy = DestroyMask(old_key->destroy);
              const int prior_nondestroyed = CrystalMask(old_key->post.row);
              if ((prior_destroy & nondestroyed) ||
                  (destroy & prior_nondestroyed))
                continue;
            }

            Row post_row = fixed;
            for (int q = 0; q < 4; ++q)
              if (unsupported >> q & 1)
                post_row = Set(post_row, q, Cell::Crystal);

            std::optional<SupportState> post;
            if (source == 0) {
              Row generated = 0;
              for (int q = 0; q < 4; ++q)
                if (bottom_mask >> q & 1)
                  generated = Set(generated, q, Cell::Pin);
              post = SupportStep(SupportStart(generated, bottom_mask), post_row,
                                 desired_support);
            } else {
              post = SupportStep(old_key->post, post_row, desired_support);
            }
            if (!post) continue;

            Row source_row = post_row;
            for (int q = 0; q < 4; ++q)
              if (destroy >> q & 1)
                source_row = Set(source_row, q, Cell::Crystal);

            const auto pre = source == 0
                ? std::optional<SupportState>(
                      SupportStart(source_row, OccupiedMask(source_row)))
                : SupportStep(old_key->pre, source_row,
                              OccupiedMask(source_row));
            if (!pre) continue;

            const auto destroy_state = source == 0
                ? std::optional<std::uint16_t>(DestroyStart(destroy))
                : DestroyStep(old_key->destroy, destroy);
            if (!destroy_state) continue;

            std::optional<ProjectState> project = source == 0
                ? std::optional<ProjectState>(ProjectStart(source_row, axis))
                : ProjectStep(old_key->project, source_row, axis);
            if (!project) continue;

            Key next{next_consumed, *post, *pre, *destroy_state, *project,
                     static_cast<std::uint8_t>((old_key && old_key->seen_unsupported) ||
                                               unsupported != 0)};
            path[source] = {fixed, static_cast<std::uint8_t>(destroy),
                            static_cast<std::uint8_t>(unsupported)};
            const bool child_solution = dfs(source + 1, next);
            any_solution = any_solution || child_solution;
            if (sink->stop) return any_solution;
          }
        }
      }

      if (!any_solution && old_key) {
        failed[source].insert(*old_key);
        result.max_failed_states =
            std::max<std::uint64_t>(result.max_failed_states,
                                    failed[source].size());
      }
      return any_solution;
    };

    if (dfs(0, std::nullopt)) {
      result.ok = true;
      result.bottom_mask = bottom_mask;
    }
    if (sink->stop) return result;
  }

  return result;
}

Result SolveProject(const std::vector<Row>& target, bool allow_unsupported,
                    bool require_unsupported = false,
                    bool prefer_unsupported = false) {
  // Fixed axis order makes the canonical predecessor reproducible.
  Result axis0 = SolveAxis(target, 0, allow_unsupported, require_unsupported,
                           prefer_unsupported, nullptr);
  if (axis0.ok) return axis0;
  Result axis1 = SolveAxis(target, 1, allow_unsupported, require_unsupported,
                           prefer_unsupported, nullptr);
  axis1.transitions += axis0.transitions;
  axis1.max_failed_states =
      std::max(axis0.max_failed_states, axis1.max_failed_states);
  return axis1;
}


Result EnumerateProject(const std::vector<Row>& target, bool allow_unsupported,
                        bool require_unsupported, bool prefer_unsupported,
                        EnumerationSink* sink) {
  Result total;
  Result axis0 = EnumerateAxis(target, 0, allow_unsupported, require_unsupported,
                               prefer_unsupported, sink);
  total.ok = axis0.ok;
  total.transitions = axis0.transitions;
  total.max_failed_states = axis0.max_failed_states;
  if (!sink->stop) {
    Result axis1 = EnumerateAxis(target, 1, allow_unsupported, require_unsupported,
                                 prefer_unsupported, sink);
    total.ok = total.ok || axis1.ok;
    total.transitions += axis1.transitions;
    total.max_failed_states =
        std::max(total.max_failed_states, axis1.max_failed_states);
  }
  return total;
}

std::vector<std::string> Split(const std::string& text, char delimiter) {
  std::vector<std::string> out;
  std::string current;
  for (char c : text) {
    if (c == delimiter) {
      out.push_back(current);
      current.clear();
    } else {
      current.push_back(c);
    }
  }
  out.push_back(current);
  return out;
}

std::vector<Row> ParseTarget(const std::string& code, int layers) {
  const auto rows = Split(code, ':');
  std::vector<Row> out(layers, 0);
  for (int layer = 0; layer < std::min(layers, static_cast<int>(rows.size())); ++layer) {
    const std::string& text = rows[layer];
    Row row = 0;
    if (text.size() >= 8) {
      for (int q = 0; q < 4; ++q) row = Set(row, q, DecodeCell(text[2 * q]));
    } else {
      for (int q = 0; q < 4 && q < static_cast<int>(text.size()); ++q)
        row = Set(row, q, DecodeCell(text[q]));
    }
    out[layer] = row;
  }
  return out;
}

std::string RowsCode(const std::vector<Row>& rows) {
  std::ostringstream out;
  for (int layer = 0; layer < static_cast<int>(rows.size()); ++layer) {
    if (layer) out << ':';
    out << RowString(rows[layer]);
  }
  return out.str();
}

}  // namespace shapez2_claw

int main(int argc, char** argv) {
  using namespace shapez2_claw;
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);

  bool no_unsupported = false;
  bool require_unsupported = false;
  bool prefer_unsupported = false;
  bool enumerate_all = false;
  bool count_only = false;
  std::uint64_t enumerate_limit = 0;
  int offset = 1;
  while (offset < argc) {
    const std::string flag = argv[offset];
    if (flag == "--no-u") no_unsupported = true;
    else if (flag == "--require-u") require_unsupported = true;
    else if (flag == "--prefer-u") prefer_unsupported = true;
    else if (flag == "--all") enumerate_all = true;
    else if (flag == "--count") { enumerate_all = true; count_only = true; }
    else if (flag == "--limit") {
      if (offset + 1 >= argc) {
        std::cerr << "--limit requires a nonnegative integer\n";
        return 2;
      }
      enumerate_limit = std::strtoull(argv[++offset], nullptr, 10);
    } else break;
    ++offset;
  }
  if (no_unsupported && require_unsupported) {
    std::cerr << "--no-u and --require-u are incompatible\n";
    return 2;
  }

  if (enumerate_all) {
    if (offset + 1 >= argc) {
      std::cerr << "usage: claw_frontier_project --all [--limit N] L TARGET\n";
      return 2;
    }
    const int layers = std::atoi(argv[offset]);
    const auto target = ParseTarget(argv[offset + 1], layers);
    EnumerationSink sink;
    sink.limit = enumerate_limit;
    if (!count_only) {
      sink.callback = [](const std::string& code, int axis, int bottom_mask) {
        std::cout << "CAND\t" << code << "\t" << axis << "\t"
                  << bottom_mask << '\n';
      };
    }
    const auto result = EnumerateProject(target, !no_unsupported,
                                         require_unsupported,
                                         prefer_unsupported, &sink);
    std::cout << "DONE\t" << sink.emitted << "\t" << result.transitions
              << "\t" << result.max_failed_states << '\n';
    return 0;
  }

  if (offset < argc && std::string(argv[offset]) == "--batch") {
    if (offset + 1 >= argc) {
      std::cerr << "usage: claw_frontier_project [--no-u] --batch L\n";
      return 2;
    }
    const int layers = std::atoi(argv[offset + 1]);
    std::string line;
    long long index = 0;
    while (std::getline(std::cin, line)) {
      if (line.empty()) continue;
      const auto target = ParseTarget(line, layers);
      const auto result = SolveProject(target, !no_unsupported, require_unsupported, prefer_unsupported);
      std::cout << index++ << '\t' << (result.ok ? "SAT" : "UNSAT") << '\t'
                << (result.ok ? RowsCode(result.rows) : std::string()) << '\t'
                << result.transitions << '\t' << result.max_failed_states << '\t'
                << result.bottom_mask << '\t' << result.axis << '\n';
    }
    return 0;
  }

  if (offset + 1 >= argc) {
    std::cerr << "usage: claw_frontier_project [--no-u] L TARGET\n";
    return 2;
  }
  const int layers = std::atoi(argv[offset]);
  const auto target = ParseTarget(argv[offset + 1], layers);
  const auto result = SolveProject(target, !no_unsupported, require_unsupported, prefer_unsupported);
  std::cout << (result.ok ? "SAT" : "UNSAT") << '\n';
  if (result.ok) std::cout << RowsCode(result.rows) << '\n';
  std::cout << "transitions " << result.transitions << " max_failed "
            << result.max_failed_states << " bmask " << result.bottom_mask
            << " axis " << result.axis << '\n';
  return 0;
}

'''


# ---------------------------------------------------------------------------
# Embedded backend build and streaming protocol
# ---------------------------------------------------------------------------


def _backend_path() -> Path:
    digest = hashlib.sha256(_CPP_SOURCE.encode("utf-8")).hexdigest()[:20]
    root = Path(os.environ.get(
        "SHAPEZ2_CLAW_CACHE",
        Path(tempfile.gettempdir()) / "shapez2_claw_candidates",
    ))
    root.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    return root / f"claw_candidates_{digest}{suffix}"


def _build_backend(logger: Optional[Callable[[str], None]] = None) -> Path:
    binary = _backend_path()
    if binary.exists():
        return binary

    source = binary.with_suffix(".cpp")
    source.write_text(_CPP_SOURCE, encoding="utf-8")
    command = [
        os.environ.get("CXX", "g++"),
        "-O3",
        "-std=c++20",
        "-pthread",
        str(source),
        "-o",
        str(binary),
    ]
    if logger:
        logger("Compiling embedded C++20 Claw candidate backend...")
    process = subprocess.run(command, text=True, capture_output=True)
    if process.returncode != 0:
        raise ClawEnumeratorInternalError(
            "C++ backend build failed:\n" + process.stdout + process.stderr
        )
    return binary


def _structural_candidates(
    target_code: str,
    layers: int,
    *,
    u_mode: Literal["all", "none", "required"] = "all",
    prefer_u: bool = False,
    logger: Optional[Callable[[str], None]] = None,
) -> Iterator[tuple[str, int, int]]:
    binary = _build_backend(logger)
    command = [str(binary), "--all"]
    if u_mode == "none":
        command.append("--no-u")
    elif u_mode == "required":
        command.append("--require-u")
    elif u_mode != "all":
        raise ValueError("u_mode must be 'all', 'none', or 'required'")
    if prefer_u:
        command.append("--prefer-u")
    command += [str(layers), target_code]

    process = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    assert process.stdout is not None
    completed = False
    try:
        for raw in process.stdout:
            line = raw.rstrip("\n")
            if not line:
                continue
            fields = line.split("\t")
            if fields[0] == "CAND" and len(fields) == 4:
                yield fields[1], int(fields[2]), int(fields[3])
            elif fields[0] == "DONE" and len(fields) == 4:
                completed = True
            else:
                raise ClawEnumeratorInternalError(
                    f"unrecognized backend output line: {line!r}"
                )
        return_code = process.wait()
        if return_code != 0:
            stderr = process.stderr.read() if process.stderr else ""
            raise ClawEnumeratorInternalError(
                f"backend exited with {return_code}: {stderr.strip()}"
            )
        if not completed:
            raise ClawEnumeratorInternalError("backend ended without DONE record")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()


# ---------------------------------------------------------------------------
# Independent project-simulator certification and exact color provenance
# ---------------------------------------------------------------------------


def _kind(piece) -> str:
    if piece is None:
        return "-"
    if piece.shape == "P":
        return "P"
    if piece.shape == "c":
        return "c"
    return "S"


def _simplify_shape(shape: Shape) -> str:
    rows = ["".join(_kind(p) for p in layer.quadrants) for layer in shape.layers]
    while rows and rows[-1] == "----":
        rows.pop()
    return ":".join(rows)


def _same_structure(a: Shape, b: Shape) -> bool:
    return _simplify_shape(a) == _simplify_shape(b)


@dataclass
class _PCell:
    kind: str
    origin: Optional[tuple[int, int]]


def _adjacent(q: int) -> tuple[int, int]:
    return (q - 1) % 4, (q + 1) % 4


def _get(grid, layer: int, quadrant: int):
    return grid[layer][quadrant] if 0 <= layer < len(grid) else None


def _group(grid, layer0: int, quadrant0: int) -> set[tuple[int, int]]:
    start = _get(grid, layer0, quadrant0)
    if start is None:
        return set()
    if start.kind == "P":
        return {(layer0, quadrant0)}

    crystal = start.kind == "c"
    pending = [(layer0, quadrant0)]
    seen: set[tuple[int, int]] = set()
    while pending:
        layer, quadrant = pending.pop(0)
        if (layer, quadrant) in seen:
            continue
        seen.add((layer, quadrant))
        for neighbor in _adjacent(quadrant):
            cell = _get(grid, layer, neighbor)
            if cell is not None and (
                (crystal and cell.kind == "c")
                or (not crystal and cell.kind not in ("c", "P"))
            ):
                pending.append((layer, neighbor))
        if crystal:
            for delta in (-1, 1):
                cell = _get(grid, layer + delta, quadrant)
                if cell is not None and cell.kind == "c":
                    pending.append((layer + delta, quadrant))
    return seen


def _shatter_set(grid, initial: set[tuple[int, int]]) -> set[tuple[int, int]]:
    total = set(initial)
    pending = {
        position
        for position in initial
        if _get(grid, *position) is not None and _get(grid, *position).kind == "c"
    }
    while pending:
        layer, quadrant = pending.pop()
        component = _group(grid, layer, quadrant)
        new = component - total
        if not new:
            continue
        total.update(new)
        for source_layer, source_quadrant in new:
            neighbors = (
                (source_layer - 1, source_quadrant),
                (source_layer + 1, source_quadrant),
                (source_layer, (source_quadrant - 1) % 4),
                (source_layer, (source_quadrant + 1) % 4),
            )
            for position in neighbors:
                cell = _get(grid, *position)
                if cell is not None and cell.kind == "c" and position not in total:
                    pending.add(position)
    return total


def _gravity(grid):
    while True:
        supported = {
            (0, q) for q in range(4) if _get(grid, 0, q) is not None
        }
        while True:
            before = len(supported)
            visited: set[tuple[int, int]] = set()
            for layer in range(len(grid)):
                for quadrant in range(4):
                    position = (layer, quadrant)
                    if position not in visited and _get(grid, layer, quadrant) is not None:
                        component = _group(grid, layer, quadrant)
                        if component & supported:
                            supported.update(component)
                        visited.update(component)
            for layer in range(len(grid)):
                for quadrant in range(4):
                    position = (layer, quadrant)
                    if position in supported or _get(grid, layer, quadrant) is None:
                        continue
                    piece = _get(grid, layer, quadrant)
                    if layer > 0 and (layer - 1, quadrant) in supported:
                        supported.add(position)
                    elif piece.kind != "P":
                        for neighbor in _adjacent(quadrant):
                            if (layer, neighbor) in supported:
                                neighbor_piece = _get(grid, layer, neighbor)
                                if neighbor_piece is not None and neighbor_piece.kind != "P":
                                    supported.add(position)
                                    break
            if len(supported) == before:
                break

        all_cells = {
            (layer, quadrant)
            for layer in range(len(grid))
            for quadrant in range(4)
            if _get(grid, layer, quadrant) is not None
        }
        unsupported = all_cells - supported
        crystals = {
            position for position in unsupported if _get(grid, *position).kind == "c"
        }
        if crystals:
            for layer, quadrant in _shatter_set(grid, crystals):
                if 0 <= layer < len(grid):
                    grid[layer][quadrant] = None
            continue
        if not unsupported:
            break

        groups = []
        visited: set[tuple[int, int]] = set()
        for layer, quadrant in sorted(unsupported, key=lambda item: item[0]):
            if (layer, quadrant) not in visited:
                falling = _group(grid, layer, quadrant) & unsupported
                if falling:
                    groups.append(falling)
                    visited.update(falling)

        moved = False
        for falling in groups:
            distance = 0
            while True:
                next_distance = distance + 1
                valid = True
                for layer, quadrant in falling:
                    target_layer = layer - next_distance
                    if target_layer < 0:
                        valid = False
                        break
                    below = _get(grid, target_layer, quadrant)
                    if below is not None and (target_layer, quadrant) not in falling:
                        valid = False
                        break
                if valid:
                    distance = next_distance
                else:
                    break
            if distance:
                moved = True
                pieces = sorted(
                    [(layer, q, _get(grid, layer, q)) for layer, q in falling],
                    key=lambda item: -item[0],
                )
                for layer, quadrant, _ in pieces:
                    grid[layer][quadrant] = None
                for layer, quadrant, piece in pieces:
                    grid[layer - distance][quadrant] = piece
        if not moved:
            break

    while grid and all(cell is None for cell in grid[-1]):
        grid.pop()
    return grid


def _push_with_provenance(shape: Shape):
    cap = shape.max_layers
    original = []
    for layer, row in enumerate(shape.layers):
        original.append([
            None if piece is None else _PCell(_kind(piece), (layer, q))
            for q, piece in enumerate(row.quadrants)
        ])
    if not original or all(piece is None for piece in original[0]):
        return original

    oversized = [
        [_PCell("P", None) if piece is not None else None for piece in original[0]]
    ] + [[piece for piece in row] for row in original]
    initial = (
        {
            (layer, q)
            for layer in range(cap, len(oversized))
            for q in range(4)
            if _get(oversized, layer, q) is not None
        }
        if len(oversized) > cap
        else set()
    )
    for layer, quadrant in _shatter_set(oversized, initial):
        if 0 <= layer < len(oversized):
            oversized[layer][quadrant] = None
    return _gravity([list(row) for row in oversized[:cap]])


def _repair_colors(candidate: Shape, target: Shape) -> Optional[Shape]:
    provenance = _push_with_provenance(candidate)
    output = candidate.copy()
    for layer in range(max(len(provenance), len(target.layers))):
        for quadrant in range(4):
            target_piece = target._get_piece(layer, quadrant)
            source_info = _get(provenance, layer, quadrant)
            if (target_piece is None) != (source_info is None):
                return None
            if target_piece is None:
                continue
            if source_info.kind != _kind(target_piece):
                return None
            if source_info.origin is None:
                if source_info.kind != "P":
                    return None
                continue
            origin_layer, origin_quadrant = source_info.origin
            source_piece = output._get_piece(origin_layer, origin_quadrant)
            if source_piece is None:
                return None
            if source_info.kind == "P":
                if source_piece.shape != "P":
                    return None
            elif source_info.kind == "c":
                if source_piece.shape != "c":
                    return None
                source_piece.color = target_piece.color
            else:
                if source_piece.shape in ("c", "P"):
                    return None
                source_piece.shape = target_piece.shape
                source_piece.color = target_piece.color
    return output


def _half_axis_stable(shape: Shape, horizontal: bool) -> bool:
    first, second = shape.simple_cutter(horizontal=horizontal)
    first.max_layers = second.max_layers = shape.max_layers
    return first.is_stable() and second.is_stable()


def _is_half_stable_any_axis(shape: Shape) -> bool:
    return _half_axis_stable(shape, False) or _half_axis_stable(shape, True)


_FORBIDDEN_PILLAR_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"-P",
        r"^P*-+c",
        r"[^P]P.*c",
        r"c-.*c",
        r"c.-+c",
        r"^S*-?S*c(.*c)?(S-+)+c",
    )
)


def _effective_rows(shape: Shape) -> list[str]:
    rows = ["".join(_kind(piece) for piece in layer.quadrants) for layer in shape.layers]
    while rows and rows[-1] == "----":
        rows.pop()
    return rows


def _project_swapable_predecessor_reason(shape: Shape) -> Optional[str]:
    if not shape.is_stable():
        return "unstable"
    rows = _effective_rows(shape)
    if not rows:
        return "empty"
    if not any("c" in row for row in rows):
        return "no_crystal"

    pillars = ["".join(row[q] for row in rows).rstrip("-") for q in range(4)]
    for q, pillar in enumerate(pillars):
        for pattern in _FORBIDDEN_PILLAR_PATTERNS:
            if pattern.search(pillar):
                return f"corner_rule_q{q + 1}:{pattern.pattern}"

    nonempty_columns = [q for q, pillar in enumerate(pillars) if pillar]
    if nonempty_columns == [0] and len(rows) != 1:
        return "q1_only_corner_branch"
    if not _is_half_stable_any_axis(shape):
        return "both_cut_axes_blocked"
    return None


def _certify_project_swapable(candidate: Shape, target: Shape) -> Optional[Shape]:
    candidate.max_layers = target.max_layers
    if not candidate.is_stable():
        return None

    pushed = candidate.push_pin()
    accepted = None
    if repr(pushed) == repr(target):
        accepted = candidate
    elif _same_structure(pushed, target):
        repaired = _repair_colors(candidate, target)
        if repaired is not None:
            repaired.max_layers = target.max_layers
            if repaired.is_stable() and repr(repaired.push_pin()) == repr(target):
                accepted = repaired
    if accepted is None:
        return None
    return accepted if _project_swapable_predecessor_reason(accepted) is None else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def claw_candidates(
    shape_code: str,
    *,
    max_layers: Optional[int] = None,
    limit: Optional[int] = None,
    u_mode: Literal["all", "none", "required"] = "all",
    prefer_u: bool = False,
    logger: Optional[Callable[[str], None]] = None,
) -> Iterator[CandidateResult]:
    """Yield one exact representative for every distinct structural candidate.

    ``limit=None`` means unlimited. The backend deduplicates structural shapes;
    this wrapper repairs the colors/types of surviving pieces from the target
    and additionally deduplicates repaired codes. It intentionally does *not*
    expand physically irrelevant color/type variants of sacrificial ordinary
    pieces that disappear during Pin Push.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative or None")
    if limit == 0:
        return

    layers = int(Shape.MAX_LAYERS if max_layers is None else max_layers)
    if layers < 2:
        raise ValueError("Claw requires at least two layers")

    old_max = Shape.MAX_LAYERS
    Shape.MAX_LAYERS = layers
    try:
        target = Shape.from_string(shape_code)
        target.max_layers = layers
        exact_seen: set[str] = set()
        emitted = 0
        for structural, axis, bottom_mask in _structural_candidates(
            repr(target),
            layers,
            u_mode=u_mode,
            prefer_u=prefer_u,
            logger=logger,
        ):
            candidate = Shape.from_string(structural)
            candidate.max_layers = layers
            accepted = _certify_project_swapable(candidate, target)
            if accepted is None:
                raise ClawEnumeratorInternalError(
                    "frontier candidate failed independent project-simulator "
                    f"certification: {structural}"
                )
            exact = repr(accepted)
            if exact in exact_seen:
                continue
            exact_seen.add(exact)
            emitted += 1
            yield CandidateResult(
                predecessor=exact,
                structural=structural,
                axis=axis,
                bottom_mask=bottom_mask,
                index=emitted,
            )
            if limit is not None and emitted >= limit:
                return
    finally:
        Shape.MAX_LAYERS = old_max


def claw_process(
    shape_code: str,
    logger: Optional[Callable[[str], None]] = None,
    *,
    max_layers: Optional[int] = None,
) -> str:
    """Backward-compatible deterministic first-candidate API."""
    candidate = next(
        claw_candidates(
            shape_code,
            max_layers=max_layers,
            limit=1,
            logger=logger,
        ),
        None,
    )
    if candidate is None:
        raise NoClawPredecessor("no accepted immediate Pin-Pusher predecessor exists")
    return candidate.predecessor


def claw_candidate_count(
    shape_code: str,
    *,
    max_layers: Optional[int] = None,
    u_mode: Literal["all", "none", "required"] = "all",
    prefer_u: bool = False,
    stop_after: Optional[int] = None,
) -> int:
    """Count structural candidate representatives; potentially output-sized."""
    return sum(
        1
        for _ in claw_candidates(
            shape_code,
            max_layers=max_layers,
            limit=stop_after,
            u_mode=u_mode,
            prefer_u=prefer_u,
        )
    )


def _default_score(shape: Shape) -> tuple[int, int, int, str]:
    occupied = 0
    crystals = 0
    effective_height = 0
    for layer_index, layer in enumerate(shape.layers):
        row_occupied = False
        for piece in layer.quadrants:
            if piece is not None:
                occupied += 1
                row_occupied = True
                if piece.shape == "c":
                    crystals += 1
        if row_occupied:
            effective_height = layer_index + 1
    return occupied, crystals, effective_height, repr(shape)


def claw_process_minimal(
    shape_code: str,
    *,
    max_layers: Optional[int] = None,
    score: Optional[Callable[[Shape], object]] = None,
    limit: Optional[int] = None,
) -> str:
    """Return the minimum among enumerated candidates.

    The default order minimizes total occupied cells, then crystals, then
    effective height, then lexicographic shape code.  ``limit`` can deliberately
    restrict optimization to the first N candidates.
    """
    layers = int(Shape.MAX_LAYERS if max_layers is None else max_layers)
    score_function = score or _default_score
    best_code: Optional[str] = None
    best_score = None
    old_max = Shape.MAX_LAYERS
    Shape.MAX_LAYERS = layers
    try:
        for item in claw_candidates(
            shape_code,
            max_layers=layers,
            limit=limit,
        ):
            candidate = Shape.from_string(item.predecessor)
            candidate.max_layers = layers
            current_score = score_function(candidate)
            if best_score is None or current_score < best_score:
                best_score = current_score
                best_code = item.predecessor
    finally:
        Shape.MAX_LAYERS = old_max
    if best_code is None:
        raise NoClawPredecessor("no accepted immediate Pin-Pusher predecessor exists")
    return best_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Enumerate all immediate Shapez 2 Claw Pin-Pusher predecessors"
    )
    parser.add_argument("mode", choices=("first", "all", "count", "minimal"))
    parser.add_argument("shape")
    parser.add_argument("--layers", type=int, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--u-mode", choices=("all", "none", "required"), default="all")
    parser.add_argument("--prefer-u", action="store_true")
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()

    if args.mode == "first":
        print(claw_process(args.shape, max_layers=args.layers))
        return 0
    if args.mode == "count":
        print(claw_candidate_count(
            args.shape,
            max_layers=args.layers,
            u_mode=args.u_mode,
            prefer_u=args.prefer_u,
            stop_after=args.limit,
        ))
        return 0
    if args.mode == "minimal":
        print(claw_process_minimal(
            args.shape,
            max_layers=args.layers,
            limit=args.limit,
        ))
        return 0

    for item in claw_candidates(
        args.shape,
        max_layers=args.layers,
        limit=args.limit,
        u_mode=args.u_mode,
        prefer_u=args.prefer_u,
    ):
        if args.jsonl:
            print(json.dumps(item.__dict__, ensure_ascii=False))
        else:
            print(item.predecessor)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
