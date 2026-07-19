from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tmam import LegacyShapeTypeKey


def enum_members(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ShapeType":
            return {
                target.id
                for statement in node.body
                if isinstance(statement, ast.Assign)
                for target in statement.targets
                if isinstance(target, ast.Name) and target.id.isupper()
            }
    raise RuntimeError("ShapeType enum was not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("classifier", type=Path)
    args = parser.parse_args()
    legacy = enum_members(args.classifier)
    integration = {member.name for member in LegacyShapeTypeKey}
    print("missing_in_integration=", sorted(legacy - integration))
    print("extra_in_integration=", sorted(integration - legacy))
    return 0 if legacy == integration else 1


if __name__ == "__main__":
    raise SystemExit(main())
