"""Minimal controller wiring for the existing PyQt GUI.

The real project supplies Shape, CompactShapeBackend, ForwardModel and plugins.
"""
from __future__ import annotations

from tmam import Progress, TMAMApplicationService, proof_to_precomputed_process_tree


class LegacyGUIController:
    def __init__(self, runtime, shape_factory):
        self.service = TMAMApplicationService(runtime)
        self.shape_factory = shape_factory

    def fast_possibility(self, shape, progress_components):
        return self.service.check_possible(shape, Progress(tuple(progress_components)))

    def minimum_route(self, shape, progress_components):
        return self.service.minimum_proof(shape, Progress(tuple(progress_components)))

    def detailed(self, shape, progress_components):
        return self.service.detailed_analysis(shape, Progress(tuple(progress_components)))

    def legacy_process_tree(self, detailed_view):
        if detailed_view.proof is None:
            return None
        return proof_to_precomputed_process_tree(
            detailed_view.proof,
            shape_factory=self.shape_factory,
            root_classification=detailed_view.shape_type.value,
            root_reason=" | ".join(detailed_view.missing_or_partial_reasons),
        )
