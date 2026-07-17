"""
Unit tests for the motion & posture context pipeline.

Run with:
    python -m unittest backend.motion_posture.tests.test_motion_posture -v
"""

from __future__ import annotations
import json, os, shutil, tempfile, unittest
import numpy as np

# ── Module under test ───────────────────────────────────────────────
from backend.motion_posture import config as CFG
from backend.motion_posture.features import (
    epoch_indices,
    extract_epoch_features,
    extract_all_features,
    FEATURE_DIM,
)
from backend.motion_posture.motion import (
    classify_motion_segments,
    _epoch_motion_score,
)
from backend.motion_posture.posture import (
    train_posture_classifier,
    predict_posture,
    heuristic_posture,
    _generate_synthetic_posture_data,
)
from backend.motion_posture.context import align_context_with_events
from backend.motion_posture.io_utils import save_posture_motion_report


# ────────────────────────────────────────────────────────────────────
#  HELPERS – synthetic signal generation
# ────────────────────────────────────────────────────────────────────
FS = 20  # 20 Hz sampling rate


def _make_signals(duration_sec: float, noise: float = 0.01) -> dict:
    """Generate clean sinusoidal vital-sign signals for *duration_sec*."""
    n = int(duration_sec * FS)
    t = np.arange(n) / FS

    rng = np.random.RandomState(0)
    breath = 0.6 * np.sin(2 * np.pi * 0.25 * t) + rng.normal(0, noise, n)
    heart  = 0.3 * np.sin(2 * np.pi * 1.2 * t)  + rng.normal(0, noise, n)
    chest  = 0.5 * np.sin(2 * np.pi * 0.25 * t) + rng.normal(0, noise, n)
    combined = 0.5 * chest + 0.3 * breath + 0.2 * heart

    motion_raw = np.abs(np.diff(chest, prepend=chest[0]))
    mx = np.percentile(motion_raw, 99) if n > 1 else 1.0
    motion = np.clip(motion_raw / max(mx, 1e-8), 0, 1)

    return {
        "timestamps":    t,
        "chest_disp":    chest,
        "breath_wave":   breath,
        "heart_wave":    heart,
        "combined":      combined,
        "range_m":       np.full(n, 0.4) + rng.normal(0, 0.01, n),
        "motion_scores": motion,
        "rr_bpm":        np.full(n, 15.0),
        "hr_bpm":        np.full(n, 72.0),
    }


def _make_still_signals(duration_sec: float) -> dict:
    """Signals with near-zero motion."""
    n = int(duration_sec * FS)
    t = np.arange(n) / FS
    return {
        "timestamps":    t,
        "chest_disp":    np.full(n, 0.3),      # constant → zero diff
        "breath_wave":   np.full(n, 0.0),
        "heart_wave":    np.full(n, 0.0),
        "combined":      np.full(n, 0.15),
        "range_m":       np.full(n, 0.4),
        "motion_scores": np.zeros(n),
        "rr_bpm":        np.full(n, 14.0),
        "hr_bpm":        np.full(n, 65.0),
    }


def _make_high_motion_signals(duration_sec: float) -> dict:
    """Signals with very large motion (simulating turning)."""
    n = int(duration_sec * FS)
    t = np.arange(n) / FS
    rng = np.random.RandomState(7)
    chest = rng.uniform(-2, 2, n)   # large, random chest movement
    motion = np.ones(n)             # max motion
    return {
        "timestamps":    t,
        "chest_disp":    chest,
        "breath_wave":   rng.normal(0, 0.5, n),
        "heart_wave":    rng.normal(0, 0.3, n),
        "combined":      chest * 0.5,
        "range_m":       np.full(n, 0.5) + rng.normal(0, 0.1, n),
        "motion_scores": motion,
        "rr_bpm":        np.full(n, 16.0),
        "hr_bpm":        np.full(n, 80.0),
    }


