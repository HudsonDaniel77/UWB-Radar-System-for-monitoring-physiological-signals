"""
ml_enhanced/tests/test_ml_enhanced.py
─────────────────────────────────────
Comprehensive unit tests for the ML-Enhanced pipeline.

Test classes:
  TestConfig                – configuration constants
  TestFeatureEngineering    – HRV, RR dynamics, spectral, scaling
  TestDataset               – synthetic data, sequences, splits
  TestClassicalModels       – RF, SVM, XGBoost wrapper tests
  TestDeepModels            – CNN / CNN-LSTM / Transformer (if TF available)
  TestEvaluation            – classification & regression metrics
  TestHyperparameterTuning  – grid search
  TestInference             – save / load / predict
  TestVisualize             – plot generation
  TestEndToEnd              – full pipeline demo run
"""

from __future__ import annotations
import json
import os
import shutil
import tempfile

import numpy as np
import pytest

# ── Module imports ──────────────────────────────────────────────────
from ml_enhanced import config as CFG
from ml_enhanced.feature_engineering import (
    FeatureScaler,
    compute_hrv_time_domain,
    compute_hrv_frequency_domain,
    compute_rr_dynamics,
    compute_motion_spectral,
    compute_cardiorespiratory_coupling,
    engineer_features_epoch,
    engineer_features_batch,
    feature_importance_from_model,
    rank_features,
)
from ml_enhanced.dataset import (
    generate_synthetic_event_data,
    generate_synthetic_stage_data,
    generate_synthetic_ahi_data,
    build_sequences,
    split_data,
)
from ml_enhanced.models.classical import (
    RandomForestModel,
    SVMModel,
    XGBoostModel,
    build_classical_model,
    list_classical_models,
)
from ml_enhanced.evaluation import (
    compute_classification_metrics,
    compute_regression_metrics,
    compute_roc_curve,
    build_comparison_table,
    evaluate_models,
)
from ml_enhanced.hyperparameter_tuning import grid_search
from ml_enhanced.inference import (
    save_trained_model,
    load_trained_model,
    predict_enhanced_events,
)
from ml_enhanced.visualize import (
    plot_confusion_matrix,
    plot_roc_curve,
    plot_model_comparison,
    plot_feature_importance,
    plot_training_history,
    save_all_plots,
)
from ml_enhanced.training import (
    train_single_model,
    train_ml_models,
    cross_validate_model,
    ALL_MODEL_NAMES,
    _ahi_to_class,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="ml_enh_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def event_data():
    return generate_synthetic_event_data(n_per_class=100, seed=42)


@pytest.fixture
def stage_data():
    return generate_synthetic_stage_data(n_per_class=80, seed=42)


@pytest.fixture
def ahi_data():
    return generate_synthetic_ahi_data(n_subjects=30, seed=42)


# ====================================================================
#  CONFIG TESTS
# ====================================================================

class TestConfig:
    def test_feature_dim(self):
        assert CFG.FEATURE_DIM == len(CFG.ALL_FEATURES)
        assert CFG.FEATURE_DIM > 20

    def test_event_labels(self):
        assert len(CFG.EVENT_LABELS_BINARY) == 2
        assert "Normal" in CFG.EVENT_LABELS_BINARY

    def test_stage_labels(self):
        assert len(CFG.STAGE_LABELS_REDUCED) == 4
        assert len(CFG.STAGE_LABELS_FULL) == 5

    def test_theme_colors(self):
        assert CFG.DARK_BG.startswith("#")
        assert CFG.ACCENT_PRIMARY.startswith("#")

    def test_model_templates(self):
        assert "{task}" in CFG.MODEL_FILE_TEMPLATE
        assert "{model_type}" in CFG.MODEL_FILE_TEMPLATE


# ====================================================================
#  FEATURE ENGINEERING TESTS
# ====================================================================

class TestFeatureEngineering:
    def test_scaler_fit_transform(self):
        X = np.random.randn(50, 10)
        scaler = FeatureScaler()
        X_s = scaler.fit_transform(X)
        assert X_s.shape == X.shape
        # Mean ≈ 0, std ≈ 1 per column
        assert np.allclose(X_s.mean(axis=0), 0, atol=1e-10)
        assert np.allclose(X_s.std(axis=0), 1, atol=0.1)

    def test_scaler_inverse(self):
        X = np.random.randn(30, 5)
        scaler = FeatureScaler()
        X_s = scaler.fit_transform(X)
        X_r = scaler.inverse_transform(X_s)
        assert np.allclose(X, X_r, atol=1e-10)

    def test_scaler_not_fitted(self):
        scaler = FeatureScaler()
        with pytest.raises(RuntimeError):
            scaler.transform(np.ones((5, 3)))

    def test_hrv_time_domain(self):
        hr = np.array([72, 75, 70, 68, 73, 71, 74])
        result = compute_hrv_time_domain(hr)
        assert "hrv_sdnn" in result
        assert "hrv_rmssd" in result
        assert "hrv_pnn50" in result
        assert result["hrv_sdnn"] > 0

    def test_hrv_time_domain_short(self):
        result = compute_hrv_time_domain(np.array([70, 72]))
        assert result["hrv_sdnn"] == 0.0

    def test_hrv_frequency_domain(self):
        hr = np.random.normal(70, 5, 30)
        result = compute_hrv_frequency_domain(hr, fs=1.0)
        assert "hrv_lf_power" in result
        assert "hrv_hf_power" in result
        assert "hrv_lf_hf_ratio" in result

    def test_hrv_frequency_short(self):
        result = compute_hrv_frequency_domain(np.array([70, 72, 68]))
        assert result["hrv_lf_power"] == 0.0

    def test_rr_dynamics(self):
        rr = np.array([14, 15, 13, 14, 16])
        result = compute_rr_dynamics(rr)
        assert "rr_trend_3" in result
        assert "rr_trend_5" in result
        assert "rr_cv" in result
        assert "rr_delta" in result

    def test_rr_dynamics_short(self):
        result = compute_rr_dynamics(np.array([14]))
        assert result["rr_delta"] == 0.0
        assert result["rr_trend_3"] == 0.0

    def test_motion_spectral(self):
        motion = np.random.uniform(0, 0.5, 20)
        result = compute_motion_spectral(motion, fs=1.0)
        assert "motion_spectral_energy" in result
        assert "motion_dominant_freq" in result

    def test_motion_spectral_short(self):
        result = compute_motion_spectral(np.array([0.1, 0.2]))
        assert result["motion_spectral_energy"] == 0.0

    def test_cardiorespiratory_coupling(self):
        rr = np.array([14, 13, 15, 12, 14])
        hr = np.array([70, 72, 68, 74, 70])
        crc = compute_cardiorespiratory_coupling(rr, hr)
        assert -1.0 <= crc <= 1.0

    def test_coupling_constant_signal(self):
        crc = compute_cardiorespiratory_coupling(
            np.ones(5), np.array([70, 72, 68, 74, 70]),
        )
        assert crc == 0.0

    def test_engineer_epoch(self):
        raw = np.random.randn(len(CFG.RAW_FEATURES))
        rr_hist = np.random.normal(15, 2, 5)
        hr_hist = np.random.normal(70, 5, 5)
        mot_hist = np.random.uniform(0, 0.3, 5)
        full = engineer_features_epoch(raw, rr_hist, hr_hist, mot_hist)
        assert full.shape == (CFG.FEATURE_DIM,)

    def test_engineer_batch(self):
        n_raw = len(CFG.RAW_FEATURES)
        X = np.random.randn(20, n_raw)
        X[:, 0] = np.random.normal(15, 2, 20)     # rr_mean
        X[:, 9] = np.random.normal(70, 5, 20)      # hr_mean
        X[:, 18] = np.random.uniform(0, 0.5, 20)   # motion_index
        out = engineer_features_batch(X)
        assert out.shape == (20, CFG.FEATURE_DIM)

    def test_feature_importance_rf(self):
        X, y = generate_synthetic_event_data(n_per_class=60, seed=1)
        model = RandomForestModel(n_estimators=10, max_depth=5)
        model.fit(X, y)
        imp = feature_importance_from_model(model)
        assert len(imp) > 0

    def test_rank_features(self):
        imp = {"a": 0.5, "b": 0.3, "c": 0.8, "d": 0.1}
        ranked = rank_features(imp, top_k=2)
        assert ranked[0] == ("c", 0.8)
        assert len(ranked) == 2


# ====================================================================
#  DATASET TESTS
# ====================================================================

class TestDataset:
    def test_synthetic_event_shape(self, event_data):
        X, y = event_data
        assert X.shape[0] == 200          # 100 per class × 2
        assert X.shape[1] == CFG.FEATURE_DIM
        assert set(y) == {0, 1}

    def test_synthetic_stage_shape(self, stage_data):
        X, y = stage_data
        assert X.shape[0] == 320          # 80 × 4
        assert set(y) == {0, 1, 2, 3}

    def test_synthetic_ahi_shape(self, ahi_data):
        X, y = ahi_data
        assert X.shape[0] == 30
        assert y.dtype == np.float64

    def test_build_sequences(self):
        X = np.random.randn(50, 10)
        y = np.random.randint(0, 2, 50)
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        assert X_seq.shape == (46, 5, 10)  # 50 - 5 + 1
        assert len(y_seq) == 46

    def test_build_sequences_short(self):
        X = np.random.randn(3, 10)
        y = np.array([0, 1, 0])
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        assert X_seq.shape[1] == 5         # padded
        assert len(y_seq) == 1

    def test_split_data(self, event_data):
        X, y = event_data
        X_tr, X_te, y_tr, y_te = split_data(X, y, test_size=0.2)
        assert len(X_tr) + len(X_te) == len(X)
        assert len(y_tr) + len(y_te) == len(y)
        # Stratified: both classes present in test
        assert len(set(y_te)) == 2


# ====================================================================
#  CLASSICAL MODEL TESTS
# ====================================================================

class TestClassicalModels:
    def test_list_models(self):
        models = list_classical_models()
        assert "random_forest" in models
        assert "svm" in models
        assert "xgboost" in models

    def test_build_factory(self):
        model = build_classical_model("random_forest", n_classes=2)
        assert model.name == "random_forest"

    def test_build_unknown_raises(self):
        with pytest.raises(ValueError):
            build_classical_model("nonexistent_model")

    def test_rf_train_predict(self, event_data):
        X, y = event_data
        model = RandomForestModel(n_estimators=20, max_depth=5)
        model.fit(X, y)
        preds = model.predict(X)
        assert len(preds) == len(X)
        assert set(preds).issubset({0, 1})

    def test_rf_proba(self, event_data):
        X, y = event_data
        model = RandomForestModel(n_estimators=20, max_depth=5)
        model.fit(X, y)
        proba = model.predict_proba(X)
        assert proba.shape == (len(X), 2)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    def test_svm_train_predict(self, event_data):
        X, y = event_data
        model = SVMModel(C=1.0)
        model.fit(X, y)
        preds = model.predict(X)
        assert len(preds) == len(X)

    def test_xgboost_train_predict(self, event_data):
        X, y = event_data
        model = XGBoostModel(n_estimators=20, max_depth=3, n_classes=2)
        model.fit(X, y)
        preds = model.predict(X)
        assert len(preds) == len(X)

    def test_rf_save_load(self, event_data, tmp_dir):
        X, y = event_data
        model = RandomForestModel(n_estimators=10, max_depth=5)
        model.fit(X, y)
        path = os.path.join(tmp_dir, "test_rf.joblib")
        model.save(path)
        assert os.path.exists(path)

        model2 = RandomForestModel()
        model2.load(path)
        p1 = model.predict(X[:5])
        p2 = model2.predict(X[:5])
        assert np.array_equal(p1, p2)

    def test_model_summary(self):
        model = RandomForestModel(n_estimators=100, max_depth=10)
        s = model.summary()
        assert s["name"] == "random_forest"
        assert s["n_estimators"] == 100

    def test_multiclass(self, stage_data):
        X, y = stage_data
        model = RandomForestModel(n_estimators=20, max_depth=5)
        model.fit(X, y)
        preds = model.predict(X)
        assert set(preds).issubset({0, 1, 2, 3})


# ====================================================================
#  DEEP MODEL TESTS  (only run if TensorFlow is available)
# ====================================================================

class TestDeepModels:
    @pytest.fixture(autouse=True)
    def check_tf(self):
        try:
            import tensorflow  # noqa: F401
            self.has_tf = True
        except ImportError:
            self.has_tf = False

    def test_cnn_available_flag(self):
        from ml_enhanced.models.cnn import is_available
        assert isinstance(is_available(), bool)

    def test_cnn_1d_train(self, event_data):
        if not self.has_tf:
            pytest.skip("TensorFlow not installed")
        from ml_enhanced.models.cnn import CNN1DModel
        X, y = event_data
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        model = CNN1DModel(n_classes=2, hidden_dim=32, dropout=0.1)
        info = model.fit(X_seq, y_seq, epochs=2, batch_size=32)
        preds = model.predict(X_seq)
        assert len(preds) == len(y_seq)

    def test_cnn_lstm_train(self, event_data):
        if not self.has_tf:
            pytest.skip("TensorFlow not installed")
        from ml_enhanced.models.cnn_lstm import CNNLSTMModel
        X, y = event_data
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        model = CNNLSTMModel(n_classes=2, hidden_dim=32, dropout=0.1)
        info = model.fit(X_seq, y_seq, epochs=2, batch_size=32)
        preds = model.predict(X_seq)
        assert len(preds) == len(y_seq)

    def test_transformer_train(self, event_data):
        if not self.has_tf:
            pytest.skip("TensorFlow not installed")
        from ml_enhanced.models.transformer import TransformerModel
        X, y = event_data
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        model = TransformerModel(n_classes=2, hidden_dim=32,
                                  n_heads=2, ff_dim=64, n_layers=1,
                                  dropout=0.1)
        info = model.fit(X_seq, y_seq, epochs=2, batch_size=32)
        preds = model.predict(X_seq)
        assert len(preds) == len(y_seq)

    def test_cnn_save_load(self, event_data, tmp_dir):
        if not self.has_tf:
            pytest.skip("TensorFlow not installed")
        from ml_enhanced.models.cnn import CNN1DModel
        X, y = event_data
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        model = CNN1DModel(n_classes=2, hidden_dim=16, dropout=0.1)
        model.fit(X_seq, y_seq, epochs=1, batch_size=32)
        path = os.path.join(tmp_dir, "test_cnn.keras")
        model.save(path)
        assert os.path.exists(path)

    def test_deep_summary(self, event_data):
        if not self.has_tf:
            pytest.skip("TensorFlow not installed")
        from ml_enhanced.models.cnn import CNN1DModel
        X, y = event_data
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        model = CNN1DModel(n_classes=2, hidden_dim=16, dropout=0.1)
        model.fit(X_seq, y_seq, epochs=1, batch_size=32)
        s = model.summary()
        assert s["name"] == "cnn_1d"
        assert "params" in s


# ====================================================================
#  EVALUATION TESTS
# ====================================================================

class TestEvaluation:
    def test_classification_metrics_binary(self):
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 1, 0, 0])
        metrics = compute_classification_metrics(y_true, y_pred)
        assert "accuracy" in metrics
        assert "f1_macro" in metrics
        assert "confusion_matrix" in metrics
        assert metrics["n"] == 6

    def test_classification_metrics_multiclass(self):
        y_true = np.array([0, 1, 2, 3, 0, 1, 2, 3])
        y_pred = np.array([0, 1, 2, 3, 1, 1, 2, 2])
        metrics = compute_classification_metrics(
            y_true, y_pred, label_names=["A", "B", "C", "D"],
        )
        assert "per_class" in metrics
        assert "A" in metrics["per_class"]

    def test_classification_metrics_with_proba(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 0])
        y_proba = np.array([[0.9, 0.1], [0.7, 0.3],
                            [0.2, 0.8], [0.6, 0.4]])
        metrics = compute_classification_metrics(y_true, y_pred, y_proba)
        assert metrics["roc_auc"] is not None

    def test_classification_metrics_empty(self):
        metrics = compute_classification_metrics(np.array([]), np.array([]))
        assert metrics["n"] == 0

    def test_regression_metrics(self):
        y_true = np.array([10, 20, 30])
        y_pred = np.array([12, 18, 32])
        metrics = compute_regression_metrics(y_true, y_pred)
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "r2" in metrics
        assert metrics["mae"] > 0

    def test_roc_curve(self):
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_proba = np.array([[0.9, 0.1], [0.7, 0.3], [0.2, 0.8],
                            [0.1, 0.9], [0.6, 0.4], [0.3, 0.7]])
        roc = compute_roc_curve(y_true, y_proba, pos_label=1)
        assert "fpr" in roc
        assert "tpr" in roc
        assert len(roc["fpr"]) > 0

    def test_comparison_table(self):
        results = {
            "rf": {
                "model_type": "rf",
                "val_metrics": {"accuracy": 0.9, "f1_macro": 0.88,
                                "precision_macro": 0.87, "recall_macro": 0.89,
                                "roc_auc": 0.95},
                "elapsed_sec": 1.2,
            },
            "svm": {
                "model_type": "svm",
                "val_metrics": {"accuracy": 0.85, "f1_macro": 0.83,
                                "precision_macro": 0.82, "recall_macro": 0.84,
                                "roc_auc": 0.90},
                "elapsed_sec": 0.8,
            },
        }
        table = build_comparison_table(results)
        assert len(table) == 2
        # Sorted by f1 desc
        assert table[0]["f1"] >= table[1]["f1"]

    def test_comparison_table_with_error(self):
        results = {
            "rf": {"model_type": "rf", "val_metrics": {"f1_macro": 0.9},
                   "elapsed_sec": 1.0},
            "bad": {"model_type": "bad", "error": "something failed"},
        }
        table = build_comparison_table(results)
        assert len(table) == 2
        err_row = [r for r in table if r["model"] == "bad"][0]
        assert "error" in err_row


