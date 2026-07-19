from __future__ import annotations

import unittest

from tmam import IntegrationRegistry, Operation, PluginManifest, RegistryError

from fakes import empty_relation


class RegistryTests(unittest.TestCase):
    def test_duplicate_provider(self):
        registry = IntegrationRegistry()
        relation = empty_relation(Operation.CUT, "cut.exact")
        registry.register_relation(relation)
        with self.assertRaises(RegistryError):
            registry.register_relation(relation)

    def test_manifest_validation(self):
        registry = IntegrationRegistry()
        registry.register_relation(empty_relation(Operation.CUT, "cut.exact"))
        registry.register_plugin(
            PluginManifest(
                plugin_id="corner-half",
                version="0.1",
                provides_relations=frozenset({"cut.exact"}),
            )
        )
        self.assertEqual(registry.validate_plugins(), ())


if __name__ == "__main__":
    unittest.main()
