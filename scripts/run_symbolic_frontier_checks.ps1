param(
    [int]$RandomSamples = 5000,
    [int]$DataLimit = 5000,
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

python -B scripts\symbolic_frontier_automaton.py `
    --depth 5 `
    --corner-mode quotient `
    --fallback kernel-hybrid-core `
    --eval-random $RandomSamples `
    --eval-limit $RandomSamples `
    --eval-random-layers 5 `
    --seed 1040 `
    --max-mismatches 4 `
    --fail-on-unknown `
    --fail-on-legacy-fallback `
    --fail-on-known-mismatch `
    --eval-max-seconds $TimeoutSeconds

python -B scripts\symbolic_frontier_automaton.py `
    --depth 5 `
    --corner-mode quotient `
    --fallback kernel-hybrid-core `
    --eval-data data `
    --eval-per-file 240 `
    --eval-limit $DataLimit `
    --seed 123 `
    --max-mismatches 4 `
    --fail-on-unknown `
    --fail-on-legacy-fallback `
    --eval-max-seconds $TimeoutSeconds

python -B scripts\symbolic_frontier_automaton.py `
    --depth 6 `
    --corner-mode quotient `
    --fallback kernel-hybrid-core `
    --eval-data data `
    --eval-per-file 50 `
    --eval-limit 120 `
    --eval-min-layers 6 `
    --eval-max-layers 6 `
    --seed 6206 `
    --max-mismatches 4 `
    --compare-limit 40 `
    --ignore-legacy-unknown `
    --fail-on-unknown `
    --fail-on-legacy-fallback `
    --fail-on-known-mismatch `
    --eval-max-seconds $TimeoutSeconds
