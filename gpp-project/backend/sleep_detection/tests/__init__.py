"""
sleep_detection/tests/test_sleep_detection.py
─────────────────────────────────────────────
Unit tests for the sleep‑event detection pipeline.

Run with:
    python -m pytest backend/sleep_detection/tests/ -v
or:
    python backend/sleep_detection/tests/test_sleep_detection.py
"""

from __future__ import annotations
import os, sys, json, tempfile, unittest

import numpy as np

# ensure project root is importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.sleep_detection.core import (
    compute_baseline_rr,
    mask_motion_segments,
    detect_sleep_events,
)
from backend.sleep_detection.io_utils import save_sleep_report


# ────────────────────────────────────────────────────────────────────
#  SYNTHETIC DATA GENERATORS
# ────────────────────────────────────────────────────────────────────

def _make_normal_breathing(duration_sec=120, fs=20, freq=0.25, amplitude=1.0):
    """Sinusoidal respiration signal (normal breathing)."""
    t = np.arange(0, duration_sec, 1.0/fs)
    rr = amplitude * np.sin(2 * np.pi * freq * t)
    motion = np.zeros_like(t)
    return t, rr, motion


def _make_apnea_segment(duration_sec=300, fs=20, freq=0.25, amplitude=1.0,
                         apnea_start=120, apnea_end=210):
    """Normal breathing with an embedded apnea (amplitude → 0) segment."""
    t = np.arange(0, duration_sec, 1.0/fs)
    rr = amplitude * np.sin(2 * np.pi * freq * t)
    # simulate apnea: drop amplitude to 10 % of normal
    mask = (t >= apnea_start) & (t < apnea_end)
    rr[mask] *= 0.05
    motion = np.zeros_like(t)
    return t, rr, motion


def _make_motion_segment(duration_sec=180, fs=20, freq=0.25, amplitude=1.0,
                          motion_start=60, motion_end=90):
    """Normal breathing with a high‑motion artifact segment."""
    t = np.arange(0, duration_sec, 1.0/fs)
    rr = amplitude * np.sin(2 * np.pi * freq * t)
    motion = np.zeros_like(t)
    mask = (t >= motion_start) & (t < motion_end)
    motion[mask] = 0.9  # high motion
    # motion also corrupts the respiration signal
    rr[mask] += np.random.randn(int(mask.sum())) * 2
    return t, rr, motion


# ────────────────────────────────────────────────────────────────────
#  TESTS
# ────────────────────────────────────────────────────────────────────

class TestComputeBaseline(unittest.TestCase):

    def test_stable_signal(self):
        t, rr, _ = _make_normal_breathing(duration_sec=60)
        baseline = compute_baseline_rr(np.abs(rr), t)
        self.assertGreater(baseline, 0)
        self.assertAlmostEqual(baseline, 1.0, delta=0.3)

    def test_with_motion_exclusion(self):
        t, rr, motion = _make_motion_segment(duration_sec=60,
                                              motion_start=0, motion_end=30)
        baseline = compute_baseline_rr(np.abs(rr), t, motion_scores=motion)
        # should still approximate 1.0 since motion samples are excluded
        self.assertGreater(baseline, 0.3)


class TestMotionMasking(unittest.TestCase):

    def test_no_motion(self):
        motion = np.zeros(600)
        mask = mask_motion_segments(motion, n_epochs=4, epoch_len=150,
                                    overlap_len=75)
        self.assertTrue(np.all(~mask))

    def test_high_motion(self):
        motion = np.ones(600) * 0.9
        mask = mask_motion_segments(motion, n_epochs=4, epoch_len=150,
                                    overlap_len=75)
        self.assertTrue(np.all(mask))


class TestDetectSleepEvents(unittest.TestCase):

    def test_all_normal(self):
        t, rr, motion = _make_normal_breathing(duration_sec=120)
        result = detect_sleep_events(np.abs(rr), t, motion)
        labels = result["epoch_labels"]
        # every epoch should be Normal
        for lab in labels:
            self.assertEqual(lab, "Normal")

    def test_apnea_detected(self):
        t, rr, motion = _make_apnea_segment(duration_sec=300,
                                             apnea_start=120, apnea_end=210)
        result = detect_sleep_events(np.abs(rr), t, motion,
                                     sampling_rate=20)
        labels = result["epoch_labels"]
        # at least one epoch should be labelled Apnea
        self.assertIn("Apnea", labels,
                      "Expected at least one Apnea epoch in a 90 s gap")

    def test_motion_overrides_apnea(self):
        """If motion is high during an amplitude drop, label should be
        Motion, NOT Apnea."""
        t, rr, _ = _make_apnea_segment(duration_sec=300,
                                        apnea_start=120, apnea_end=210)
        motion = np.zeros_like(t)
        motion[(t >= 120) & (t < 210)] = 0.9  # high motion during drop
        result = detect_sleep_events(np.abs(rr), t, motion, sampling_rate=20)
        labels = result["epoch_labels"]
        # should NOT label any epoch in that zone as Apnea
        apnea_in_motion_zone = False
        for ev in result["events"]:
            if ev["timestamp_start"] >= 120 and ev["timestamp_end"] <= 210:
                if ev["event_type"] == "Apnea":
                    apnea_in_motion_zone = True
        self.assertFalse(apnea_in_motion_zone,
                         "Apnea should not be labelled during motion")

    def test_summary_keys(self):
        t, rr, motion = _make_normal_breathing(duration_sec=60)
        result = detect_sleep_events(np.abs(rr), t, motion)
        summary = result["summary"]
        for key in ["total_duration_sec", "total_epochs", "baseline_amplitude",
                     "amplitude_threshold", "event_counts", "severity"]:
            self.assertIn(key, summary)

    def test_irregular_detection(self):
        """A short amplitude drop (< apnea threshold) should be Irregular."""
        t, rr, motion = _make_apnea_segment(duration_sec=180,
                                             apnea_start=80, apnea_end=110)
        result = detect_sleep_events(np.abs(rr), t, motion,
                                     sampling_rate=20,
                                     apnea_min_consecutive=5)
        labels = result["epoch_labels"]
        # should see Irregular but not Apnea (gap is short)
        self.assertIn("Irregular", labels)


class TestSaveReport(unittest.TestCase):

    def test_csv_and_json_created(self):
        t, rr, motion = _make_normal_breathing(duration_sec=60)
        result = detect_sleep_events(np.abs(rr), t, motion)

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = save_sleep_report(result, tmpdir)
            self.assertIn("csv", paths)
            self.assertIn("json", paths)
            self.assertTrue(os.path.isfile(paths["csv"]))
            self.assertTrue(os.path.isfile(paths["json"]))

            with open(paths["json"]) as f:
                data = json.load(f)
            self.assertIn("summary", data)
            self.assertIn("events", data)


# ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    unittest.main()
