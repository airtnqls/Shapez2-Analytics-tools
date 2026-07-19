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

namespace shapez2_rawpp {

#include "half_dfa.inc"

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
// Exact all-layer Swappable family: union of the two cutter-axis products of
// the 210-state Half DFA.  Each half tracks both the raw prefix state and the
// state committed at its last non-empty row, so trailing empty rows in one
// half are ignored independently of the opposite half.
// ---------------------------------------------------------------------------
struct HalfTrack {
  std::uint16_t current = HALF_START;
  std::uint16_t committed = HALF_START;
  bool operator==(const HalfTrack&) const = default;
};
struct SwappableState {
  // axis0: 01 | 23, axis1: 30 | 12
  std::array<HalfTrack, 4> half{};
  bool operator==(const SwappableState&) const = default;
};
int HalfSymbol(Row row, int a, int b) {
  return static_cast<int>(Get(row, a)) * 4 + static_cast<int>(Get(row, b));
}
HalfTrack HalfAdvance(HalfTrack old, int symbol) {
  old.current = HALF_TRANS[old.current][symbol];
  if (symbol != 0) old.committed = old.current;
  return old;
}
SwappableState SwappableStart(Row row) {
  SwappableState s;
  const int symbols[4] = {HalfSymbol(row,0,1), HalfSymbol(row,2,3),
                          HalfSymbol(row,3,0), HalfSymbol(row,1,2)};
  for (int i=0;i<4;++i) s.half[i] = HalfAdvance(s.half[i], symbols[i]);
  return s;
}
SwappableState SwappableStep(SwappableState s, Row row) {
  const int symbols[4] = {HalfSymbol(row,0,1), HalfSymbol(row,2,3),
                          HalfSymbol(row,3,0), HalfSymbol(row,1,2)};
  for (int i=0;i<4;++i) s.half[i] = HalfAdvance(s.half[i], symbols[i]);
  return s;
}
bool SwappableFinish(const SwappableState& s) {
  return (HALF_ACC[s.half[0].committed] && HALF_ACC[s.half[1].committed]) ||
         (HALF_ACC[s.half[2].committed] && HALF_ACC[s.half[3].committed]);
}
void HashCombine(std::size_t& h, std::uint64_t x);
std::vector<std::vector<int>> OrdinaryComponents(int mask);

bool IsSwappableRows(const std::vector<Row>& rows) {
  if (rows.empty()) return false;
  auto s = SwappableStart(rows[0]);
  for (std::size_t i=1;i<rows.size();++i) s = SwappableStep(s, rows[i]);
  return SwappableFinish(s);
}


// ---------------------------------------------------------------------------
// Exact target-guided StackClosure(Swappable) NFA state.
// ---------------------------------------------------------------------------
// ``switched`` is the set of columns that have begun receiving visible
// single-layer top pieces.  Once a column switches, every higher occupied cell
// in that column belongs to the top stream; crystals can never belong to that
// stream.  The remaining A projection is checked simultaneously for exact
// physical stability and membership in the all-layer Swappable family.
struct Rank0StackState {
  std::uint8_t switched = 0;
  bool has_a = false;
  SupportState support{};
  SwappableState base{};
  bool initialized = false;
  bool operator==(const Rank0StackState&) const = default;
};

void HashRank0Stack(std::size_t& h, const Rank0StackState& s) {
  HashCombine(h, s.switched);
  HashCombine(h, s.has_a);
  HashCombine(h, s.initialized);
  SupportHash sh;
  HashCombine(h, sh(s.support));
  for (const auto& t : s.base.half) {
    HashCombine(h, t.current);
    HashCombine(h, t.committed);
  }
}

bool StackLandingValid(Row row, int b_mask, int below_occupied, bool floor) {
  if (b_mask == 0 || floor) return true;
  int pin_mask = 0, ordinary_mask = 0;
  for (int q = 0; q < 4; ++q) {
    if (!(b_mask >> q & 1)) continue;
    if (Get(row, q) == Cell::Pin) pin_mask |= 1 << q;
    if (Get(row, q) == Cell::Ordinary) ordinary_mask |= 1 << q;
  }
  if (pin_mask & ~below_occupied) return false;
  for (const auto& component : OrdinaryComponents(ordinary_mask)) {
    int mask = 0;
    for (int q : component) mask |= 1 << q;
    if (!(mask & below_occupied)) return false;
  }
  return true;
}

std::vector<Rank0StackState> Rank0StackNext(
    const std::optional<Rank0StackState>& old, Row row, Row previous_row,
    bool floor) {
  const int occupied = OccupiedMask(row);
  const int crystals = CrystalMask(row);
  const int switched = old ? old->switched : 0;
  if (switched & crystals) return {};
  const int startable = occupied & ~crystals & ~switched & 15;
  std::vector<Rank0StackState> out;
  for (int subset = startable;; subset = (subset - 1) & startable) {
    const int next_mask = switched | subset;
    const int b_mask = occupied & next_mask;
    if (StackLandingValid(row, b_mask, OccupiedMask(previous_row), floor)) {
      const Row a_row = MaskRow(row, ~next_mask & 15);
      std::optional<SupportState> support;
      SwappableState base;
      if (!old) {
        support = SupportStart(a_row, OccupiedMask(a_row));
        base = SwappableStart(a_row);
      } else {
        support = SupportStep(old->support, a_row, OccupiedMask(a_row));
        base = SwappableStep(old->base, a_row);
      }
      if (support) {
        Rank0StackState next;
        next.switched = static_cast<std::uint8_t>(next_mask);
        next.has_a = (old && old->has_a) || OccupiedMask(a_row) != 0;
        next.support = *support;
        next.base = base;
        next.initialized = true;
        out.push_back(next);
      }
    }
    if (subset == 0) break;
  }
  return out;
}

bool Rank0StackFinish(const Rank0StackState& s) {
  return s.initialized && s.switched != 0 && s.has_a &&
         SupportFinish(s.support) && SwappableFinish(s.base);
}

bool IsRank0Rows(const std::vector<Row>& rows) {
  if (rows.empty()) return false;
  if (IsSwappableRows(rows)) return true;
  std::vector<Rank0StackState> states;
  states = Rank0StackNext(std::nullopt, rows[0], 0, true);
  for (std::size_t i = 1; i < rows.size() && !states.empty(); ++i) {
    std::vector<Rank0StackState> next;
    for (const auto& state : states) {
      auto local = Rank0StackNext(state, rows[i], rows[i - 1], false);
      next.insert(next.end(), local.begin(), local.end());
    }
    std::sort(next.begin(), next.end(), [](const auto& a, const auto& b) {
      if (a.switched != b.switched) return a.switched < b.switched;
      if (a.has_a != b.has_a) return a.has_a < b.has_a;
      if (a.support.row != b.support.row) return a.support.row < b.support.row;
      if (a.support.desired != b.support.desired) return a.support.desired < b.support.desired;
      if (a.support.closure != b.support.closure) return a.support.closure < b.support.closure;
      if (a.support.positive != b.support.positive) return a.support.positive < b.support.positive;
      if (a.support.negative != b.support.negative) return a.support.negative < b.support.negative;
      for (int i=0;i<4;++i) {
        if (a.base.half[i].current != b.base.half[i].current)
          return a.base.half[i].current < b.base.half[i].current;
        if (a.base.half[i].committed != b.base.half[i].committed)
          return a.base.half[i].committed < b.base.half[i].committed;
      }
      return false;
    });
    next.erase(std::unique(next.begin(), next.end()), next.end());
    states.swap(next);
  }
  return std::any_of(states.begin(), states.end(), Rank0StackFinish);
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
  std::uint8_t seen_unsupported = 0;
  SwappableState family{};
  Rank0StackState rank0_stack{};
  bool operator==(const Key& o) const {
    return consumed == o.consumed && post == o.post && pre == o.pre &&
           destroy == o.destroy && seen_unsupported == o.seen_unsupported &&
           family == o.family && rank0_stack == o.rank0_stack;
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
    HashCombine(h, key.seen_unsupported);
    for (const auto& t : key.family.half) { HashCombine(h, t.current); HashCombine(h, t.committed); }
    HashRank0Stack(h, key.rank0_stack);
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
  // An overflow predecessor has height == cap, so its old top row is merely
  // non-empty.  It need not contain a crystal: ordinary parts and pins are
  // trimmed directly, while only trimmed crystals seed D-component shatter.
  std::vector<Row> rows;
  for (int row = 1; row < 256; ++row) rows.push_back(static_cast<Row>(row));
  std::sort(rows.begin(), rows.end(), [](int a, int b) {
    auto score = [](int row) {
      int occupied = 0;
      int crystals = 0;
      for (int q = 0; q < 4; ++q) {
        const Cell c = Get(static_cast<Row>(row), q);
        occupied += c != Cell::Empty;
        crystals += c == Cell::Crystal;
      }
      return std::tuple<int, int, int>(crystals, occupied, row);
    };
    return score(a) < score(b);
  });
  return rows;
}

Result SolveOverflow(const std::vector<Row>& target, bool allow_unsupported,
                     bool require_unsupported, bool prefer_unsupported,
                     bool require_swappable,
                     bool require_rank0_stack,
                     std::atomic<bool>* cancel) {
  const int layers = static_cast<int>(target.size());
  Result result;
  result.axis = -1;
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
          const auto final_family = SwappableStep(key.family, top);
          if (require_swappable && !SwappableFinish(final_family)) continue;
          if (require_rank0_stack) {
            bool accepted = false;
            for (const auto& st : Rank0StackNext(key.rank0_stack, top, key.pre.row, false)) {
              if (Rank0StackFinish(st)) { accepted = true; break; }
            }
            if (!accepted) continue;
          }
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

            const auto family = source == 0
                ? SwappableStart(source_row)
                : SwappableStep(old_key->family, source_row);
            std::vector<Rank0StackState> stack_states;
            if (require_rank0_stack) {
              stack_states = Rank0StackNext(
                  source == 0 ? std::optional<Rank0StackState>()
                              : std::optional<Rank0StackState>(old_key->rank0_stack),
                  source_row, source == 0 ? Row(0) : old_key->pre.row,
                  source == 0);
              if (stack_states.empty()) continue;
            } else {
              stack_states.push_back(Rank0StackState{});
            }
            path[source] = {fixed, static_cast<std::uint8_t>(destroy),
                            static_cast<std::uint8_t>(unsupported)};
            for (const auto& stack_state : stack_states) {
              Key next{next_consumed, *post, *pre, *destroy_state,
                       static_cast<std::uint8_t>((old_key && old_key->seen_unsupported) ||
                                                 unsupported != 0), family,
                       stack_state};
              if (dfs(source + 1, next)) return true;
            }
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

std::optional<std::vector<Row>> SolvePlainInverse(const std::vector<Row>& target) {
  const int cap = static_cast<int>(target.size());
  if (cap < 1) return std::nullopt;
  // No-overflow Pin Push is a pure lift.  Target row 0 must be exactly the
  // receipt pins determined by predecessor row 0 == target row 1.
  Row predecessor_bottom = cap >= 2 ? target[1] : 0;
  Row expected_receipt = 0;
  for (int q = 0; q < 4; ++q) {
    if (Occupied(Get(predecessor_bottom, q))) expected_receipt = Set(expected_receipt, q, Cell::Pin);
  }
  if (target[0] != expected_receipt) return std::nullopt;
  std::vector<Row> predecessor(cap, 0);
  for (int layer = 0; layer + 1 < cap; ++layer) predecessor[layer] = target[layer + 1];
  // A no-overflow source must have height < cap; the shifted candidate does.
  // Validate stability with the exact support automaton.
  int height = cap - 1;
  while (height > 0 && predecessor[height - 1] == 0) --height;
  if (height == 0) return predecessor; // empty
  SupportState state = SupportStart(predecessor[0], OccupiedMask(predecessor[0]));
  for (int layer = 1; layer < height; ++layer) {
    auto next = SupportStep(state, predecessor[layer], OccupiedMask(predecessor[layer]));
    if (!next) return std::nullopt;
    state = *next;
  }
  if (!SupportFinish(state)) return std::nullopt;
  return predecessor;
}

std::optional<std::vector<Row>> SolveCapOne(const std::vector<Row>& target) {
  if (target.size() != 1) return std::nullopt;
  Row witness = 0;
  for (int q = 0; q < 4; ++q) {
    const Cell c = Get(target[0], q);
    if (c == Cell::Empty) continue;
    if (c != Cell::Pin) return std::nullopt;
    witness = Set(witness, q, Cell::Ordinary);
  }
  return std::vector<Row>{witness};
}

Result SolvePinPush(const std::vector<Row>& target, bool allow_unsupported = true,
                    bool require_unsupported = false, bool prefer_unsupported = false,
                    bool require_swappable = false,
                    bool require_rank0 = false) {
  Result result;
  if (auto plain = SolvePlainInverse(target)) {
    if (require_swappable && !IsSwappableRows(*plain)) plain.reset();
    if (require_rank0 && !IsRank0Rows(*plain)) plain.reset();
    if (plain) {
    result.ok = true;
    result.rows = *plain;
    result.axis = -2; // plain
    return result;
    }
  }
  if (target.size() == 1) {
    if (auto cap1 = SolveCapOne(target)) {
      if (require_swappable && !IsSwappableRows(*cap1)) cap1.reset();
      if (require_rank0 && !IsRank0Rows(*cap1)) cap1.reset();
      if (cap1) {
      result.ok = true;
      result.rows = *cap1;
      result.axis = -3; // cap-one overflow
      }
    }
    return result;
  }
  if (require_rank0) {
    // Direct Swappable is part of rank 0; try it before the strict Stack branch.
    auto direct = SolveOverflow(target, allow_unsupported, require_unsupported,
                                prefer_unsupported, true, false, nullptr);
    if (direct.ok) return direct;
  }
  return SolveOverflow(target, allow_unsupported, require_unsupported,
                       prefer_unsupported, require_swappable,
                       require_rank0, nullptr);
}

Result SolveRawOverflow(const std::vector<Row>& target) {
  return SolveOverflow(target, true, false, false, false, false, nullptr);
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

}  // namespace shapez2_rawpp

int main(int argc, char** argv) {
  using namespace shapez2_rawpp;
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);

  bool no_unsupported = false;
  bool require_unsupported = false;
  bool prefer_unsupported = false;
  bool require_swappable = false;
  bool require_rank0 = false;
  int offset = 1;
  while (offset < argc) {
    const std::string flag = argv[offset];
    if (flag == "--no-u") no_unsupported = true;
    else if (flag == "--require-u") require_unsupported = true;
    else if (flag == "--prefer-u") prefer_unsupported = true;
    else if (flag == "--swappable") require_swappable = true;
    else if (flag == "--rank0") require_rank0 = true;
    else break;
    ++offset;
  }
  if (no_unsupported && require_unsupported) {
    std::cerr << "--no-u and --require-u are incompatible\n";
    return 2;
  }

  if (offset < argc && std::string(argv[offset]) == "--batch") {
    if (offset + 1 >= argc) {
      std::cerr << "usage: raw_pinpush_frontier [--no-u] --batch L\n";
      return 2;
    }
    const int layers = std::atoi(argv[offset + 1]);
    std::string line;
    long long index = 0;
    while (std::getline(std::cin, line)) {
      if (line.empty()) continue;
      const auto target = ParseTarget(line, layers);
      const auto result = SolvePinPush(target, !no_unsupported, require_unsupported, prefer_unsupported, require_swappable, require_rank0);
      std::cout << index++ << '\t' << (result.ok ? "SAT" : "UNSAT") << '\t'
                << (result.ok ? RowsCode(result.rows) : std::string()) << '\t'
                << result.transitions << '\t' << result.max_failed_states << '\t'
                << result.bottom_mask << '\t' << result.axis << '\n';
    }
    return 0;
  }

  if (offset + 1 >= argc) {
    std::cerr << "usage: raw_pinpush_frontier [--no-u] L TARGET\n";
    return 2;
  }
  const int layers = std::atoi(argv[offset]);
  const auto target = ParseTarget(argv[offset + 1], layers);
  const auto result = SolvePinPush(target, !no_unsupported, require_unsupported, prefer_unsupported, require_swappable, require_rank0);
  std::cout << (result.ok ? "SAT" : "UNSAT") << '\n';
  if (result.ok) std::cout << RowsCode(result.rows) << '\n';
  std::cout << "transitions " << result.transitions << " max_failed "
            << result.max_failed_states << " bmask " << result.bottom_mask
            << " axis " << result.axis << '\n';
  return 0;
}
