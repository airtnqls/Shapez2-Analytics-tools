# Changelog

## 0.3.0 — Stack automaton state-control revision

- preserve legacy StackClosure implementation as `LegacyStackClosureAutomaton`
- add exact 131-state support residual quotient
- add compact row/product/subset/state interning
- add exact switched/support/family residual-inclusion antichain
- add lazy sparse transition generation and state-local row action grouping
- add separate exists-only and witness paths
- add complete reachable DFA compiler and exact minimizer
- add global exact row alphabet quotient
- add metrics, benchmarks, differential tests, proofs, and merge API docs
- keep PP rank semantics unchanged; do not claim symbolic PP fixed point

## 0.2.0

- family-constrained Stack product
- finite base-family Stack closure construction
- abstract cpcp-style PP rank engine
