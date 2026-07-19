// Proven O(L^3) state compression for the cut-stable Claw inverse frontier.
//
// Preconditions established by CLAW_L3_THREE_FALL_PROOF_KO.md:
//   * the queried target is a true structural Claw (not Swapper/Stacker), and
//   * the frontier searches stable predecessors separable by one Cutter axis.
// Then every valid predecessor has at most two active/falling columns, hence
// at least one fixed eager pair among the six 2-bit masks.

Result SolveClawL3(const Target& target) {
    if (auto plain = SolvePlainInverse(target)) {
        return *plain; // O(L)
    }

    static constexpr std::uint8_t kPairs[6] = {
        0b0011, 0b0101, 0b1001, 0b0110, 0b1010, 0b1100,
    };

    for (std::uint8_t eager_pair : kPairs) {
        if (auto answer = SolveFixedTwoEager(target, eager_pair)) {
            return *answer;
        }
    }
    return Result::Unsat();
}

// In SolveFixedTwoEager, immediately after next_consumed is computed:
bool PairRemainsEager(
    std::uint8_t eager_pair,
    int source,
    const std::array<std::uint16_t, 4>& next_consumed,
    const std::array<std::vector<std::uint16_t>, 4>& eligible_prefix) {
  for (int q = 0; q < 4; ++q) {
    if (!(eager_pair & (1u << q))) continue;
    if (next_consumed[q] != eligible_prefix[q][source + 1]) return false;
  }
  return true;
}

struct L3Key {
  std::uint16_t source;
  std::uint8_t eager_pair;
  std::uint16_t free_cursor_0;
  std::uint16_t free_cursor_1;
  PackedFrontier frontier; // width-four finite state
};

L3Key MakeL3Key(
    int source,
    std::uint8_t eager_pair,
    const std::array<std::uint16_t, 4>& consumed,
    PackedFrontier frontier) {
  std::array<std::uint16_t, 2> free{};
  int j = 0;
  for (int q = 0; q < 4; ++q)
    if (!(eager_pair & (1u << q))) free[j++] = consumed[q];
  return {
      static_cast<std::uint16_t>(source), eager_pair,
      free[0], free[1], frontier,
  };
}
