from __future__ import annotations

import random
import unittest

from stack_pp import (
    FamilyWitness,
    PPSeed,
    PPRankEngine,
    RankedPPFamily,
    StackCertificate,
    StackClosureNode,
    trace_pp_seed_chain,
)


class ToyDomain:
    """Two-batch algebra exercising cleanup and retained parent chains."""

    def __init__(self, shuffle: bool = False):
        self.shuffle = shuffle
        self._rng = random.Random(20260717)
        self.push = {
            "pre:A": "A",
            "pre:B": "B",
            "pre:C": "C",
            "pre:D": "D",
        }
        self.progress = {"SW": 0, "C": 1, "A": 2, "B": 3, "D": 4}

    def seeds_for_batch(self, batch, previous_batch, retained):
        del retained
        if batch == 0:
            return [PPSeed("SW", -1, "swappable")]
        return [PPSeed(e.shape, e.discovery_rank, "pp") for e in previous_batch]

    def stack_closure(self, seed):
        rows = {
            "SW": [StackClosureNode("pre:A", "SW->A"), StackClosureNode("pre:B", "SW->B")],
            "A": [StackClosureNode("pre:C", "A->C"), StackClosureNode("pre:D", "A->D")],
            "C": [],
        }.get(seed.shape, [])
        rows = list(rows)
        if self.shuffle:
            self._rng.shuffle(rows)
        return rows

    def pin_push(self, predecessor):
        return self.push[predecessor]

    def canonical(self, shape):
        return shape

    def is_empty(self, shape):
        return shape == ""

    def is_swappable(self, shape):
        return shape == "SW"

    def stack_witness(self, target, allowed_base):
        base_for = {
            "B": "A",  # same-batch redundant in batch 0
            "D": "C",  # same-batch redundant in batch 1
            "A": "C",  # later C makes A globally redundant, but A is retained
        }
        base = base_for.get(target)
        if base is None or not allowed_base(base):
            return None
        family_witness = FamilyWitness("allowed", base)
        return StackCertificate(
            target=target,
            bottom=base,
            top=f"piece:{target}",
            bottom_family="allowed",
            top_family="piece",
            bottom_witness=family_witness,
            top_witness=FamilyWitness("piece", f"piece:{target}"),
        )

    def progress_key(self, shape):
        return (self.progress.get(shape, 99), shape)

    def order_key(self, shape):
        return (shape,)


