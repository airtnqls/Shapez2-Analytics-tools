// O(L^4) eager-column pruning sketch.
// Build this after the bottom receipt tokens have been erased from sequences.
std::array<std::vector<std::uint16_t>, 4> eligible_prefix;
for (int q = 0; q < 4; ++q) {
  eligible_prefix[q].assign(layers + 1, 0);
  std::uint16_t count = 0;
  std::size_t token = 0;
  for (int r = 0; r <= layers; ++r) {
    while (token < sequences[q].size() &&
           sequences[q][token].target_layer <= r) {
      ++count;
      ++token;
    }
    eligible_prefix[q][r] = count;
  }
}

// Insert immediately after next_consumed has been computed for source row s.
bool has_eager_column = false;
for (int q = 0; q < 4; ++q) {
  if (next_consumed[q] == eligible_prefix[q][source + 1]) {
    has_eager_column = true;
    break;
  }
}
if (!has_eager_column) continue;

// Once the lemma is proved, an explicitly compressed key can omit one cursor:
struct CompressedCursor {
  std::uint8_t eager_q;                 // 0..3
  std::array<std::uint16_t, 3> other;  // remaining cursors
};
// Reconstruct omitted cursor as eligible_prefix[eager_q][source + 1].
