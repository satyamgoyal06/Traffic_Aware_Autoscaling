import unittest

from guardscale.policy import ScalingObservation, decide


class DecideTests(unittest.TestCase):
    def observation(self, **overrides):
        values = dict(
            current_replicas=2,
            min_replicas=1,
            max_replicas=12,
            observed_rps=80,
            forecast_rps=240,
            rps_per_replica=50,
            attack_risk_upper=0.0,
            max_predictive_step=4,
        )
        values.update(overrides)
        return ScalingObservation(**values)

    def test_low_risk_allows_capped_predictive_step(self):
        result = decide(self.observation())
        self.assertEqual(result.forecast_target, 5)
        self.assertEqual(result.desired_replicas, 5)
        self.assertEqual(result.predictive_step_budget, 4)

    def test_high_risk_limits_prediction_but_keeps_reactive_escape(self):
        result = decide(self.observation(attack_risk_upper=1.0))
        self.assertEqual(result.predictive_step_budget, 0)
        self.assertEqual(result.desired_replicas, 2)
        escaped = decide(self.observation(attack_risk_upper=1.0, observed_rps=260))
        self.assertEqual(escaped.desired_replicas, 6)
        self.assertEqual(escaped.reason, "reactive_slo_escape")

    def test_replica_floor_and_ceiling_are_enforced(self):
        floor = decide(self.observation(current_replicas=1, observed_rps=0, forecast_rps=0))
        self.assertEqual(floor.desired_replicas, 1)
        no_downscale = decide(self.observation(current_replicas=5, observed_rps=0, forecast_rps=0))
        self.assertEqual(no_downscale.desired_replicas, 5)
        ceiling = decide(self.observation(max_replicas=3, forecast_rps=10_000))
        self.assertEqual(ceiling.desired_replicas, 3)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            decide(self.observation(attack_risk_upper=1.1))
        with self.assertRaises(ValueError):
            decide(self.observation(rps_per_replica=0))


if __name__ == "__main__":
    unittest.main()
