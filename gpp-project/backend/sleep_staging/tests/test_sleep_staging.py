"""
tests/test_sleep_staging.py
───────────────────────────
Comprehensive unit tests for the sleep_staging pipeline.

Run:
    cd backend
    python -m pytest sleep_staging/tests/test_sleep_staging.py -v
"""

from __future__ import annotations
import os, sys, json, tempfile, shutil
import unittest
import numpy as np

# ── Ensure package is importable ────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sleep_staging import config as CFG
from sleep_staging.features import (
    epoch_indices,
    _signal_stats,
    _variability_features,
    _motion_features,
    _posture_features,
    _event_features,
    extract_epoch_features,
    extract_all_features,
    FEATURE_DIM,
    FEATURE_NAMES,
)
from sleep_staging.models_classical import build_model, save_model, load_model
from sleep_staging.training import (
    generate_synthetic_sleep_data,
    build_sequences,
    train_classical,
)
from sleep_staging.predict import (
    predict_sleep_stages,
    run_prediction,
    _compute_sleep_structure,
)
from sleep_staging.evaluate import compute_metrics
from sleep_staging.io_utils import save_staging_report


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _synth_signal(n: int, freq: float = 0.25, amp: float = 1.0,
                  offset: float = 0.0, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    t = np.arange(n) / CFG.SAMPLING_RATE
    return offset + amp * np.sin(2 * np.pi * freq * t) + rng.normal(0, 0.05, n)


def _make_data(duration_sec: float = 180.0, sr: float = CFG.SAMPLING_RATE):
    """Create a minimal synthetic data dict (3 min)."""
    n = int(duration_sec * sr)
    ts = np.arange(n) / sr
    return {
        "timestamps":    ts,
        "rr_bpm":        _synth_signal(n, 0.2, 2.0, 15.0, seed=1),
        "hr_bpm":        _synth_signal(n, 0.3, 5.0, 70.0, seed=2),
        "chest_disp":    _synth_signal(n, 0.25, 0.5, 0.0, seed=3),
        "breath_wave":   _synth_signal(n, 0.25, 0.4, 0.0, seed=4),
        "motion_scores": np.abs(_synth_signal(n, 0.1, 0.2, 0.1, seed=5)),
    }


# ════════════════════════════════════════════════════════════════════
#  1.  CONFIG TESTS
# ════════════════════════════════════════════════════════════════════

class TestConfig(unittest.TestCase):
    """Verify constants are sane."""

    def test_stage_labels_reduced_count(self):
        self.assertEqual(len(CFG.STAGE_LABELS_REDUCED), 4)

    def test_stage_labels_full_count(self):
        self.assertEqual(len(CFG.STAGE_LABELS_FULL), 5)

    def test_encoding_keys_match_labels(self):
        self.assertEqual(set(CFG.STAGE_ENCODING_REDUCED.keys()),
                         set(CFG.STAGE_LABELS_REDUCED))

    def test_sampling_rate_positive(self):
        self.assertGreater(CFG.SAMPLING_RATE, 0)

    def test_epoch_duration_positive(self):
        self.assertGreater(CFG.EPOCH_DURATION_SEC, 0)


# ════════════════════════════════════════════════════════════════════
#  2.  EPOCH INDEX TESTS
# ════════════════════════════════════════════════════════════════════

class TestEpochIndices(unittest.TestCase):

    def test_no_overlap_basic(self):
        idx = epoch_indices(600, 200, 0)
        self.assertEqual(len(idx), 3)
        self.assertEqual(idx[0], (0, 200))
        self.assertEqual(idx[-1], (400, 600))

    def test_partial_trailing_epoch_included(self):
        idx = epoch_indices(350, 200, 0)
        # 350 - 200 = 150 > 100 (200//2), so trailing included
        self.assertEqual(len(idx), 2)
        self.assertEqual(idx[1], (200, 350))

    def test_partial_trailing_epoch_skipped(self):
        idx = epoch_indices(250, 200, 0)
        # 250 - 200 = 50 < 100 (200//2), skipped
        self.assertEqual(len(idx), 1)

    def test_overlap(self):
        idx = epoch_indices(600, 200, 100)   # step=100
        # starts: 0, 100, 200, 300, 400
        self.assertEqual(len(idx), 5)

    def test_empty_when_too_short(self):
        idx = epoch_indices(10, 200, 0)
        self.assertEqual(len(idx), 0)


# ════════════════════════════════════════════════════════════════════
#  3.  SIGNAL STATS TESTS
# ════════════════════════════════════════════════════════════════════

class TestSignalStats(unittest.TestCase):

    def test_output_length(self):
        seg = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        out = _signal_stats(seg)
        self.assertEqual(len(out), 10)

    def test_mean_correct(self):
        seg = np.array([2.0, 4.0, 6.0])
        out = _signal_stats(seg)
        self.assertAlmostEqual(out[0], 4.0, places=5)

    def test_std_positive(self):
        seg = np.random.randn(100)
        out = _signal_stats(seg)
        self.assertGreater(out[2], 0)

    def test_zeros_for_short_segment(self):
        out = _signal_stats(np.array([1.0]))
        np.testing.assert_array_equal(out, np.zeros(10))


# ════════════════════════════════════════════════════════════════════
#  4.  VARIABILITY FEATURES TESTS
# ════════════════════════════════════════════════════════════════════

class TestVariabilityFeatures(unittest.TestCase):

    def test_output_length(self):
        seg = np.array([60, 62, 61, 63, 60], dtype=float)
        out = _variability_features(seg)
        self.assertEqual(len(out), 3)

    def test_sdnn_positive(self):
        out = _variability_features(np.random.randn(50) * 5 + 70)
        self.assertGreater(out[0], 0)

    def test_short_segment(self):
        out = _variability_features(np.array([70.0]))
        np.testing.assert_array_equal(out, np.zeros(3))


# ════════════════════════════════════════════════════════════════════
#  5.  MOTION FEATURES TESTS
# ════════════════════════════════════════════════════════════════════

class TestMotionFeatures(unittest.TestCase):

    def test_output_length(self):
        out = _motion_features(np.array([0.1, 0.2, 0.3, 0.6, 0.05]))
        self.assertEqual(len(out), 5)

    def test_fraction_still_range(self):
        out = _motion_features(np.random.rand(100) * 0.05)
        self.assertGreaterEqual(out[4], 0.0)
        self.assertLessEqual(out[4], 1.0)

    def test_spike_count(self):
        # 3 values > 0.5
        seg = np.array([0.1, 0.6, 0.7, 0.2, 0.8])
        out = _motion_features(seg)
        self.assertEqual(out[3], 3)


# ════════════════════════════════════════════════════════════════════
#  6.  POSTURE FEATURES TESTS
# ════════════════════════════════════════════════════════════════════

class TestPostureFeatures(unittest.TestCase):

    def test_no_posture_data(self):
        out = _posture_features(None, 0, None)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], 0.0)
        self.assertEqual(out[1], 1.0)

    def test_stable_posture(self):
        pmap = {0: "supine", 1: "supine", 2: "supine", 3: "supine"}
        out = _posture_features(None, 2, pmap)
        # all same → changes=0, stability=1
        self.assertEqual(out[0], 0.0)
        self.assertEqual(out[1], 1.0)


