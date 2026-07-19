# C7 structural compiler — completed lemma

## Input convention

`compile_c7(post_lift_a, cap, duties)` receives A after receipt/lift but before
overflow destruction and gravity. Duties are post-lift coordinates.

```text
ANCHORED/NATURAL(f,t): 0 < t < f
FLOOR(f,0): unique lowest duty, empty A receipt
```

The compiler verifies receipt type, disjoint source order, empty post-shatter
fall paths, surviving anchors, and unit separation. Invalid snapshots are
rejected as invalid C7 witnesses, not as impossible target columns.

## Helpers

### B — static side

A grounded continuous S/P tower. B[f]=P exactly at faller sources and B=S at
other active layers. It supports stationary A content without supporting a
faller.

### C — overflow trigger

Pre-push C is `c^L`. Push creates a receipt P and shifts the top crystal into
overflow. Its component destruction reaches every D relay.

### D — relay/catcher side

For each duty:

```text
pedestal/anchor ... catcher at t-1
relay c-run at t..f-1
rider S at f
```

A floor duty uses a source-level relay rather than a rider pair. Empty active D
positions are canonically filled by S. This strengthening makes the `(D,A)`
half independently stable and is harmless:

- at an occupied A layer it duplicates static support;
- at an empty A layer it cannot join an A group;
- at relay layers it is not inserted;
- at faller sources the intended rider already occupies D.

## Correctness

1. **Predecessor stability.** B/C/D are grounded. A statics are supported by B
   or D; fallers are held by sacrificial A crystal or D rider/relay.
2. **Exact shatter.** C overflow destroys C, D relays, and exactly the A
   crystal runs intersecting relay levels. Helper S/P cells break all paths to
   keeper runs.
3. **Exact fall.** For anchored duty, A faller and D rider form one group and
   D catcher sets its drop to f-t. Floor duty becomes an unsupported singleton
   and falls to layer0.
4. **No interference.** Units are separated by surviving static anchor layers;
   gravity processes them bottom-up.
5. **Helper craftability.** Every predecessor column is natural-route Corner.
   `(B,C)` and `(D,A)` are stable natural halves. They are built independently,
   swapped to `(B,C,D,A)`, then rotated to `(A,B,C,D)`.

This last point closes helper fabrication without recursive use of event
Corner.

## Machine validation

- cap6 single-duty candidates: 3,840 attempted, 259 valid, failure 0
- random candidate snapshots: 50,000, valid 5,987, failure 0
- systematic multi-duty: 622, failure 0
- high random multi-duty: 10,000, failure 0
- accepted event columns length7..200: 10,000, failure 0
- complete Corner constructor high event: 2,000, failure 0

The all-layer result follows from the coordinate proof above; finite tests audit
the implementation.
