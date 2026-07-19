# Upstream provider cache/stream contract

Operation-specific branches must satisfy:

```python
class Provider:
    provider_id: str
    operation: Operation
    priority: int
    cache_token: str

    def inverse(self, goal: Goal) -> InverseBatch:
        return InverseBatch(
            candidates=lazy_generator(),
            coverage=Coverage.complete_result(...),
        )

    def admissible_lower_bound(self, goal: Goal) -> CostVector:
        ...  # optional, must never overestimate
```

Rules:

1. Same provider cache token + same goal/context must mean identical semantics.
2. Candidates must be deterministic in order.
3. Candidate children must strictly lower Progress.
4. Candidate certificate must replay independently.
5. Timeout/resource limit raises ProviderResourceLimit or returns partial coverage.
6. A complete provider's iterator must be exhaustive.
7. Generator should be lazy; do not build the full candidate list before returning.
8. Family-specific semantics must be represented in Goal.family_context.
9. Provider must not call the legacy classifier string as a proof oracle.
10. Stack automaton internal minimization remains owned by stack-pp; integration only supplies generic interning/pruning/minimization/cache tools.