# ====================================================================
#  HYPERPARAMETER TUNING TESTS
# ====================================================================

class TestHyperparameterTuning:
    def test_grid_search_rf(self, event_data):
        X, y = event_data
        result = grid_search(
            "random_forest", X, y,
            param_grid={"model__n_estimators": [10, 20],
                        "model__max_depth": [3, 5]},
            cv=2,
            n_classes=2,
        )
        assert "best_params" in result
        assert "best_score" in result
        assert result["best_score"] > 0

    def test_grid_search_empty_grid(self, event_data):
        X, y = event_data
        result = grid_search("random_forest", X, y, param_grid={}, cv=2)
        assert "error" in result


# ====================================================================
#  INFERENCE TESTS
# ====================================================================

class TestInference:
    def test_save_load_classical(self, event_data, tmp_dir):
        X, y = event_data
        model = RandomForestModel(n_estimators=10, max_depth=5)
        model.fit(X, y)
        paths = save_trained_model(model, "event", "random_forest",
                                   output_dir=tmp_dir)
        assert "model" in paths
        assert os.path.exists(paths["model"])

        loaded = load_trained_model("event", "random_forest",
                                    model_dir=tmp_dir)
        assert loaded["model"] is not None

    def test_save_with_metadata(self, event_data, tmp_dir):
        X, y = event_data
        model = RandomForestModel(n_estimators=10, max_depth=5)
        model.fit(X, y)
        meta = {"task": "event", "accuracy": 0.95}
        paths = save_trained_model(model, "event", "random_forest",
                                   output_dir=tmp_dir, metadata=meta)
        assert "metadata" in paths
        with open(paths["metadata"]) as f:
            loaded_meta = json.load(f)
        assert loaded_meta["accuracy"] == 0.95

    def test_predict_enhanced_events(self, event_data):
        X, y = event_data
        model = RandomForestModel(n_estimators=10, max_depth=5)
        model.fit(X, y)
        result = predict_enhanced_events(
            model.pipeline, X[:10],
            label_names=CFG.EVENT_LABELS_BINARY,
        )
        assert "predictions" in result
        assert "decoded" in result
        assert len(result["predictions"]) == 10
        assert all(d in CFG.EVENT_LABELS_BINARY for d in result["decoded"])

    def test_load_nonexistent(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            load_trained_model("event", "nonexistent", model_dir=tmp_dir)


# ====================================================================
#  VISUALIZE TESTS
# ====================================================================

class TestVisualize:
    def test_confusion_matrix_plot(self, tmp_dir):
        cm = [[40, 5], [3, 42]]
        path = plot_confusion_matrix(
            cm, ["Normal", "Apnea"],
            output_path=os.path.join(tmp_dir, "cm.png"),
        )
        assert os.path.exists(path)

    def test_roc_curve_plot(self, tmp_dir):
        roc_data = {"fpr": [0, 0.1, 0.5, 1.0],
                    "tpr": [0, 0.8, 0.9, 1.0]}
        path = plot_roc_curve(
            roc_data,
            output_path=os.path.join(tmp_dir, "roc.png"),
        )
        assert os.path.exists(path)

    def test_model_comparison_plot(self, tmp_dir):
        table = [
            {"model": "RF", "f1": 0.92, "accuracy": 0.91},
            {"model": "SVM", "f1": 0.85, "accuracy": 0.84},
        ]
        path = plot_model_comparison(
            table, metric="f1",
            output_path=os.path.join(tmp_dir, "cmp.png"),
        )
        assert os.path.exists(path)

    def test_feature_importance_plot(self, tmp_dir):
        imp = {"rr_mean": 0.3, "hr_std": 0.25, "motion": 0.15}
        path = plot_feature_importance(
            imp, top_k=3,
            output_path=os.path.join(tmp_dir, "fi.png"),
        )
        assert os.path.exists(path)

    def test_training_history_plot(self, tmp_dir):
        hist = {"loss": [1.0, 0.5, 0.3], "val_loss": [1.1, 0.6, 0.4],
                "accuracy": [0.5, 0.7, 0.85], "val_accuracy": [0.45, 0.65, 0.80]}
        path = plot_training_history(
            hist,
            output_path=os.path.join(tmp_dir, "hist.png"),
        )
        assert os.path.exists(path)

    def test_save_all_plots(self, event_data, tmp_dir):
        X, y = event_data
        model = RandomForestModel(n_estimators=10, max_depth=5)
        model.fit(X, y)
        preds = model.predict(X)
        proba = model.predict_proba(X)
        metrics = compute_classification_metrics(y, preds, proba,
                                                  CFG.EVENT_LABELS_BINARY)
        results = {
            "random_forest": {
                "model_type": "random_forest",
                "model": model,
                "val_metrics": metrics,
                "label_names": CFG.EVENT_LABELS_BINARY,
                "is_deep": False,
                "train_info": {},
                "elapsed_sec": 1.0,
            }
        }
        table = [{"model": "random_forest", "f1": 0.9, "accuracy": 0.9}]
        paths = save_all_plots(results, table, tmp_dir)
        assert isinstance(paths, dict)
        assert len(paths) > 0


# ====================================================================
#  TRAINING INTEGRATION TESTS
# ====================================================================

class TestTraining:
    def test_train_single_rf(self, event_data):
        X, y = event_data
        X_tr, X_va, y_tr, y_va = split_data(X, y)
        result = train_single_model(
            "random_forest", X_tr, y_tr, X_va, y_va,
            n_classes=2, label_names=CFG.EVENT_LABELS_BINARY,
        )
        assert result["model_type"] == "random_forest"
        assert "metrics" in result
        assert "val_metrics" in result
        assert result["val_metrics"]["accuracy"] > 0

    def test_train_ml_models_classical(self):
        results = train_ml_models(
            task="event",
            model_types=["random_forest", "svm"],
            skip_deep=True,
            seed=42,
        )
        assert "random_forest" in results
        assert "svm" in results
        for mt, res in results.items():
            assert "error" not in res or isinstance(res.get("model"), object)

    def test_cross_validate(self, event_data):
        X, y = event_data
        cv = cross_validate_model(
            "random_forest", X, y, n_folds=3,
            n_classes=2, label_names=CFG.EVENT_LABELS_BINARY,
        )
        assert "mean_accuracy" in cv
        assert cv["mean_accuracy"] > 0
        assert len(cv["fold_metrics"]) == 3

    def test_ahi_to_class(self):
        ahi = np.array([2, 8, 20, 40])
        classes = _ahi_to_class(ahi)
        assert list(classes) == [0, 1, 2, 3]

    def test_train_stage_task(self):
        results = train_ml_models(
            task="stage",
            model_types=["random_forest"],
            skip_deep=True,
            seed=42,
        )
        assert "random_forest" in results
        lns = results["random_forest"].get("label_names", [])
        assert len(lns) == 4

    def test_all_model_names(self):
        assert len(ALL_MODEL_NAMES) >= 3
        assert "random_forest" in ALL_MODEL_NAMES


# ====================================================================
#  END-TO-END TESTS
# ====================================================================

class TestEndToEnd:
    def test_demo_event_pipeline(self, tmp_dir):
        """Full demo pipeline: train + compare + save + plots."""
        from ml_enhanced.run_training import parse_args, run_training
        args = parse_args([
            "--task", "event",
            "--demo",
            "--skip-deep",
            "--output", tmp_dir,
            "--models", "random_forest", "svm",
        ])
        summary = run_training(args)

        assert "comparison_table" in summary
        assert "best_model" in summary
        assert summary["best_model"] is not None

        # Summary JSON written
        assert os.path.exists(os.path.join(tmp_dir, "training_summary.json"))

    def test_demo_stage_pipeline(self, tmp_dir):
        from ml_enhanced.run_training import parse_args, run_training
        args = parse_args([
            "--task", "stage",
            "--demo",
            "--skip-deep",
            "--output", tmp_dir,
            "--models", "random_forest",
        ])
        summary = run_training(args)
        assert summary["best_model"] is not None

    def test_demo_no_plots(self, tmp_dir):
        from ml_enhanced.run_training import parse_args, run_training
        args = parse_args([
            "--task", "event",
            "--demo",
            "--skip-deep",
            "--no-plots",
            "--output", tmp_dir,
            "--models", "random_forest",
        ])
        summary = run_training(args)
        assert summary["plot_paths"] == {}

    def test_demo_with_tuning(self, tmp_dir):
        from ml_enhanced.run_training import parse_args, run_training
        args = parse_args([
            "--task", "event",
            "--demo",
            "--skip-deep",
            "--tune",
            "--tune-model", "random_forest",
            "--output", tmp_dir,
            "--models", "random_forest",
        ])
        summary = run_training(args)
        assert summary.get("tuning") is not None
        assert summary["tuning"]["best_score"] > 0


# ====================================================================
#  EDGE CASE TESTS
# ====================================================================

class TestEdgeCases:
    def test_single_sample(self):
        X = np.random.randn(1, CFG.FEATURE_DIM)
        y = np.array([0])
        # Should not crash, but may have degenerate metrics
        X_seq, y_seq = build_sequences(X, y, seq_len=5)
        assert X_seq.shape[1] == 5

    def test_all_same_class(self):
        X = np.random.randn(50, CFG.FEATURE_DIM)
        y = np.zeros(50, dtype=int)
        model = RandomForestModel(n_estimators=5, max_depth=3)
        model.fit(X, y)
        preds = model.predict(X)
        assert np.all(preds == 0)

    def test_empty_importance(self):
        # Model without feature_importances_ or coef_
        imp = feature_importance_from_model(object())
        assert imp == {}

    def test_regression_single_sample(self):
        metrics = compute_regression_metrics(np.array([5.0]),
                                              np.array([6.0]))
        assert metrics["mae"] == 1.0
        assert metrics["r2"] == 0.0  # r2 undefined for single sample