# ════════════════════════════════════════════════════════════════════
#  7.  EVENT FEATURES TESTS
# ════════════════════════════════════════════════════════════════════

class TestEventFeatures(unittest.TestCase):

    def test_no_events(self):
        out = _event_features(None, 0, 30)
        np.testing.assert_array_equal(out, np.zeros(3))

    def test_event_counting(self):
        evts = [
            {"timestamp_start": 5, "timestamp_end": 10, "event_type": "Irregular"},
            {"timestamp_start": 15, "timestamp_end": 20, "event_type": "Apnea"},
            {"timestamp_start": 50, "timestamp_end": 55, "event_type": "Motion"},
        ]
        out = _event_features(evts, 0, 30)
        self.assertEqual(out[0], 1)   # irregular
        self.assertEqual(out[1], 1)   # apnea
        self.assertEqual(out[2], 0)   # motion outside window


# ════════════════════════════════════════════════════════════════════
#  8.  FEATURE EXTRACTION TESTS
# ════════════════════════════════════════════════════════════════════

class TestFeatureExtraction(unittest.TestCase):

    def test_feature_dim(self):
        self.assertEqual(FEATURE_DIM, 56)

    def test_feature_names_count(self):
        self.assertEqual(len(FEATURE_NAMES), 56)

    def test_single_epoch_vector_shape(self):
        n = 600  # 30 s × 20 Hz
        vec = extract_epoch_features(
            rr_bpm=_synth_signal(n, 0.2, 2.0, 15.0),
            hr_bpm=_synth_signal(n, 0.3, 5.0, 70.0),
            chest_disp=_synth_signal(n, 0.25, 0.5, 0.0),
            breath_wave=_synth_signal(n, 0.25, 0.4, 0.0),
            motion_scores=np.abs(_synth_signal(n, 0.1, 0.2, 0.1)),
            start=0, end=n,
        )
        self.assertEqual(vec.shape, (56,))

    def test_no_nans(self):
        n = 600
        vec = extract_epoch_features(
            rr_bpm=np.random.randn(n) + 15,
            hr_bpm=np.random.randn(n) + 70,
            chest_disp=np.random.randn(n),
            breath_wave=np.random.randn(n),
            motion_scores=np.abs(np.random.randn(n) * 0.1),
            start=0, end=n,
        )
        self.assertFalse(np.any(np.isnan(vec)))

    def test_extract_all_features_shape(self):
        data = _make_data(180)   # 3 min → expect 6 epochs at 30s
        X, indices, centers = extract_all_features(data)
        self.assertEqual(X.shape[1], 56)
        self.assertEqual(len(indices), X.shape[0])
        self.assertEqual(len(centers), X.shape[0])
        self.assertGreaterEqual(X.shape[0], 5)  # at least 5 epochs


