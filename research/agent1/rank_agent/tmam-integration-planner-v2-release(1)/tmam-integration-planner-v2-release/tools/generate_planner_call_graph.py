from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tmam_integration"))

from fakes import CertificateForwardModel, StringBackend, standard_relations
from tmam import Goal, IntegrationRegistry, PlannerConfig, Progress, TMAMPlanner

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
goal = Goal("PAB", Progress((3,)))
planner.solve_exists(goal)
planner.solve_min_cost(goal)
planner.analyze_all_ops(goal)

reports = ROOT / "reports"
reports.mkdir(exist_ok=True)
(reports / "planner_call_graph.dot").write_text(planner.call_graph_dot(), encoding="utf-8")
(reports / "planner_metrics_example.json").write_text(
    json.dumps(
        {
            "metrics": planner.metrics_snapshot().to_dict(),
            "cache": planner.cache_report(),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(reports / "planner_call_graph.dot")
print(reports / "planner_metrics_example.json")
