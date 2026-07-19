# Merge guide

## Public imports

```python
from corner_half import (
    is_craftable_column,
    first_rejection,
    analyze_column,
    construct_corner,
    corner_raw_proof,
    is_buildable_half,
    analyze_half,
    construct_half,
    half_raw_proof,
    verify_proof,
    HALF_FAMILY,
)
```

## core-kernel adapter boundary

The branch uses structural cells `-/S/P/c`. On merge, implement
`interfaces.CompactPhysics` with exact normalized operations:

```text
normalize, stable, rotate, cut, swap, stack, generate, pin_push
```

Keep the bundled reference kernel and tests for differential verification. Do
not change the DFA or theorem semantics.

## planner integration

- Fast family facts: `is_craftable_column`, `is_buildable_half`.
- Compact parent witnesses: `construct_corner`, `construct_half`.
- Fully expanded ProcessTree/audit witnesses: `corner_raw_proof`,
  `half_raw_proof`; verify with `verify_proof`.

The only raw-proof leaf is the one-layer `SSSS` input. Never replace exact
rejection with timeout or `UNKNOWN`.