# ════════════════════════════════════════════════════════════════════
#  9.  MODEL BUILD TESTS
# ════════════════════════════════════════════════════════════════════

class TestModelBuild(unittest.TestCase):

    def test_build_random_forest(self):
        pipe = build_model("random_forest")
        self.assertEqual(pipe.named_steps["scaler"].__class__.__name__, "StandardScaler")
        self.assertIn("RandomForest", pipe.named_steps["classifier"].__class__.__name__)

    def test_build_svm(self):
        pipe = build_model("svm")
        self.assertIn("SVC", pipe.named_steps["classifier"].__class__.__name__)

    def test_build_xgboost(self):
        pipe = build_model("xgboost")
        self.assertIn("XGB", pipe.named_steps["classifier"].__class__.__name__)

    def test_unknown_model_raises(self):
        with self.assertRaises(ValueError):
            build_model("nonexistent_model")


# ════════════════════════════════════════════════════════════════════
# 10.  SYNTHETIC DATA TESTS
# ════════════════════════════════════════════════════════════════════

class TestSyntheticData(unittest.TestCase):

    def test_shape(self):
        X, y = generate_synthetic_sleep_data(n_per_class=50)
        self.assertEqual(X.shape, (200, 56))  # 50 × 4 classes
        self.assertEqual(len(y), 200)

    def test_balanced_classes(self):
        X, y = generate_synthetic_sleep_data(n_per_class=100)
        unique, counts = np.unique(y, return_counts=True)
        self.assertEqual(len(unique), 4)
        for c in counts:
            self.assertEqual(c, 100)

    def test_full_stages(self):
        X, y = generate_synthetic_sleep_data(n_per_class=30, use_full_stages=True)
        unique = np.unique(y)
        self.assertEqual(len(unique), 5)

    def test_deterministic(self):
        X1, y1 = generate_synthetic_sleep_data(n_per_class=20, seed=99)
        X2, y2 = generate_synthetic_sleep_data(n_per_class=20, seed=99)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)


# ════════════════════════════════════════════════════════════════════
# 11.  SEQUENCE BUILDER TESTS
# ════════════════════════════════════════════════════════════════════