class PPRankTests(unittest.TestCase):
    def test_batches_cleanup_and_true_pp(self):
        result = PPRankEngine(ToyDomain()).run()
        self.assertEqual(result.batches, (("A",), ("C",)))
        self.assertEqual(set(result.same_batch_redundant), {"B", "D"})
        self.assertEqual(set(result.entries), {"A", "C"})
        self.assertEqual(result.entries["A"].discovery_rank, 0)
        self.assertEqual(result.entries["C"].discovery_rank, 1)
        self.assertEqual(result.entries["C"].parent.seed, "A")
        self.assertEqual(set(result.global_redundant), {"A"})
        self.assertEqual(result.true_pp, ("C",))
        self.assertEqual(result.retained_for_parent_chain, ("A",))
        self.assertEqual(result.termination_reason, "fixed_point")
        self.assertTrue(result.fixed_point_proved)
        chain = trace_pp_seed_chain(result, "C")
        self.assertEqual(tuple(entry.shape for entry in chain), ("C", "A"))
        lower = RankedPPFamily(result, max_rank_exclusive=1)
        self.assertTrue(lower.contains("A"))
        self.assertFalse(lower.contains("C"))

    def test_discovery_is_deterministic_under_enumeration_order(self):
        a = PPRankEngine(ToyDomain(shuffle=False)).run()
        b = PPRankEngine(ToyDomain(shuffle=True)).run()
        self.assertEqual(a.batches, b.batches)
        self.assertEqual(a.entries, b.entries)
        self.assertEqual(a.true_pp, b.true_pp)


    def test_smallest_parent_wins_within_batch(self):
        class MultiParent(ToyDomain):
            def __init__(self, shuffle=False):
                super().__init__(shuffle=shuffle)
                self.push["pre:0A"] = "A"

            def stack_closure(self, seed):
                rows = list(super().stack_closure(seed))
                if seed.shape == "SW":
                    rows.append(StackClosureNode("pre:0A", "SW->A-better"))
                if self.shuffle:
                    self._rng.shuffle(rows)
                return rows

        a = PPRankEngine(MultiParent(False)).run()
        b = PPRankEngine(MultiParent(True)).run()
        self.assertEqual(a.entries["A"].parent.predecessor, "pre:0A")
        self.assertEqual(b.entries["A"].parent.predecessor, "pre:0A")

    def test_max_batches_is_explicit_nonproof_stop(self):
        result = PPRankEngine(ToyDomain()).run(max_batches=1)
        self.assertEqual(result.batches, (("A",),))
        self.assertEqual(result.termination_reason, "max_batches")
        self.assertFalse(result.fixed_point_proved)



    def test_transitive_stack_witness_bypasses_removed_peer(self):
        class Transitive(ToyDomain):
            def __init__(self):
                super().__init__()
                self.push.update({"pre:T": "T"})
                self.progress.update({"T": 4})

            def stack_closure(self, seed):
                if seed.shape == "SW":
                    return [
                        StackClosureNode("pre:A", "SW->A"),
                        StackClosureNode("pre:B", "SW->B"),
                        StackClosureNode("pre:T", "SW->T"),
                    ]
                return []

            def stack_witness(self, target, allowed_base):
                if target == "B" and allowed_base("A"):
                    return StackCertificate(
                        target="B",
                        bottom="A",
                        top="p:B",
                        bottom_family="allowed",
                        top_family="piece",
                        bottom_witness=FamilyWitness("allowed", "A"),
                        top_witness=FamilyWitness("piece", "p:B"),
                    )
                # T's immediate base B is itself removed.  The complete
                # witness must peel both pieces and expose A directly.
                if target == "T" and allowed_base("A"):
                    pieces = ("p:B", "p:T")
                    witnesses = tuple(FamilyWitness("piece", p) for p in pieces)
                    return StackCertificate(
                        target="T",
                        bottom="A",
                        top="bundle:T",
                        bottom_family="allowed",
                        top_family="piece",
                        bottom_witness=FamilyWitness("allowed", "A"),
                        top_witness=FamilyWitness(
                            "piece", "bundle:T", {"piece_witnesses": witnesses}
                        ),
                        top_pieces=pieces,
                        top_piece_witnesses=witnesses,
                    )
                return None

        result = PPRankEngine(Transitive()).run()
        self.assertEqual(result.batches, (("A",),))
        self.assertEqual(set(result.same_batch_redundant), {"B", "T"})
        self.assertEqual(result.same_batch_redundant["T"].pieces, ("p:B", "p:T"))

    def test_empty_pinpush_output_is_never_pp(self):
        class EmptyOutput(ToyDomain):
            def stack_closure(self, seed):
                if seed.shape == "SW":
                    return [StackClosureNode("pre:empty", "empty")]
                return []

            def pin_push(self, predecessor):
                if predecessor == "pre:empty":
                    return ""
                return super().pin_push(predecessor)

        result = PPRankEngine(EmptyOutput()).run()
        self.assertEqual(result.entries, {})
        self.assertEqual(result.stats["empty_skips"], 1)
        self.assertTrue(result.fixed_point_proved)

    def test_rank_violation_is_rejected(self):
        class Bad(ToyDomain):
            def seeds_for_batch(self, batch, previous_batch, retained):
                del previous_batch, retained
                return [PPSeed("SW", batch, "bad")]

        with self.assertRaises(AssertionError):
            PPRankEngine(Bad()).run(max_batches=1)


if __name__ == "__main__":
    unittest.main()