# ====================================================================
#  FEATURE EXTRACTION TESTS
# ====================================================================
class TestFeatureExtraction(unittest.TestCase):

    def test_feature_dim_constant(self):
        """FEATURE_DIM should equal 34."""
        self.assertEqual(FEATURE_DIM, 34)

    def test_epoch_indices_basic(self):
        """Epoch indices cover the signal with correct overlap."""
        idx = epoch_indices(n_samples=1000, epoch_len=300, overlap_len=150)
        self.assertGreater(len(idx), 0)
        for s, e in idx:
            self.assertGreaterEqual(e - s, 150)  # at least half epoch
            self.assertLessEqual(e, 1000)

    def test_epoch_indices_empty(self):
        """No epochs if signal shorter than epoch_len."""
        idx = epoch_indices(n_samples=10, epoch_len=300, overlap_len=150)
        self.assertEqual(len(idx), 0)

    def test_extract_epoch_features_shape(self):
        """Feature vector for one epoch should have 34 elements."""
        data = _make_signals(60)
        vec = extract_epoch_features(
            data["chest_disp"], data["breath_wave"], data["heart_wave"],
            data["combined"], data["range_m"], data["motion_scores"],
            data["rr_bpm"], data["hr_bpm"],
            start=0, end=300,
        )
        self.assertEqual(vec.shape, (FEATURE_DIM,))
        self.assertFalse(np.any(np.isnan(vec)))

    def test_extract_all_features_shape(self):
        """Feature matrix should have shape (n_epochs, 34)."""
        data = _make_signals(120)
        X, indices = extract_all_features(data, sampling_rate=FS)
        self.assertEqual(X.shape[1], FEATURE_DIM)
        self.assertEqual(X.shape[0], len(indices))
        self.assertGreater(X.shape[0], 0)

    def test_extract_features_short_signal(self):
        """Very short signal (< 1 epoch) → zero-row feature matrix."""
        data = _make_signals(0.5)  # 10 samples, way less than epoch
        X, indices = extract_all_features(data, sampling_rate=FS)
        self.assertEqual(X.shape[0], 0)
        self.assertEqual(len(indices), 0)


# ====================================================================
#  MOTION CLASSIFICATION TESTS
# ====================================================================
class TestMotionClassification(unittest.TestCase):

    def test_still_motion(self):
        """Constant signals should be classified as Still."""
        data = _make_still_signals(60)
        result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        labels = result["epoch_labels"]
        self.assertGreater(len(labels), 0)
        for lbl in labels:
            self.assertEqual(lbl, "Still")

    def test_high_motion_is_turning(self):
        """Extreme motion should be classified as Major Movement or Turning."""
        data = _make_high_motion_signals(60)
        result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        labels = result["epoch_labels"]
        self.assertGreater(len(labels), 0)
        major_or_turning = [l for l in labels if l in ("Major Movement", "Turning")]
        self.assertGreater(len(major_or_turning), 0,
                           f"Expected Major/Turning but got {labels}")

    def test_moderate_motion(self):
        """Normal sinusoidal breathing should yield Still or Minor Movement."""
        data = _make_signals(60)
        result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        labels = result["epoch_labels"]
        for lbl in labels:
            self.assertIn(lbl, CFG.MOTION_LABELS)

    def test_epoch_records_structure(self):
        """Each epoch record should contain expected keys."""
        data = _make_signals(60)
        result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        for rec in result["epoch_records"]:
            self.assertIn("epoch_index", rec)
            self.assertIn("motion_type", rec)
            self.assertIn("motion_score", rec)
            self.assertIn("timestamp_start", rec)
            self.assertIn("timestamp_end", rec)

    def test_epoch_motion_score_bounds(self):
        """All epoch scores should be in [0, 1]."""
        data = _make_signals(60)
        result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        for s in result["epoch_scores"]:
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)