class TestSequenceBuilder(unittest.TestCase):

    def test_output_shape(self):
        X = np.random.randn(50, 56)
        y = np.random.randint(0, 4, 50)
        X_seq, y_seq = build_sequences(X, y, seq_len=10)
        # 50 - 10 + 1 = 41 sequences
        self.assertEqual(X_seq.shape, (41, 10, 56))
        self.assertEqual(len(y_seq), 41)

    def test_short_input_padded(self):
        X = np.random.randn(3, 56)
        y = np.array([0, 1, 2])
        X_seq, y_seq = build_sequences(X, y, seq_len=10)
        self.assertEqual(X_seq.shape[1], 10)
        self.assertEqual(X_seq.shape[2], 56)


# ════════════════════════════════════════════════════════════════════
# 12.  TRAINING TESTS
# ════════════════════════════════════════════════════════════════════

class TestTraining(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Train a fast RF on small synthetic data (run once)."""
        cls.tmpdir = tempfile.mkdtemp(prefix="sleep_staging_test_")
        cls.result = train_classical(
            model_type="random_forest",
            test_size=0.25,
            cv_folds=3,
            seed=42,
            save_path=os.path.join(cls.tmpdir, "test_rf.joblib"),
            n_estimators=30,
            max_depth=8,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_result_keys(self):
        expected = {"model", "model_type", "metrics", "cv_scores",
                    "model_path", "label_names"}
        self.assertTrue(expected.issubset(set(self.result.keys())))

    def test_accuracy_above_chance(self):
        acc = self.result["metrics"]["accuracy"]
        self.assertGreater(acc, 0.30)   # > 25% chance for 4 classes

    def test_cv_scores_present(self):
        cv = self.result["cv_scores"]
        self.assertIn("mean_accuracy", cv)
        self.assertGreater(cv["mean_accuracy"], 0.25)

    def test_model_saved(self):
        self.assertTrue(os.path.isfile(self.result["model_path"]))


# ════════════════════════════════════════════════════════════════════
# 13.  MODEL SAVE / LOAD TESTS
# ════════════════════════════════════════════════════════════════════

class TestModelPersistence(unittest.TestCase):

    def test_save_and_load(self):
        tmpdir = tempfile.mkdtemp(prefix="sleep_staging_persist_")
        try:
            pipe = build_model("random_forest", seed=0, n_estimators=10)
            X, y = generate_synthetic_sleep_data(n_per_class=20)
            pipe.fit(X, y)

            path = os.path.join(tmpdir, "model.joblib")
            save_model(pipe, "random_forest", path=path)
            loaded = load_model("random_forest", path=path)

            preds_orig = pipe.predict(X[:5])
            preds_loaded = loaded.predict(X[:5])
            np.testing.assert_array_equal(preds_orig, preds_loaded)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_model("random_forest", path="/nonexistent/model.joblib")


# ════════════════════════════════════════════════════════════════════
# 14.  PREDICTION TESTS
# ════════════════════════════════════════════════════════════════════

class TestPrediction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="sleep_staging_pred_")
        res = train_classical(
            model_type="random_forest",
            save_path=os.path.join(cls.tmpdir, "rf.joblib"),
            n_estimators=20, max_depth=6,
        )
        cls.model = res["model"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_predict_labels_and_proba(self):
        X, _ = generate_synthetic_sleep_data(n_per_class=10)
        labels, proba = predict_sleep_stages(X, model=self.model)
        self.assertEqual(len(labels), 40)
        self.assertEqual(proba.shape, (40, 4))
        # probabilities sum to 1
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-5)

    def test_labels_are_valid_strings(self):
        X, _ = generate_synthetic_sleep_data(n_per_class=5)
        labels, _ = predict_sleep_stages(X, model=self.model)
        valid = set(CFG.STAGE_LABELS_REDUCED)
        for lbl in labels:
            self.assertIn(lbl, valid)


# ════════════════════════════════════════════════════════════════════
# 15.  RUN PREDICTION PIPELINE TESTS
# ════════════════════════════════════════════════════════════════════

class TestRunPrediction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="sleep_staging_run_")
        res = train_classical(
            model_type="random_forest",
            save_path=os.path.join(cls.tmpdir, "rf.joblib"),
            n_estimators=20, max_depth=6,
        )
        cls.model = res["model"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_full_pipeline(self):
        data = _make_data(180)
        result = run_prediction(data, model=self.model)
        self.assertIn("epoch_records", result)
        self.assertIn("sleep_structure", result)
        self.assertGreater(len(result["epoch_records"]), 0)

    def test_epoch_records_structure(self):
        data = _make_data(120)
        result = run_prediction(data, model=self.model)
        for rec in result["epoch_records"]:
            self.assertIn("epoch_index", rec)
            self.assertIn("predicted_stage", rec)
            self.assertIn("confidence", rec)
            self.assertIn("probabilities", rec)
            self.assertGreater(rec["confidence"], 0)

    def test_empty_data(self):
        data = {
            "timestamps":    np.arange(10) / 20.0,
            "rr_bpm":        np.zeros(10),
            "hr_bpm":        np.zeros(10),
            "chest_disp":    np.zeros(10),
            "breath_wave":   np.zeros(10),
            "motion_scores": np.zeros(10),
        }
        result = run_prediction(data, model=self.model)
        self.assertEqual(len(result["epoch_records"]), 0)


# ════════════════════════════════════════════════════════════════════
# 16.  SLEEP STRUCTURE TESTS
# ════════════════════════════════════════════════════════════════════

class TestSleepStructure(unittest.TestCase):

    def test_all_fields_present(self):
        labels = ["Wake", "Light", "Light", "Deep", "REM", "Light",
                  "Light", "Deep", "REM", "Wake"]
        struct = _compute_sleep_structure(labels, 30.0, CFG.STAGE_LABELS_REDUCED)
        expected_keys = {
            "total_epochs", "total_duration_sec", "total_duration_min",
            "time_per_stage_sec", "pct_per_stage", "stage_counts",
            "sleep_efficiency", "sleep_efficiency_pct", "efficiency_rating",
            "sleep_onset_latency_sec", "rem_episodes",
        }
        self.assertTrue(expected_keys.issubset(set(struct.keys())))

    def test_efficiency_calculation(self):
        # 2 Wake + 8 Sleep = 80% efficiency
        labels = ["Wake", "Wake"] + ["Light"] * 6 + ["Deep", "REM"]
        struct = _compute_sleep_structure(labels, 30.0, CFG.STAGE_LABELS_REDUCED)
        self.assertAlmostEqual(struct["sleep_efficiency"], 0.8, places=2)

    def test_onset_latency(self):
        labels = ["Wake", "Wake", "Wake", "Light", "Deep", "REM"]
        struct = _compute_sleep_structure(labels, 30.0, CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(struct["sleep_onset_latency_sec"], 90.0)

    def test_rem_episodes_count(self):
        labels = ["Light", "REM", "REM", "Light", "REM", "Light"]
        struct = _compute_sleep_structure(labels, 30.0, CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(struct["rem_episodes"], 2)

    def test_all_wake(self):
        labels = ["Wake"] * 10
        struct = _compute_sleep_structure(labels, 30.0, CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(struct["sleep_efficiency"], 0.0)
        self.assertEqual(struct["efficiency_rating"], "Poor")

    def test_perfect_sleep(self):
        labels = ["Deep"] * 20
        struct = _compute_sleep_structure(labels, 30.0, CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(struct["sleep_efficiency"], 1.0)
        self.assertEqual(struct["efficiency_rating"], "Good")


# ════════════════════════════════════════════════════════════════════
# 17.  EVALUATION METRICS TESTS
# ════════════════════════════════════════════════════════════════════

class TestEvaluation(unittest.TestCase):

    def test_perfect_predictions(self):
        y_true = np.array([0, 1, 2, 3, 0, 1, 2, 3])
        y_pred = np.array([0, 1, 2, 3, 0, 1, 2, 3])
        m = compute_metrics(y_true, y_pred, label_names=CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(m["accuracy"], 1.0)
        self.assertEqual(m["f1_macro"], 1.0)
        self.assertEqual(m["cohens_kappa"], 1.0)

    def test_random_predictions_low_kappa(self):
        rng = np.random.RandomState(42)
        y_true = rng.randint(0, 4, 200)
        y_pred = rng.randint(0, 4, 200)
        m = compute_metrics(y_true, y_pred, label_names=CFG.STAGE_LABELS_REDUCED)
        self.assertLess(m["cohens_kappa"], 0.3)

    def test_per_class_f1(self):
        y_true = np.array([0, 0, 1, 1, 2, 2, 3, 3])
        y_pred = np.array([0, 0, 1, 1, 2, 2, 3, 3])
        m = compute_metrics(y_true, y_pred, label_names=CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(len(m["per_class_f1"]), 4)

    def test_confusion_matrix_shape(self):
        y_true = np.array([0, 1, 2, 3, 0, 1])
        y_pred = np.array([0, 1, 2, 3, 1, 0])
        m = compute_metrics(y_true, y_pred, label_names=CFG.STAGE_LABELS_REDUCED)
        self.assertEqual(len(m["confusion_matrix"]), 4)

    def test_roc_auc_with_proba(self):
        y_true = np.array([0, 0, 1, 1, 2, 2, 3, 3])
        y_proba = np.eye(4)[[0, 0, 1, 1, 2, 2, 3, 3]]  # perfect proba
        m = compute_metrics(y_true, y_true, y_proba,
                            label_names=CFG.STAGE_LABELS_REDUCED)
        self.assertIsNotNone(m["roc_auc_macro"])
        self.assertAlmostEqual(m["roc_auc_macro"], 1.0, places=2)


# ════════════════════════════════════════════════════════════════════
# 18.  IO / REPORT TESTS
# ════════════════════════════════════════════════════════════════════

class TestIOReport(unittest.TestCase):

    def test_save_report(self):
        tmpdir = tempfile.mkdtemp(prefix="sleep_staging_io_")
        try:
            records = [
                {"epoch_index": 0, "predicted_stage": "Light",
                 "confidence": 0.85, "probabilities": {"Wake": 0.05, "REM": 0.05,
                                                        "Light": 0.85, "Deep": 0.05}},
            ]
            structure = {
                "total_epochs": 1,
                "total_duration_sec": 30,
                "sleep_efficiency": 1.0,
            }
            metrics = {"accuracy": 0.9, "f1_macro": 0.88}
            pred_result = {
                "epoch_records": records,
                "sleep_structure": structure,
            }

            paths = save_staging_report(
                pred_result, metrics, output_dir=tmpdir,
            )
            self.assertTrue(os.path.isfile(paths["csv"]))
            self.assertTrue(os.path.isfile(paths["json"]))

            with open(paths["json"]) as f:
                j = json.load(f)
            self.assertIn("sleep_structure", j)
            self.assertIn("metrics", j)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
# 19.  END-TO-END INTEGRATION TEST
# ════════════════════════════════════════════════════════════════════

class TestEndToEnd(unittest.TestCase):
    """
    Full flow: synthetic train → predict on signal data → sleep
    structure → metrics → save report.
    """

    def test_full_flow(self):
        tmpdir = tempfile.mkdtemp(prefix="sleep_staging_e2e_")
        try:
            # 1. Train
            res = train_classical(
                model_type="random_forest",
                save_path=os.path.join(tmpdir, "rf.joblib"),
                n_estimators=20, max_depth=6,
            )
            model = res["model"]
            self.assertGreater(res["metrics"]["accuracy"], 0.3)

            # 2. Predict on synthetic signal data
            data = _make_data(300)  # 5 min → ~10 epochs
            pred = run_prediction(data, model=model)
            self.assertGreater(len(pred["epoch_records"]), 0)

            # 3. Sleep structure present
            ss = pred["sleep_structure"]
            self.assertIn("sleep_efficiency", ss)
            self.assertIn("efficiency_rating", ss)

            # 4. Save report
            paths = save_staging_report(
                pred, res["metrics"],
                output_dir=tmpdir,
            )
            self.assertTrue(os.path.isfile(paths["csv"]))
            self.assertTrue(os.path.isfile(paths["json"]))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    unittest.main()
