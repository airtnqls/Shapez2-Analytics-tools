"""Small executable example using toy string shapes.

Real branches replace StringBackend and the table relations with CompactShape
plugins, while the planner/runtime code remains unchanged.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tmam_integration"))

from fakes import CertificateForwardModel, StringBackend, standard_relations
from tmam import IntegrationRegistry, PlannerConfig, Progress, TMAMPlanner, TMAMRuntime

relations = standard_relations()
registry = IntegrationRegistry()
for relation in relations:
    registry.register_relation(relation)
planner = TMAMPlanner(
    backend=StringBackend(),
    forward=CertificateForwardModel(),
    registry=registry,
    config=PlannerConfig(frozenset(relation.provider_id for relation in relations)),
)
runtime = TMAMRuntime(
    backend=StringBackend(),
    forward=CertificateForwardModel(),
    planner=planner,
)
result = runtime.analyze("PAB", Progress((3,)))
print(result.classification.primary.name)
print(result.analysis.solve.proof.to_dict() if result.analysis.solve.proof else None)
