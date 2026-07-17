"""
tests/test_validation.py
────────────────────────
Comprehensive unit tests for the validation & benchmarking pipeline.

Run:
    cd backend
    python -m pytest validation/tests/test_validation.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import numpy as np
import pytest

# ── make validation package importable ──────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, BACKEND_DIR)

from validation import config as CFG
from validation.io_utils import (
    _normalise_event_type,
    save_validation_report,
    load_psg_events_csv,
    load_psg_events_json,
    load_psg_stages_csv,
    load_system_events_json,
    load_system_stages_json,
    load_psg_ahi_csv,
)
from validation.event_metrics import (
    match_events,
    compute_event_metrics,
    compute_epoch_metrics,
    _overlap_iou,
    _event_midpoint,
    _event_duration,
)
from validation.ahi import (
    compute_ahi,
    classify_ahi_severity,
    compare_ahi,
    screening_performance,
)
from validation.agreement import (
    bland_altman,
    compute_icc,
    build_confusion_matrix,
    cohens_kappa,
)
from validation.staging_validation import (
    validate_stages,
    stage_transition_agreement,
)
from validation.threshold_optimization import (
    ahi_roc_curve,
    optimize_event_confidence_threshold,
    multi_cutoff_screening,
)
from validation.visualize import save_all_plots
from validation.reporting import report_validation_results


# ====================================================================
#  FIXTURES
# ====================================================================

@pytest.fixture
def psg_events():
    """PSG reference events with timestamp_start / timestamp_end."""
    return [
        {"timestamp_start": 10.0, "timestamp_end": 25.0, "event_type": "Apnea"},
        {"timestamp_start": 60.0, "timestamp_end": 80.0, "event_type": "Hypopnea"},
        {"timestamp_start": 120.0, "timestamp_end": 140.0, "event_type": "Apnea"},
        {"timestamp_start": 200.0, "timestamp_end": 220.0, "event_type": "Irregular"},
        {"timestamp_start": 300.0, "timestamp_end": 315.0, "event_type": "Apnea"},
    ]


@pytest.fixture
def sys_events():
    """System-predicted events."""
    return [
        # matches psg[0] with slight jitter
        {"timestamp_start": 11.0, "timestamp_end": 26.0, "event_type": "Apnea", "confidence": 0.9},
        # matches psg[1]
        {"timestamp_start": 61.0, "timestamp_end": 78.0, "event_type": "Hypopnea", "confidence": 0.85},
        # matches psg[2]
        {"timestamp_start": 122.0, "timestamp_end": 138.0, "event_type": "Apnea", "confidence": 0.7},
        # false positive
        {"timestamp_start": 170.0, "timestamp_end": 185.0, "event_type": "Apnea", "confidence": 0.4},
        # psg[3] (Irregular) missed, psg[4] missed
    ]


@pytest.fixture
def stage_labels():
    """120 epochs of stages."""
    np.random.seed(99)
    labels = ["Wake", "Light", "Deep", "REM"]
    ref = np.random.choice(labels, 120).tolist()
    pred = []
    for s in ref:
        if np.random.rand() < 0.75:
            pred.append(s)
        else:
            pred.append(np.random.choice(labels))
    return ref, pred


@pytest.fixture
def subjects_data():
    """Multi-subject dicts with system_ahi and psg_ahi."""
    np.random.seed(7)
    psg = np.array([2.0, 7.5, 16.0, 35.0, 4.0, 12.0, 22.0, 40.0])
    sys_ = psg + np.random.normal(0, 2, len(psg))
    sys_ = np.clip(sys_, 0, None)
    return [
        {"subject_id": f"s{i+1:02d}", "system_ahi": float(sys_[i]), "psg_ahi": float(psg[i])}
        for i in range(len(psg))
    ]


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ====================================================================
#  CONFIG TESTS
# ====================================================================

class TestConfig:
    def test_ahi_severity_cutoffs(self):
        assert CFG.AHI_SEVERITY_CUTOFFS["Normal"] == 5
        assert CFG.AHI_SEVERITY_CUTOFFS["Mild"] == 15
        assert CFG.AHI_SEVERITY_CUTOFFS["Moderate"] == 30

    def test_clinical_cutoffs(self):
        assert CFG.CLINICAL_AHI_CUTOFFS == [5, 15, 30]

    def test_stage_labels(self):
        assert "Wake" in CFG.STAGE_LABELS_REDUCED
        assert "REM" in CFG.STAGE_LABELS_REDUCED

    def test_event_labels(self):
        assert "Apnea" in CFG.EVENT_LABELS

    def test_theme_colors_exist(self):
        assert CFG.DARK_BG is not None
        assert CFG.ACCENT_PRIMARY is not None


# ====================================================================
#  IO UTILS TESTS
# ====================================================================

class TestIOUtils:
    def test_normalise_apnea(self):
        assert _normalise_event_type("apnea") == "Apnea"
        assert _normalise_event_type("APNEA") == "Apnea"
        assert _normalise_event_type("obstructive_apnea") == "Apnea"

    def test_normalise_hypopnea(self):
        assert _normalise_event_type("hypopnea") == "Hypopnea"
        assert _normalise_event_type("Hypopnea") == "Hypopnea"

    def test_normalise_irregular(self):
        assert _normalise_event_type("irregular") == "Irregular"
        assert _normalise_event_type("Irregular") == "Irregular"

    def test_normalise_normal(self):
        assert _normalise_event_type("normal") == "Normal"
        assert _normalise_event_type("Normal") == "Normal"

    def test_normalise_motion(self):
        assert _normalise_event_type("motion") == "Motion"

    def test_normalise_unknown(self):
        assert _normalise_event_type("xyzzy") == "xyzzy"

    def test_load_psg_events_csv(self, tmp_dir):
        csv_path = os.path.join(tmp_dir, "psg.csv")
        with open(csv_path, "w") as f:
            f.write("subject_id,event_type,timestamp_start,timestamp_end\n")
            f.write("s01,apnea,10.0,25.0\n")
            f.write("s01,hypopnea,60.0,80.0\n")
        events = load_psg_events_csv(csv_path)
        assert len(events) == 2
        assert events[0]["event_type"] == "Apnea"
        assert events[0]["timestamp_start"] == 10.0

    def test_load_psg_events_json(self, tmp_dir):
        json_path = os.path.join(tmp_dir, "psg.json")
        data = [
            {"timestamp_start": 10.0, "timestamp_end": 25.0, "event_type": "Apnea"},
            {"timestamp_start": 60.0, "timestamp_end": 80.0, "event_type": "Hypopnea"},
        ]
        with open(json_path, "w") as f:
            json.dump(data, f)
        events = load_psg_events_json(json_path)
        assert len(events) == 2

    def test_load_psg_stages_csv(self, tmp_dir):
        csv_path = os.path.join(tmp_dir, "stages.csv")
        with open(csv_path, "w") as f:
            f.write("subject_id,epoch_index,timestamp_start,timestamp_end,stage\n")
            f.write("s01,0,0.0,30.0,Wake\n")
            f.write("s01,1,30.0,60.0,Light\n")
            f.write("s01,2,60.0,90.0,Deep\n")
        stages = load_psg_stages_csv(csv_path)
        assert len(stages) == 3
        assert stages[0]["stage"] == "Wake"
        assert stages[1]["epoch_index"] == 1

    def test_load_system_events_json(self, tmp_dir):
        json_path = os.path.join(tmp_dir, "sys.json")
        data = {"events": [
            {"timestamp_start": 10.0, "timestamp_end": 25.0, "event_type": "Apnea"},
        ]}
        with open(json_path, "w") as f:
            json.dump(data, f)
        events = load_system_events_json(json_path)
        assert len(events) == 1

    def test_load_system_stages_json(self, tmp_dir):
        json_path = os.path.join(tmp_dir, "sys_stages.json")
        data = {"epoch_records": [
            {"predicted_stage": "Wake"},
            {"predicted_stage": "Light"},
        ]}
        with open(json_path, "w") as f:
            json.dump(data, f)
        stages = load_system_stages_json(json_path)
        assert len(stages) == 2
        assert stages[0]["stage"] == "Wake"
        assert stages[1]["stage"] == "Light"

    def test_load_psg_ahi_csv(self, tmp_dir):
        csv_path = os.path.join(tmp_dir, "ahi.csv")
        with open(csv_path, "w") as f:
            f.write("subject_id,ahi\n")
            f.write("s01,12.5\n")
            f.write("s02,30.0\n")
        rows = load_psg_ahi_csv(csv_path)
        assert len(rows) == 2
        assert rows[0]["ahi"] == 12.5

    def test_save_validation_report(self, tmp_dir):
        results = {"event_metrics": {"tp": 3, "fp": 1, "fn": 2}}
        paths = save_validation_report(results, tmp_dir)
        assert "json" in paths
        assert os.path.exists(paths["json"])


# ====================================================================
#  EVENT METRICS TESTS
# ====================================================================

class TestEventMetrics:
    def test_overlap_iou_identical(self):
        assert _overlap_iou(
            {"timestamp_start": 10, "timestamp_end": 20},
            {"timestamp_start": 10, "timestamp_end": 20},
        ) == 1.0

    def test_overlap_iou_no_overlap(self):
        assert _overlap_iou(
            {"timestamp_start": 10, "timestamp_end": 20},
            {"timestamp_start": 30, "timestamp_end": 40},
        ) == 0.0

    def test_overlap_iou_partial(self):
        iou = _overlap_iou(
            {"timestamp_start": 10, "timestamp_end": 20},
            {"timestamp_start": 15, "timestamp_end": 25},
        )
        # intersection = 5, union = 15
        assert abs(iou - 5.0 / 15.0) < 1e-6

    def test_event_midpoint(self):
        assert _event_midpoint({"timestamp_start": 10, "timestamp_end": 20}) == 15.0

    def test_event_duration(self):
        assert _event_duration({"timestamp_start": 10, "timestamp_end": 25}) == 15.0

    def test_match_events_basic(self, psg_events, sys_events):
        matched, un_ref, un_pred = match_events(psg_events, sys_events)
        # 3 matched (first three PSG), 2 unmatched ref (Irregular + last Apnea),
        # 1 unmatched pred (FP)
        assert len(matched) == 3
        assert len(un_ref) == 2
        assert len(un_pred) == 1

    def test_compute_event_metrics(self, psg_events, sys_events):
        m = compute_event_metrics(psg_events, sys_events)
        assert m["tp"] == 3
        assert m["fp"] == 1
        assert m["fn"] == 2
        assert 0 < m["precision"] <= 1
        assert 0 < m["recall"] <= 1
        assert 0 < m["f1"] <= 1

    def test_compute_event_metrics_per_type(self, psg_events, sys_events):
        m = compute_event_metrics(psg_events, sys_events)
        assert "per_type" in m
        assert "Apnea" in m["per_type"]

    def test_duration_errors(self, psg_events, sys_events):
        m = compute_event_metrics(psg_events, sys_events)
        dur = m["duration_errors"]
        assert dur["n"] == 3
        assert dur["mae"] >= 0
        assert dur["rmse"] >= 0

    def test_epoch_metrics(self):
        """Epoch-level binary metrics with string labels."""
        ref_labels = ["Normal", "Apnea", "Normal", "Irregular", "Normal",
                       "Apnea", "Normal", "Normal", "Hypopnea", "Normal"]
        pred_labels = ["Normal", "Apnea", "Normal", "Normal", "Normal",
                        "Apnea", "Apnea", "Normal", "Hypopnea", "Normal"]
        m = compute_epoch_metrics(ref_labels, pred_labels)
        assert "sensitivity" in m
        assert "specificity" in m
        assert "f1" in m
        assert 0 <= m["sensitivity"] <= 1

    def test_all_matched(self):
        """All events match perfectly."""
        ref = [{"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"}]
        pred = [{"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"}]
        m = compute_event_metrics(ref, pred)
        assert m["tp"] == 1
        assert m["fp"] == 0
        assert m["fn"] == 0
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0

    def test_no_events(self):
        m = compute_event_metrics([], [])
        assert m["tp"] == 0
        assert m["fp"] == 0
        assert m["fn"] == 0


# ====================================================================
#  AHI TESTS
# ====================================================================

class TestAHI:
    def test_compute_ahi_basic(self):
        events = [
            {"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"},
            {"timestamp_start": 30, "timestamp_end": 50, "event_type": "Hypopnea"},
            {"timestamp_start": 100, "timestamp_end": 115, "event_type": "Irregular"},
        ]
        result = compute_ahi(events, total_sleep_time_hr=1.0)
        assert result["ahi"] == 3.0  # 3 events / 1 hour
        assert result["severity"] == "Normal"

    def test_compute_ahi_ignores_normal(self):
        events = [
            {"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"},
            {"timestamp_start": 30, "timestamp_end": 50, "event_type": "Normal"},
        ]
        result = compute_ahi(events, total_sleep_time_hr=1.0)
        assert result["ahi"] == 1.0

    def test_classify_severity_normal(self):
        assert classify_ahi_severity(3.0) == "Normal"

    def test_classify_severity_mild(self):
        assert classify_ahi_severity(10.0) == "Mild"

    def test_classify_severity_moderate(self):
        assert classify_ahi_severity(20.0) == "Moderate"

    def test_classify_severity_severe(self):
        assert classify_ahi_severity(35.0) == "Severe"

    def test_classify_severity_boundary(self):
        assert classify_ahi_severity(5.0) == "Mild"
        assert classify_ahi_severity(15.0) == "Moderate"
        assert classify_ahi_severity(30.0) == "Severe"

    def test_compare_ahi(self, subjects_data):
        cmp = compare_ahi(subjects_data)
        assert "per_subject" in cmp
        assert len(cmp["per_subject"]) == 8
        assert "aggregate" in cmp
        assert "ahi_errors" in cmp
        assert cmp["ahi_errors"]["mae"] >= 0

    def test_compare_ahi_correlation(self, subjects_data):
        cmp = compare_ahi(subjects_data)
        corr = cmp["correlation"]
        assert "pearson_r" in corr
        assert abs(corr["pearson_r"]) <= 1.0

    def test_screening_performance(self, subjects_data):
        scr = screening_performance(subjects_data, cutoff=15.0)
        assert "sensitivity" in scr
        assert "specificity" in scr
        assert "ppv" in scr
        assert "npv" in scr
        assert scr["tp"] + scr["tn"] + scr["fp"] + scr["fn"] == len(subjects_data)

    def test_empty_events(self):
        result = compute_ahi([], total_sleep_time_hr=1.0)
        assert result["ahi"] == 0.0
        assert result["severity"] == "Normal"


# ====================================================================
#  AGREEMENT TESTS
# ====================================================================

class TestAgreement:
    def test_bland_altman_identical(self):
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ba = bland_altman(a, a)
        assert ba["mean_diff"] == 0.0
        assert ba["std_diff"] == 0.0
        assert ba["pct_within_loa"] == 100.0

    def test_bland_altman_known(self):
        a = np.array([10.0, 20.0, 30.0])
        b = np.array([12.0, 18.0, 31.0])
        ba = bland_altman(a, b)
        # diffs = [-2, 2, -1], mean = -1/3
        expected_mean = (-2 + 2 + -1) / 3
        assert abs(ba["mean_diff"] - expected_mean) < 1e-3  # rounded to 4dp in source
        assert ba["n"] == 3

    def test_icc_perfect(self):
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        icc = compute_icc(a, a)
        assert icc["icc"] >= 0.99

    def test_icc_random(self):
        np.random.seed(0)
        a = np.random.rand(20)
        b = np.random.rand(20)
        icc = compute_icc(a, b)
        # random should have poor ICC
        assert icc["icc"] < 0.5

    def test_confusion_matrix(self):
        pred = ["A", "B", "A", "C", "B"]
        ref = ["A", "B", "B", "C", "A"]
        cm = build_confusion_matrix(pred, ref)
        assert cm["accuracy"] == 3 / 5  # A-A, B-B, C-C correct
        assert cm["labels"] == ["A", "B", "C"]
        assert len(cm["matrix"]) == 3

    def test_cohens_kappa_perfect(self):
        pred = ["A", "B", "C", "A"]
        ref = ["A", "B", "C", "A"]
        k = cohens_kappa(pred, ref)
        assert k["kappa"] == 1.0

    def test_cohens_kappa_poor(self):
        pred = ["A", "A", "A", "A"]
        ref = ["B", "B", "B", "B"]
        k = cohens_kappa(pred, ref)
        assert k["kappa"] <= 0.0

    def test_bland_altman_empty(self):
        ba = bland_altman(np.array([]), np.array([]))
        assert ba["n"] == 0

    def test_icc_insufficient(self):
        icc = compute_icc(np.array([1.0]), np.array([2.0]))
        assert icc["icc"] is None


# ====================================================================
#  STAGING VALIDATION TESTS
# ====================================================================

class TestStagingValidation:
    def test_validate_stages_basic(self, stage_labels):
        ref, pred = stage_labels
        result = validate_stages(ref, pred)
        assert "accuracy" in result
        assert "cohens_kappa" in result
        assert "per_class" in result
        assert 0 <= result["accuracy"] <= 1

    def test_validate_stages_perfect(self):
        stages = ["Wake", "Light", "Deep", "REM"] * 10
        result = validate_stages(stages, stages)
        assert result["accuracy"] == 1.0
        assert result["cohens_kappa"] == 1.0

    def test_validate_stages_per_class(self, stage_labels):
        ref, pred = stage_labels
        result = validate_stages(ref, pred)
        for stage_name, metrics in result["per_class"].items():
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1" in metrics
            assert "support" in metrics

    def test_stage_transition_agreement(self, stage_labels):
        ref, pred = stage_labels
        ta = stage_transition_agreement(ref, pred)
        assert "ref_transitions" in ta
        assert "pred_transitions" in ta
        assert "both_transitions" in ta
        assert ta["ref_transitions"] >= 0

    def test_validate_stages_empty(self):
        result = validate_stages([], [])
        assert result["n_epochs"] == 0

    def test_validate_stages_macro_metrics(self, stage_labels):
        ref, pred = stage_labels
        result = validate_stages(ref, pred)
        assert "precision_macro" in result
        assert "recall_macro" in result
        assert "f1_macro" in result

    def test_confusion_matrix_in_staging(self, stage_labels):
        ref, pred = stage_labels
        result = validate_stages(ref, pred)
        assert "confusion_matrix" in result

    def test_classification_report(self, stage_labels):
        ref, pred = stage_labels
        result = validate_stages(ref, pred)
        assert "classification_report" in result


# ====================================================================
#  THRESHOLD OPTIMIZATION TESTS
# ====================================================================

class TestThresholdOptimization:
    def test_ahi_roc_curve(self, subjects_data):
        roc = ahi_roc_curve(subjects_data, psg_cutoff=15.0)
        assert "auc" in roc
        assert "best_threshold" in roc
        assert 0 <= roc["auc"] <= 1.0

    def test_ahi_roc_curve_tpr_fpr(self, subjects_data):
        roc = ahi_roc_curve(subjects_data, psg_cutoff=15.0)
        assert "tpr" in roc
        assert "fpr" in roc
        assert len(roc["tpr"]) == len(roc["fpr"])

    def test_optimize_confidence_threshold(self, psg_events, sys_events):
        result = optimize_event_confidence_threshold(psg_events, sys_events)
        assert "best_threshold" in result
        assert "best_f1" in result
        assert 0 <= result["best_threshold"] <= 1.0

    def test_multi_cutoff_screening(self, subjects_data):
        results = multi_cutoff_screening(subjects_data)
        assert len(results) == 3  # cutoffs 5, 15, 30
        for r in results:
            assert "cutoff" in r
            assert "sensitivity" in r
            assert "specificity" in r

    def test_roc_with_no_positive(self):
        """All subjects below cutoff."""
        subj = [
            {"subject_id": "s1", "system_ahi": 1.0, "psg_ahi": 1.0},
            {"subject_id": "s2", "system_ahi": 2.0, "psg_ahi": 2.0},
            {"subject_id": "s3", "system_ahi": 3.0, "psg_ahi": 3.0},
        ]
        roc = ahi_roc_curve(subj, psg_cutoff=15.0)
        # Should handle gracefully
        assert "auc" in roc


# ====================================================================
#  VISUALIZE TESTS
# ====================================================================

class TestVisualize:
    def test_save_all_plots_with_results(self, tmp_dir, subjects_data, psg_events, sys_events):
        sys_ahis = np.array([s["system_ahi"] for s in subjects_data])
        psg_ahis = np.array([s["psg_ahi"] for s in subjects_data])
        results = {
            "bland_altman": bland_altman(sys_ahis, psg_ahis),
            "ahi_comparison": compare_ahi(subjects_data),
            "event_metrics": compute_event_metrics(psg_events, sys_events),
            "roc_curve": ahi_roc_curve(subjects_data, psg_cutoff=15.0),
            "ref_events": psg_events,
            "pred_events": sys_events,
        }
        paths = save_all_plots(results, tmp_dir)
        assert isinstance(paths, dict)
        # At least one plot should be generated
        assert len(paths) > 0
        for p in paths.values():
            assert os.path.exists(p)

    def test_save_all_plots_empty(self, tmp_dir):
        paths = save_all_plots({}, tmp_dir)
        assert isinstance(paths, dict)

    def test_save_all_plots_staging(self, tmp_dir, stage_labels):
        ref, pred = stage_labels
        stg = validate_stages(ref, pred)
        results = {"staging_validation": stg}
        paths = save_all_plots(results, tmp_dir)
        assert isinstance(paths, dict)


# ====================================================================
#  REPORTING TESTS
# ====================================================================

class TestReporting:
    def test_report_json(self, tmp_dir, subjects_data, psg_events, sys_events):
        sys_ahis = np.array([s["system_ahi"] for s in subjects_data])
        psg_ahis = np.array([s["psg_ahi"] for s in subjects_data])
        results = {
            "event_metrics": compute_event_metrics(psg_events, sys_events),
            "ahi_comparison": compare_ahi(subjects_data),
            "bland_altman": bland_altman(sys_ahis, psg_ahis),
        }
        paths = report_validation_results(results, tmp_dir)
        assert "json" in paths
        assert os.path.exists(paths["json"])
        with open(paths["json"]) as f:
            loaded = json.load(f)
        assert "event_metrics" in loaded

    def test_report_csv(self, tmp_dir, subjects_data):
        results = {
            "ahi_comparison": compare_ahi(subjects_data),
        }
        paths = report_validation_results(results, tmp_dir)
        assert "csv" in paths
        assert os.path.exists(paths["csv"])

    def test_report_markdown(self, tmp_dir, subjects_data, psg_events, sys_events, stage_labels):
        sys_ahis = np.array([s["system_ahi"] for s in subjects_data])
        psg_ahis = np.array([s["psg_ahi"] for s in subjects_data])
        ref, pred = stage_labels
        results = {
            "event_metrics": compute_event_metrics(psg_events, sys_events),
            "ahi_comparison": compare_ahi(subjects_data),
            "bland_altman": bland_altman(sys_ahis, psg_ahis),
            "staging_validation": validate_stages(ref, pred),
        }
        paths = report_validation_results(results, tmp_dir)
        assert "markdown" in paths
        assert os.path.exists(paths["markdown"])
        with open(paths["markdown"], encoding="utf-8") as f:
            md = f.read()
        assert "# Validation" in md
        assert "Event Detection" in md
        assert "AHI Comparison" in md
        assert "Sleep Stage Validation" in md

    def test_report_empty_results(self, tmp_dir):
        paths = report_validation_results({}, tmp_dir)
        assert "json" in paths
        assert "markdown" in paths


# ====================================================================
#  END-TO-END (CLI) TESTS
# ====================================================================

class TestEndToEnd:
    def test_demo_run(self, tmp_dir):
        """End-to-end demo run via the run_validation module."""
        from validation.run_validation import run_validation, _parse_args
        args = _parse_args(["--demo", "--output", tmp_dir, "--no-plots"])
        results = run_validation(args)
        assert "event_metrics" in results
        assert "ahi_comparison" in results
        assert "staging_validation" in results
        assert "report_paths" in results

    def test_demo_with_plots(self, tmp_dir):
        from validation.run_validation import run_validation, _parse_args
        args = _parse_args(["--demo", "--output", tmp_dir])
        results = run_validation(args)
        assert "plot_paths" in results
        assert len(results["plot_paths"]) > 0

    def test_demo_report_files(self, tmp_dir):
        from validation.run_validation import run_validation, _parse_args
        args = _parse_args(["--demo", "--output", tmp_dir, "--no-plots"])
        results = run_validation(args)
        rp = results["report_paths"]
        assert os.path.exists(rp["json"])
        assert os.path.exists(rp["markdown"])

    def test_empty_run(self, tmp_dir):
        """Run with no data – should not crash."""
        from validation.run_validation import run_validation, _parse_args
        args = _parse_args(["--output", tmp_dir, "--no-plots"])
        results = run_validation(args)
        assert "timestamp" in results


# ====================================================================
#  EDGE CASE TESTS
# ====================================================================

class TestEdgeCases:
    def test_single_event(self):
        ref = [{"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"}]
        pred = [{"timestamp_start": 1, "timestamp_end": 16, "event_type": "Apnea"}]
        m = compute_event_metrics(ref, pred)
        assert m["tp"] == 1
        assert m["f1"] == 1.0

    def test_only_false_positives(self):
        ref = []
        pred = [{"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"}]
        m = compute_event_metrics(ref, pred)
        assert m["fp"] == 1
        assert m["tp"] == 0
        assert m["precision"] == 0.0

    def test_only_false_negatives(self):
        pred = []
        ref = [{"timestamp_start": 0, "timestamp_end": 15, "event_type": "Apnea"}]
        m = compute_event_metrics(ref, pred)
        assert m["fn"] == 1
        assert m["tp"] == 0
        assert m["recall"] == 0.0

    def test_ahi_zero_hours(self):
        result = compute_ahi([], total_sleep_time_hr=0.0)
        assert result["ahi"] == 0.0

    def test_bland_altman_single(self):
        ba = bland_altman(np.array([5.0]), np.array([6.0]))
        assert ba["mean_diff"] == -1.0
        assert ba["n"] == 1

    def test_large_dataset(self):
        """Stress test with many events."""
        np.random.seed(123)
        n = 500
        ref = [{"timestamp_start": float(i * 40), "timestamp_end": float(i * 40 + 15),
                "event_type": "Apnea"} for i in range(n)]
        pred = [{"timestamp_start": float(i * 40 + np.random.normal(0, 2)),
                 "timestamp_end": float(i * 40 + 15 + np.random.normal(0, 2)),
                 "event_type": "Apnea", "confidence": 0.8}
                for i in range(n)]
        m = compute_event_metrics(ref, pred)
        assert m["tp"] == n  # all should match
        assert m["fp"] == 0
        assert m["fn"] == 0

    def test_severity_boundary_values(self):
        assert classify_ahi_severity(0.0) == "Normal"
        assert classify_ahi_severity(4.99) == "Normal"
        assert classify_ahi_severity(5.0) == "Mild"
        assert classify_ahi_severity(14.99) == "Mild"
        assert classify_ahi_severity(15.0) == "Moderate"
        assert classify_ahi_severity(29.99) == "Moderate"
        assert classify_ahi_severity(30.0) == "Severe"
        assert classify_ahi_severity(100.0) == "Severe"

    def test_icc_constant_values(self):
        a = np.array([5.0, 5.0, 5.0, 5.0])
        icc = compute_icc(a, a)
        # constant values → undefined ICC, should handle gracefully
        assert "icc" in icc

    def test_kappa_single_class(self):
        pred = ["A", "A", "A"]
        ref = ["A", "A", "A"]
        k = cohens_kappa(pred, ref)
        # Perfect agreement, but single class → κ can be undefined
        assert "kappa" in k
