# Half linear fast-path experiment

This branch compares a generic prefix-rematerializing proof DAG with a strict
O(L) event-periodic Half compiler for the supplied target.

The fast path is accepted only when:

- the permanent support spine is present;
- crystal event gaps are constant;
- the complete suffix matches the inferred block;
- independent structural replay reconstructs the exact target;
- node, edge, operation, and materialized-cell counts all decrease;
- 200 deterministic mutations are rejected;
- scan count remains at most `2L` through 128 repeated blocks.

Primitive Shapez2 Pin/Swap physics replay is intentionally not claimed by this
standalone experiment; it is the required integration gate before production.
