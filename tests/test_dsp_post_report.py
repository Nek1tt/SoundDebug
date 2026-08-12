from __future__ import annotations

import unittest

from services.workers.dsp_worker.recommendations import generate_findings, split_priority_findings
from services.workers.dsp_worker.report_builder import build_report


class DiagnosticContractTests(unittest.TestCase):
    def setUp(self):
        self.metrics = {
            "meta": {"num_channels": 2, "sample_rate": 48000},
            "loudness": {
                "clipping_count": 0, "true_peak_dbtp": -2.0, "plr_lu": 10.0,
                "dc_offset_by_channel": [0.0, 0.0],
            },
            "stereo": {
                "is_mono": False, "channel_layout": "stereo", "stereo_width": 0.5,
                "minimum_phase_correlation": 0.8, "mono_fold_down_loss_db": -0.3,
                "bass_side_energy_pct": 4.0,
            },
            "tonal": {"band_energy_pct": {"low_mid": 20.0}},
            "rhythm": {},
        }

    def comparison(self, reliability: str = "HIGH", support: int = 3) -> dict:
        return {
            "source": "references", "reference_count": 3,
            "tonal_shape_difference": {
                "low_mid": {
                    "difference_db": 4.7, "reference_mad_db": 0.3,
                    "support_count": support, "reference_count": 3,
                    "reliability": reliability,
                    "reliability_reason": f"support {support}/3",
                }
            },
            "outlier_segments": [{"band": "low_mid", "time_sec": 42.0, "difference_db": 5.0}],
            "dynamics_difference": {}, "stereo_difference": {}, "loudness_difference": None,
        }

    def test_every_finding_has_exact_class_and_full_card(self):
        metrics = {**self.metrics, "loudness": {**self.metrics["loudness"], "plr_lu": 5.5}}
        findings = generate_findings(metrics, "techno", self.comparison())
        required = {
            "classification", "title", "priority", "what_detected", "why_attention",
            "audible_meaning", "possible_causes", "daw_check_steps", "do_not_automate",
            "reliability", "reliability_reason",
        }
        self.assertTrue(findings)
        for finding in findings:
            self.assertIn(finding["classification"], {"FACT", "REFERENCE_DIFFERENCE", "HYPOTHESIS"})
            self.assertTrue(required.issubset(finding))

    def test_consistent_tonal_difference_becomes_hypothesis_without_eq_setting(self):
        tonal = next(item for item in generate_findings(self.metrics, comparison=self.comparison()) if item["category"] == "tonal_balance")
        self.assertEqual(tonal["classification"], "HYPOTHESIS")
        self.assertEqual(tonal["timestamps_sec"], [42.0])
        self.assertIn("не вырезайте", tonal["do_not_automate"].lower())
        self.assertIn("4.7", tonal["do_not_automate"])
        combined = " ".join(tonal["daw_check_steps"] + [tonal["do_not_automate"]]).lower()
        self.assertNotIn("q=", combined)

    def test_single_reference_outlier_stays_reference_difference(self):
        tonal = next(item for item in generate_findings(self.metrics, comparison=self.comparison("LOW", 1)) if item["category"] == "tonal_balance")
        self.assertEqual(tonal["classification"], "REFERENCE_DIFFERENCE")
        self.assertEqual(tonal["priority"], "LOW")

    def test_technical_fault_is_direct_fact(self):
        metrics = {**self.metrics, "loudness": {**self.metrics["loudness"], "clipping_count": 50, "clipping_events": [{"start_sec": 1.2}]}}
        finding = generate_findings(metrics)[0]
        self.assertEqual(finding["id"], "FACT_SAMPLE_CLIPPING")
        self.assertEqual(finding["classification"], "FACT")
        self.assertEqual(finding["reliability"], "DIRECT")

    def test_report_has_maximum_three_main_recommendations(self):
        metrics = {
            **self.metrics,
            "loudness": {
                **self.metrics["loudness"], "clipping_count": 10,
                "clipping_events": [{"start_sec": 1.0}], "true_peak_dbtp": 0.2,
                "plr_lu": 4.0, "dc_offset_by_channel": [0.02, 0.0],
            },
        }
        report = build_report(metrics, "techno", self.comparison(), {"enabled": False}, uses_user_references=True)
        self.assertLessEqual(len(report["recommendations"]), 3)
        self.assertGreater(len(report["additional_findings"]), 0)
        self.assertEqual(report["report_version"], "p0-trustworthy-diagnostics-1")
        self.assertIn("technical_details", report)
        payload = str(report).lower()
        self.assertNotIn("similarity_percent", payload)
        self.assertNotIn("tonal_confidence", payload)

    def test_split_never_discards_findings(self):
        findings = [{"id": str(index)} for index in range(7)]
        main, additional = split_priority_findings(findings)
        self.assertEqual(len(main), 3)
        self.assertEqual(main + additional, findings)


if __name__ == "__main__":
    unittest.main()