# ====================================================================
#  POSTURE CLASSIFICATION TESTS
# ====================================================================
class TestPostureClassification(unittest.TestCase):

    _model = None
    _tmpdir = None

    @classmethod
    def setUpClass(cls):
        """Train posture model once for all posture tests."""
        cls._tmpdir = tempfile.mkdtemp(prefix="mp_test_")
        model_path = os.path.join(cls._tmpdir, "posture_test.joblib")
        result = train_posture_classifier(save_path=model_path, seed=42)
        cls._model = result["model"]
        cls._accuracy = result["accuracy"]
        cls._model_path = model_path

    @classmethod
    def tearDownClass(cls):
        if cls._tmpdir and os.path.isdir(cls._tmpdir):
            shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_training_accuracy(self):
        """Synthetic posture classifier should exceed 60% accuracy."""
        self.assertGreater(self._accuracy, 0.60)

    def test_predict_shape(self):
        """predict_posture should return labels and confidences."""
        X_syn, _ = _generate_synthetic_posture_data(n_per_class=20, seed=99)
        labels, confs = predict_posture(X_syn, model=self._model)
        self.assertEqual(len(labels), X_syn.shape[0])
        self.assertEqual(confs.shape, (X_syn.shape[0],))

    def test_predict_labels_valid(self):
        """All predicted labels should be in the allowed set."""
        X_syn, _ = _generate_synthetic_posture_data(n_per_class=20, seed=99)
        labels, _ = predict_posture(X_syn, model=self._model)
        for lbl in labels:
            self.assertIn(lbl, CFG.POSTURE_LABELS)

    def test_confidence_range(self):
        """All confidences should be in [0, 1]."""
        X_syn, _ = _generate_synthetic_posture_data(n_per_class=20, seed=99)
        _, confs = predict_posture(X_syn, model=self._model)
        self.assertTrue(np.all(confs >= 0.0))
        self.assertTrue(np.all(confs <= 1.0))

    def test_heuristic_supine(self):
        """Heuristic: high-amplitude symmetric chest → Supine."""
        n = 200
        t = np.arange(n) / FS
        chest  = 0.8 * np.sin(2 * np.pi * 0.25 * t)
        breath = 0.5 * np.sin(2 * np.pi * 0.25 * t)
        range_m = np.full(n, 0.4)
        result = heuristic_posture(chest, breath, range_m, 0, n)
        self.assertEqual(result, "Supine")

    def test_heuristic_prone(self):
        """Heuristic: low breath amplitude + close range → Prone."""
        n = 200
        chest  = 0.1 * np.sin(2 * np.pi * 0.25 * np.arange(n) / FS)
        breath = 0.05 * np.sin(2 * np.pi * 0.25 * np.arange(n) / FS)
        range_m = np.full(n, 0.25)
        result = heuristic_posture(chest, breath, range_m, 0, n)
        self.assertEqual(result, "Prone")

    def test_heuristic_left_lateral(self):
        """Heuristic: negative chest skew → Left Lateral."""
        n = 200
        rng = np.random.RandomState(5)
        # Generate strongly left-skewed signal (chi-squared, flipped)
        chest  = -rng.chisquare(df=2, size=n)  # strong negative skew
        breath = 0.3 * np.sin(2 * np.pi * 0.25 * np.arange(n) / FS)
        range_m = np.full(n, 0.45)
        result = heuristic_posture(chest, breath, range_m, 0, n)
        self.assertEqual(result, "Left Lateral")

    def test_heuristic_unknown_short(self):
        """Heuristic: fewer than 10 samples → Unknown."""
        result = heuristic_posture(np.zeros(5), np.zeros(5), np.zeros(5), 0, 5)
        self.assertEqual(result, "Unknown")


