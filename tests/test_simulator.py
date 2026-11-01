import json
import tempfile
import unittest
from pathlib import Path

from guardscale.benchmark import run_benchmark
from guardscale.simulator import SimulationConfig, simulate
from guardscale.workload import make_scenario


class WorkloadAndSimulatorTests(unittest.TestCase):
    def test_scenario_generation_is_seeded_and_labels_are_explicit(self):
        first = make_scenario("adaptive_attack", seed=23, duration=180)
        second = make_scenario("adaptive_attack", seed=23, duration=180)
        self.assertEqual(first, second)
        self.assertTrue(all(row.attack_rps >= 0 for row in first))
        self.assertTrue(any(row.attack_rps > 0 for row in first))

    def test_simulation_is_reproducible_and_labels_evidence(self):
        rows = make_scenario("attack_flood", seed=4, duration=180)
        one = simulate("guardscale", "attack_flood", 4, rows)
        two = simulate("guardscale", "attack_flood", 4, rows)
        self.assertEqual(one, two)
        self.assertEqual(one["evidence_type"], "synthetic_simulation")
        self.assertGreater(one["attack_window_replica_seconds"], 0)
        self.assertLessEqual(one["max_ready_replicas"], SimulationConfig().max_replicas)

    def test_benchmark_writes_machine_readable_results_and_site(self):
        with tempfile.TemporaryDirectory() as temp:
            payload = run_benchmark(Path(temp) / "run", seeds=2, duration=180)
            root = Path(temp) / "run"
            self.assertEqual(len(payload["runs"]), 2 * 4 * 4)
            self.assertTrue((root / "index.html").is_file())
            self.assertTrue((root / "runs.csv").is_file())
            saved = json.loads((root / "results.json").read_text())
            self.assertEqual(saved["evidence_type"], "synthetic_simulation")
            self.assertIn("queue latency", " ".join(saved["limitations"]).lower())


if __name__ == "__main__":
    unittest.main()