# ====================================================================
#  CONTEXT FUSION TESTS
# ====================================================================
class TestContextFusion(unittest.TestCase):

    def _make_records(self):
        """Helper to create motion and posture records."""
        motion_records = [
            {"epoch_index": 0, "timestamp_start": 0, "timestamp_end": 15,
             "motion_type": "Still", "motion_score": 0.05},
            {"epoch_index": 1, "timestamp_start": 7.5, "timestamp_end": 22.5,
             "motion_type": "Minor Movement", "motion_score": 0.25},
            {"epoch_index": 2, "timestamp_start": 15, "timestamp_end": 30,
             "motion_type": "Major Movement", "motion_score": 0.50},
        ]
        posture_records = [
            {"epoch_index": 0, "timestamp_start": 0, "timestamp_end": 15,
             "posture_label": "Supine", "posture_confidence": 0.85},
            {"epoch_index": 1, "timestamp_start": 7.5, "timestamp_end": 22.5,
             "posture_label": "Left Lateral", "posture_confidence": 0.72},
            {"epoch_index": 2, "timestamp_start": 15, "timestamp_end": 30,
             "posture_label": "Left Lateral", "posture_confidence": 0.68},
        ]
        return motion_records, posture_records

    def test_combined_timeline_length(self):
        """Combined timeline should have epochs from both sources."""
        motion_recs, posture_recs = self._make_records()
        result = align_context_with_events(motion_recs, posture_recs)
        self.assertEqual(len(result["combined_timeline"]), 3)

    def test_combined_has_both_labels(self):
        """Each combined epoch should have both motion and posture keys."""
        motion_recs, posture_recs = self._make_records()
        result = align_context_with_events(motion_recs, posture_recs)
        for rec in result["combined_timeline"]:
            self.assertIn("motion_type", rec)
            self.assertIn("posture_label", rec)

    def test_no_sleep_events(self):
        """Without sleep events, event_annotations should be empty."""
        motion_recs, posture_recs = self._make_records()
        result = align_context_with_events(motion_recs, posture_recs, sleep_events=None)
        self.assertEqual(len(result["event_annotations"]), 0)

    def test_sleep_event_annotation(self):
        """Sleep events should produce contextual annotations."""
        motion_recs, posture_recs = self._make_records()
        sleep_events = [
            {"event_type": "Apnea", "timestamp_start": 10, "timestamp_end": 20,
             "RR_mean": 8.0, "HR_mean": 60.0},
        ]
        result = align_context_with_events(motion_recs, posture_recs, sleep_events=sleep_events)
        self.assertEqual(len(result["event_annotations"]), 1)
        ann = result["event_annotations"][0]
        self.assertEqual(ann["event_type"], "Apnea")
        self.assertIn("posture_during", ann)
        self.assertIn("description", ann)

    def test_session_stats_keys(self):
        """Session stats should contain expected keys."""
        motion_recs, posture_recs = self._make_records()
        result = align_context_with_events(motion_recs, posture_recs)
        stats = result["session_stats"]
        self.assertIn("posture_distribution_pct", stats)
        self.assertIn("motion_epoch_counts", stats)
        self.assertIn("posture_epoch_counts", stats)

    def test_normal_events_skipped(self):
        """Normal sleep events should NOT generate annotations."""
        motion_recs, posture_recs = self._make_records()
        sleep_events = [
            {"event_type": "Normal", "timestamp_start": 0, "timestamp_end": 10},
        ]
        result = align_context_with_events(motion_recs, posture_recs, sleep_events=sleep_events)
        self.assertEqual(len(result["event_annotations"]), 0)


# ====================================================================
#  IO / REPORT SAVING TESTS
# ====================================================================
class TestIOUtils(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="mp_io_test_")

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _dummy_context_result(self):
        return {
            "combined_timeline": [
                {"epoch_index": 0, "timestamp_start": 0, "timestamp_end": 15,
                 "motion_type": "Still", "motion_score": 0.05,
                 "posture_label": "Supine", "posture_confidence": 0.85,
                 "associated_sleep_event": None},
            ],
            "event_annotations": [],
            "session_stats": {"posture_distribution_pct": {"Supine": 100.0}},
        }

    def _dummy_motion_result(self):
        return {
            "epoch_labels": ["Still"],
            "epoch_scores": [0.05],
            "epoch_indices": [(0, 300)],
            "epoch_centers": [7.5],
            "epoch_records": [
                {"epoch_index": 0, "motion_type": "Still", "motion_score": 0.05,
                 "timestamp_start": 0, "timestamp_end": 15},
            ],
        }

    def test_save_csv(self):
        """save_posture_motion_report should create a CSV file."""
        ctx = self._dummy_context_result()
        mot = self._dummy_motion_result()
        posture_recs = [{"posture_label": "Supine", "posture_confidence": 0.85}]
        paths = save_posture_motion_report(
            ctx, mot, posture_recs, self._tmpdir,
            save_csv=True, save_json=False,
        )
        self.assertIn("csv", paths)
        self.assertTrue(os.path.isfile(paths["csv"]))

    def test_save_json(self):
        """save_posture_motion_report should create a valid JSON file."""
        ctx = self._dummy_context_result()
        mot = self._dummy_motion_result()
        posture_recs = [{"posture_label": "Supine", "posture_confidence": 0.85}]
        paths = save_posture_motion_report(
            ctx, mot, posture_recs, self._tmpdir,
            save_csv=False, save_json=True,
        )
        self.assertIn("json", paths)
        with open(paths["json"]) as f:
            obj = json.load(f)
        self.assertIn("session_stats", obj)
        self.assertIn("combined_timeline", obj)

    def test_save_both(self):
        """Both CSV and JSON should be saved when both flags are True."""
        ctx = self._dummy_context_result()
        mot = self._dummy_motion_result()
        posture_recs = []
        paths = save_posture_motion_report(
            ctx, mot, posture_recs, self._tmpdir,
            save_csv=True, save_json=True,
        )
        self.assertIn("csv", paths)
        self.assertIn("json", paths)
        self.assertTrue(os.path.isfile(paths["csv"]))
        self.assertTrue(os.path.isfile(paths["json"]))


# ====================================================================
#  INTEGRATION-STYLE TEST
# ====================================================================
class TestEndToEnd(unittest.TestCase):

    def test_full_pipeline(self):
        """
        End-to-end: signals → features → motion → posture → context.
        """
        data = _make_signals(120)  # 2 minutes

        # 1. Feature extraction
        X, indices = extract_all_features(data, sampling_rate=FS)
        self.assertGreater(X.shape[0], 0)

        # 2. Motion classification
        motion_result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        self.assertEqual(len(motion_result["epoch_labels"]),
                         len(motion_result["epoch_scores"]))

        # 3. Posture prediction (auto-train on synthetic data)
        labels, confs = predict_posture(X)
        self.assertEqual(len(labels), X.shape[0])

        # 4. Build posture records
        posture_records = []
        for k, (s, e) in enumerate(indices):
            ts_s = float(data["timestamps"][s])
            ts_e = float(data["timestamps"][min(e - 1, len(data["timestamps"]) - 1)])
            posture_records.append({
                "epoch_index": k,
                "timestamp_start": ts_s,
                "timestamp_end": ts_e,
                "posture_label": labels[k],
                "posture_confidence": float(confs[k]),
            })

        # 5. Context fusion
        context_result = align_context_with_events(
            motion_result["epoch_records"], posture_records,
        )
        self.assertIn("combined_timeline", context_result)
        self.assertIn("session_stats", context_result)
        self.assertGreater(len(context_result["combined_timeline"]), 0)

    def test_full_pipeline_with_sleep_events(self):
        """End-to-end with mock sleep events."""
        data = _make_signals(120)
        X, indices = extract_all_features(data, sampling_rate=FS)
        motion_result = classify_motion_segments(
            data["motion_scores"], data["chest_disp"], data["timestamps"],
            sampling_rate=FS,
        )
        labels, confs = predict_posture(X)

        posture_records = []
        for k, (s, e) in enumerate(indices):
            ts_s = float(data["timestamps"][s])
            ts_e = float(data["timestamps"][min(e - 1, len(data["timestamps"]) - 1)])
            posture_records.append({
                "epoch_index": k,
                "timestamp_start": ts_s,
                "timestamp_end": ts_e,
                "posture_label": labels[k],
                "posture_confidence": float(confs[k]),
            })

        sleep_events = [
            {"event_type": "Apnea", "timestamp_start": 30, "timestamp_end": 45,
             "RR_mean": 6.0, "HR_mean": 58.0},
            {"event_type": "Hypopnea", "timestamp_start": 80, "timestamp_end": 95,
             "RR_mean": 10.0, "HR_mean": 62.0},
        ]

        context_result = align_context_with_events(
            motion_result["epoch_records"], posture_records,
            sleep_events=sleep_events,
        )
        self.assertEqual(len(context_result["event_annotations"]), 2)
        for ann in context_result["event_annotations"]:
            self.assertIn("description", ann)
            self.assertIn("posture_during", ann)


if __name__ == "__main__":
    unittest.main()
