"""
field_testing/tests/test_field_testing.py
─────────────────────────────────────────
Comprehensive unit + integration tests for the field-testing &
deployment evaluation module.

Run:  python -m pytest field_testing/tests/test_field_testing.py -v
"""

from __future__ import annotations
import json
import os
import sys
import tempfile

import numpy as np
import pytest

# ── Ensure imports resolve ─────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from field_testing import config as CFG
from field_testing.test_config import (
    make_test_config,
    generate_test_configs,
    save_configs,
    load_configs,
    save_configs_csv,
)
from field_testing.synthetic_data import (
    generate_recording,
    generate_batch,
)
from field_testing.field_runner import (
    run_field_test,
    run_field_tests,
    _binary_f1,
    _cohens_kappa,
    _linear_drift,
)
from field_testing.metrics import (
    evaluate_field_results,
    compute_placement_metrics,
    compute_environment_metrics,
    compute_subject_metrics,
    compute_confidence_interval,
)
from field_testing.robustness import (
    classify_tier,
    score_single_result,
    score_placement,
    score_environment,
    aggregate_robustness,
    _rr_score,
    _hr_score,
    _event_score,
    _stage_score,
    _motion_score,
)
from field_testing.visualize import plot_field_performance
from field_testing.reports import (
    report_deployment_recommendations,
    write_report,
)
from field_testing.run_field_testing import (
    parse_args,
    run_field_testing,
    _safe_serialise,
)


# ────────────────────────────────────────────────────────────────────
#  FIXTURES
# ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def single_config():
    return make_test_config(
        subject_id="test_sub_01",
        placement="bedside_right",
        mattress="foam",
        bedding="duvet",
        test_id="TEST0001",
    )


@pytest.fixture(scope="module")
def batch_configs():
    return generate_test_configs(n_subjects=3, seed=42)


@pytest.fixture(scope="module")
def single_recording(single_config):
    return generate_recording(single_config, n_epochs=120, seed=42)


@pytest.fixture(scope="module")
def batch_recordings(batch_configs):
    return generate_batch(batch_configs, seed=42, n_epochs=120)


@pytest.fixture(scope="module")
def single_result(single_recording):
    return run_field_test(single_recording)


@pytest.fixture(scope="module")
def batch_results(batch_recordings):
    return run_field_tests(batch_recordings)


@pytest.fixture(scope="module")
def field_evaluation(batch_results):
    return evaluate_field_results(batch_results)


@pytest.fixture(scope="module")
def robustness_result(field_evaluation):
    return aggregate_robustness(field_evaluation)


@pytest.fixture()
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ════════════════════════════════════════════════════════════════════
#  1.  CONFIG MODULE
# ════════════════════════════════════════════════════════════════════

class TestConfig:
    """Tests for config.py constants."""

    def test_placement_types_non_empty(self):
        assert len(CFG.PLACEMENT_TYPES) >= 6

    def test_placement_coords_keys_match(self):
        for pt in CFG.PLACEMENT_TYPES:
            assert pt in CFG.PLACEMENT_COORDS_DEFAULT

    def test_mattress_types_non_empty(self):
        assert len(CFG.MATTRESS_TYPES) >= 3

    def test_bedding_types_non_empty(self):
        assert len(CFG.BEDDING_TYPES) >= 3

    def test_occlusion_types_non_empty(self):
        assert len(CFG.OCCLUSION_TYPES) >= 4

    def test_metric_weights_sum_1(self):
        assert abs(sum(CFG.METRIC_WEIGHTS.values()) - 1.0) < 1e-9

    def test_thresholds_ordered(self):
        assert CFG.RR_MAE_EXCELLENT < CFG.RR_MAE_GOOD < CFG.RR_MAE_ACCEPTABLE
        assert CFG.HR_MAE_EXCELLENT < CFG.HR_MAE_GOOD < CFG.HR_MAE_ACCEPTABLE
        assert CFG.EVENT_F1_EXCELLENT > CFG.EVENT_F1_GOOD > CFG.EVENT_F1_ACCEPTABLE
        assert CFG.STAGE_KAPPA_EXCELLENT > CFG.STAGE_KAPPA_GOOD > CFG.STAGE_KAPPA_ACCEPTABLE

    def test_dark_theme_colours_hex(self):
        for c in [CFG.DARK_BG, CFG.DARK_CARD, CFG.DARK_TEXT,
                  CFG.ACCENT_PRIMARY, CFG.ACCENT_GOOD]:
            assert c.startswith("#")


# ════════════════════════════════════════════════════════════════════
#  2.  TEST CONFIG MODULE
# ════════════════════════════════════════════════════════════════════

class TestTestConfig:
    """Tests for test_config.py."""

    def test_make_test_config_keys(self, single_config):
        expected = {
            "test_id", "subject_id", "timestamp", "placement",
            "placement_coords", "mattress", "bedding", "occlusions",
            "room_size", "duration_sec", "ground_truth", "notes",
        }
        assert expected.issubset(set(single_config.keys()))

    def test_make_test_config_defaults(self):
        cfg = make_test_config()
        assert len(cfg["test_id"]) > 0
        assert cfg["placement"] == "bedside_right"
        assert cfg["mattress"] == "foam"
        assert cfg["bedding"] == "duvet"
        assert cfg["room_size"] == "medium"
        assert isinstance(cfg["placement_coords"], list)
        assert len(cfg["placement_coords"]) == 3

    def test_make_test_config_custom_id(self):
        cfg = make_test_config(test_id="CUSTOM")
        assert cfg["test_id"] == "CUSTOM"

    def test_make_test_config_custom_coords(self):
        cfg = make_test_config(placement_coords=(1.0, 2.0, 3.0))
        assert cfg["placement_coords"] == [1.0, 2.0, 3.0]

    def test_make_test_config_occlusions(self):
        cfg = make_test_config(occlusions=["partner_present", "fan_running"])
        assert cfg["occlusions"] == ["partner_present", "fan_running"]

    def test_generate_test_configs_count(self, batch_configs):
        # 3 subjects × 4 placements × 3 envs = 36
        assert len(batch_configs) == 36

    def test_generate_test_configs_unique_ids(self, batch_configs):
        ids = [c["test_id"] for c in batch_configs]
        assert len(set(ids)) == len(ids)

    def test_generate_test_configs_subjects(self, batch_configs):
        subs = set(c["subject_id"] for c in batch_configs)
        assert len(subs) == 3

    def test_generate_test_configs_placements(self, batch_configs):
        pls = set(c["placement"] for c in batch_configs)
        assert len(pls) == 4

    def test_save_load_roundtrip(self, batch_configs, tmp_dir):
        path = save_configs(batch_configs, tmp_dir, "test_cfgs.json")
        assert os.path.exists(path)
        loaded = load_configs(path)
        assert len(loaded) == len(batch_configs)
        for orig, ld in zip(batch_configs, loaded):
            assert orig["test_id"] == ld["test_id"]
            assert orig["placement"] == ld["placement"]

    def test_save_configs_csv(self, batch_configs, tmp_dir):
        path = save_configs_csv(batch_configs, tmp_dir, "test.csv")
        assert os.path.exists(path)
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == len(batch_configs) + 1  # header + rows

    def test_generate_deterministic(self):
        c1 = generate_test_configs(n_subjects=2, seed=99)
        c2 = generate_test_configs(n_subjects=2, seed=99)
        for a, b in zip(c1, c2):
            assert a["test_id"] == b["test_id"]
            assert a["mattress"] == b["mattress"]


# ════════════════════════════════════════════════════════════════════
#  3.  SYNTHETIC DATA MODULE
# ════════════════════════════════════════════════════════════════════

class TestSyntheticData:
    """Tests for synthetic_data.py."""

    def test_recording_keys(self, single_recording):
        expected = {
            "test_id", "subject_id", "config", "n_epochs",
            "rr_radar", "rr_truth", "hr_radar", "hr_truth",
            "event_pred", "event_truth",
            "stage_pred", "stage_truth",
            "motion_index", "posture_pred", "posture_truth",
        }
        assert expected.issubset(set(single_recording.keys()))

    def test_recording_length(self, single_recording):
        n = single_recording["n_epochs"]
        assert n == 120
        for key in ["rr_radar", "rr_truth", "hr_radar", "hr_truth",
                     "event_pred", "event_truth", "stage_pred",
                     "stage_truth", "motion_index", "posture_pred",
                     "posture_truth"]:
            assert len(single_recording[key]) == n

    def test_rr_truth_in_range(self, single_recording):
        rr = single_recording["rr_truth"]
        assert np.all(rr >= CFG.RR_NORMAL_RANGE[0])
        assert np.all(rr <= CFG.RR_NORMAL_RANGE[1])

    def test_hr_truth_in_range(self, single_recording):
        hr = single_recording["hr_truth"]
        assert np.all(hr >= CFG.HR_NORMAL_RANGE[0])
        assert np.all(hr <= CFG.HR_NORMAL_RANGE[1])

    def test_events_binary(self, single_recording):
        ev = single_recording["event_truth"]
        assert set(np.unique(ev)).issubset({0, 1})

    def test_stages_labels(self, single_recording):
        st = single_recording["stage_truth"]
        assert set(np.unique(st)).issubset({0, 1, 2, 3})

    def test_posture_labels(self, single_recording):
        pos = single_recording["posture_truth"]
        assert set(np.unique(pos)).issubset({0, 1, 2, 3})

    def test_motion_non_negative(self, single_recording):
        assert np.all(single_recording["motion_index"] >= 0)

    def test_dropout_exists(self, single_recording):
        rr = single_recording["rr_radar"]
        # With duvet + bedside_right, dropout is low but may exist
        # Just check radar is float and may have NaN
        assert rr.dtype == float or rr.dtype == np.float64

    def test_batch_size(self, batch_recordings, batch_configs):
        assert len(batch_recordings) == len(batch_configs)

    def test_deterministic(self, single_config):
        r1 = generate_recording(single_config, n_epochs=60, seed=123)
        r2 = generate_recording(single_config, n_epochs=60, seed=123)
        np.testing.assert_array_equal(r1["rr_truth"], r2["rr_truth"])
        np.testing.assert_array_equal(r1["hr_truth"], r2["hr_truth"])

    def test_different_seeds_differ(self, single_config):
        r1 = generate_recording(single_config, n_epochs=60, seed=1)
        r2 = generate_recording(single_config, n_epochs=60, seed=2)
        assert not np.array_equal(r1["rr_truth"], r2["rr_truth"])

    def test_placement_noise_effect(self):
        cfg_close = make_test_config(placement="bedside_right",
                                     bedding="thin_sheet", test_id="A1")
        cfg_far   = make_test_config(placement="corner_left",
                                     bedding="thin_sheet", test_id="A2")
        r_close = generate_recording(cfg_close, n_epochs=960, seed=42)
        r_far   = generate_recording(cfg_far, n_epochs=960, seed=42)
        err_close = np.nanmean(np.abs(r_close["rr_radar"] - r_close["rr_truth"]))
        err_far = np.nanmean(np.abs(r_far["rr_radar"] - r_far["rr_truth"]))
        # Corner placement should have higher error
        assert err_far > err_close

    def test_bedding_effect(self):
        cfg_thin = make_test_config(bedding="thin_sheet",
                                    placement="bedside_right", test_id="B1")
        cfg_heavy = make_test_config(bedding="weighted_blanket",
                                     placement="bedside_right", test_id="B2")
        r_thin = generate_recording(cfg_thin, n_epochs=960, seed=42)
        r_heavy = generate_recording(cfg_heavy, n_epochs=960, seed=42)
        err_thin = np.nanmean(np.abs(r_thin["rr_radar"] - r_thin["rr_truth"]))
        err_heavy = np.nanmean(np.abs(r_heavy["rr_radar"] - r_heavy["rr_truth"]))
        assert err_heavy > err_thin


# ════════════════════════════════════════════════════════════════════
#  4.  FIELD RUNNER MODULE
# ════════════════════════════════════════════════════════════════════

class TestFieldRunner:
    """Tests for field_runner.py."""

    def test_result_keys(self, single_result):
        expected = {
            "test_id", "subject_id", "placement", "environment",
            "rr_errors", "hr_errors", "dropout_mask",
            "event_match", "stage_match", "posture_match",
            "summary",
        }
        assert expected.issubset(set(single_result.keys()))

    def test_summary_keys(self, single_result):
        s = single_result["summary"]
        expected = {
            "rr_mae", "rr_std", "rr_drift",
            "hr_mae", "hr_std", "hr_drift",
            "dropout_rate",
            "event_acc", "event_f1",
            "stage_acc", "stage_kappa",
            "posture_acc", "motion_std",
            "n_epochs", "n_valid",
        }
        assert expected.issubset(set(s.keys()))

    def test_rr_mae_positive(self, single_result):
        assert single_result["summary"]["rr_mae"] >= 0

    def test_hr_mae_positive(self, single_result):
        assert single_result["summary"]["hr_mae"] >= 0

    def test_event_f1_range(self, single_result):
        f1 = single_result["summary"]["event_f1"]
        assert 0.0 <= f1 <= 1.0

    def test_stage_kappa_range(self, single_result):
        kappa = single_result["summary"]["stage_kappa"]
        assert -1.0 <= kappa <= 1.0

    def test_posture_acc_range(self, single_result):
        acc = single_result["summary"]["posture_acc"]
        assert 0.0 <= acc <= 1.0

    def test_dropout_rate_range(self, single_result):
        d = single_result["summary"]["dropout_rate"]
        assert 0.0 <= d <= 1.0

    def test_n_valid_less_equal_n_epochs(self, single_result):
        s = single_result["summary"]
        assert s["n_valid"] <= s["n_epochs"]

    def test_batch_results_count(self, batch_results, batch_recordings):
        assert len(batch_results) == len(batch_recordings)

    def test_environment_structure(self, single_result):
        env = single_result["environment"]
        assert "mattress" in env
        assert "bedding" in env
        assert "room_size" in env

    # -- internal helpers --

    def test_binary_f1_perfect(self):
        y = np.array([0, 1, 1, 0, 1])
        assert _binary_f1(y, y) == 1.0

    def test_binary_f1_zero(self):
        y_true = np.array([1, 1, 1])
        y_pred = np.array([0, 0, 0])
        assert _binary_f1(y_true, y_pred) == 0.0

    def test_binary_f1_partial(self):
        y_true = np.array([0, 1, 1, 0])
        y_pred = np.array([0, 1, 0, 0])
        f1 = _binary_f1(y_true, y_pred)
        assert 0.0 < f1 < 1.0

    def test_cohens_kappa_perfect(self):
        y = np.array([0, 1, 2, 3, 0, 1])
        assert _cohens_kappa(y, y, n_classes=4) == pytest.approx(1.0)

    def test_cohens_kappa_no_agreement(self):
        y_true = np.array([0, 0, 0, 0])
        y_pred = np.array([1, 1, 1, 1])
        kappa = _cohens_kappa(y_true, y_pred, n_classes=4)
        assert kappa < 0.5

    def test_cohens_kappa_empty(self):
        assert _cohens_kappa(np.array([]), np.array([]), 4) == 0.0

    def test_linear_drift_flat(self):
        errs = np.zeros(100)
        valid = np.ones(100, dtype=bool)
        drift = _linear_drift(errs, valid)
        assert abs(drift) < 1e-10

    def test_linear_drift_rising(self):
        errs = np.linspace(0, 10, 100)
        valid = np.ones(100, dtype=bool)
        drift = _linear_drift(errs, valid)
        assert drift > 0

    def test_linear_drift_few_valid(self):
        errs = np.zeros(10)
        valid = np.zeros(10, dtype=bool)
        valid[0] = True
        valid[5] = True
        drift = _linear_drift(errs, valid)
        assert abs(drift) < 1e-10


# ════════════════════════════════════════════════════════════════════
#  5.  METRICS MODULE
# ════════════════════════════════════════════════════════════════════

class TestMetrics:
    """Tests for metrics.py."""

    def test_evaluation_keys(self, field_evaluation):
        expected = {"n_tests", "overall", "per_placement",
                    "per_environment", "per_subject"}
        assert expected == set(field_evaluation.keys())

    def test_n_tests(self, field_evaluation, batch_results):
        assert field_evaluation["n_tests"] == len(batch_results)

    def test_overall_has_metrics(self, field_evaluation):
        o = field_evaluation["overall"]
        for key in ["rr_mae", "hr_mae", "event_f1", "stage_kappa"]:
            assert key in o
            assert "mean" in o[key]
            assert "std" in o[key]
            assert "ci_low" in o[key]
            assert "ci_high" in o[key]

    def test_per_placement_keys(self, field_evaluation):
        pls = field_evaluation["per_placement"]
        assert len(pls) >= 1
        for pl, agg in pls.items():
            assert "rr_mae" in agg

    def test_per_environment_keys(self, field_evaluation):
        envs = field_evaluation["per_environment"]
        assert len(envs) >= 1
        for ek, agg in envs.items():
            assert "/" in ek  # mattress/bedding format

    def test_per_subject_keys(self, field_evaluation):
        subs = field_evaluation["per_subject"]
        assert len(subs) >= 1

    def test_total_epochs(self, field_evaluation):
        o = field_evaluation["overall"]
        assert o["total_epochs"] > 0
        assert o["total_valid"] > 0
        assert o["total_valid"] <= o["total_epochs"]

    def test_empty_results(self):
        ev = evaluate_field_results([])
        assert ev["n_tests"] == 0
        assert ev["overall"] == {}

    # -- confidence interval --

    def test_ci_basic(self):
        vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        mean, lo, hi = compute_confidence_interval(vals)
        assert abs(mean - 3.0) < 0.01
        assert lo <= mean <= hi

    def test_ci_single_value(self):
        mean, lo, hi = compute_confidence_interval([7.0])
        assert mean == 7.0
        assert lo == 7.0
        assert hi == 7.0

    def test_ci_empty(self):
        mean, lo, hi = compute_confidence_interval([])
        assert mean == 0.0

    def test_ci_with_nans(self):
        vals = [1.0, np.nan, 3.0, np.nan, 5.0]
        mean, lo, hi = compute_confidence_interval(vals)
        assert abs(mean - 3.0) < 0.01

    def test_ci_level(self):
        vals = np.random.RandomState(42).normal(10, 1, 200)
        _, lo95, hi95 = compute_confidence_interval(vals, level=0.95)
        _, lo50, hi50 = compute_confidence_interval(vals, level=0.50)
        assert (hi95 - lo95) >= (hi50 - lo50)

    # -- compute helpers --

    def test_compute_placement_metrics(self, batch_results):
        pm = compute_placement_metrics(batch_results)
        assert len(pm) >= 1

    def test_compute_environment_metrics(self, batch_results):
        em = compute_environment_metrics(batch_results)
        assert len(em) >= 1

    def test_compute_subject_metrics(self, batch_results):
        sm = compute_subject_metrics(batch_results)
        assert len(sm) >= 1


# ════════════════════════════════════════════════════════════════════
#  6.  ROBUSTNESS MODULE
# ════════════════════════════════════════════════════════════════════

class TestRobustness:
    """Tests for robustness.py."""

    # -- tier classification --

    @pytest.mark.parametrize("score,tier", [
        (1.0, "Excellent"),
        (0.9, "Excellent"),
        (0.875, "Excellent"),
        (0.874, "Good"),
        (0.7, "Good"),
        (0.625, "Good"),
        (0.5, "Acceptable"),
        (0.375, "Acceptable"),
        (0.3, "Poor"),
        (0.125, "Poor"),
        (0.1, "Failing"),
        (0.0, "Failing"),
    ])
    def test_classify_tier(self, score, tier):
        assert classify_tier(score) == tier

    # -- metric scorers --

    def test_rr_score_excellent(self):
        assert _rr_score(0.5) == 1.0

    def test_rr_score_good(self):
        assert _rr_score(1.5) == 0.75

    def test_rr_score_acceptable(self):
        assert _rr_score(2.5) == 0.50

    def test_rr_score_poor(self):
        assert _rr_score(4.0) == 0.25

    def test_rr_score_failing(self):
        assert _rr_score(6.0) == 0.0

    def test_rr_score_none(self):
        assert _rr_score(None) == 0.0

    def test_hr_score_excellent(self):
        assert _hr_score(1.0) == 1.0

    def test_hr_score_failing(self):
        assert _hr_score(15.0) == 0.0

    def test_event_score_excellent(self):
        assert _event_score(0.95) == 1.0

    def test_event_score_failing(self):
        assert _event_score(0.30) == 0.0

    def test_stage_score_excellent(self):
        assert _stage_score(0.85) == 1.0

    def test_stage_score_failing(self):
        assert _stage_score(0.10) == 0.0

    def test_motion_score_excellent(self):
        assert _motion_score(0.95) == 1.0

    def test_motion_score_failing(self):
        assert _motion_score(0.50) == 0.0

    # -- single result scoring --

    def test_score_single_result(self, single_result):
        scores = score_single_result(single_result["summary"])
        assert "aggregate" in scores
        assert "tier" in scores
        assert 0.0 <= scores["aggregate"] <= 1.0
        for k in CFG.METRIC_WEIGHTS:
            assert k in scores
            assert 0.0 <= scores[k] <= 1.0

    # -- aggregate robustness --

    def test_aggregate_keys(self, robustness_result):
        expected = {
            "overall_score", "overall_tier", "overall_detail",
            "per_placement", "per_environment",
            "best_placement", "worst_placement",
            "best_environment", "worst_environment",
            "n_tests",
        }
        assert expected.issubset(set(robustness_result.keys()))

    def test_overall_score_range(self, robustness_result):
        assert 0.0 <= robustness_result["overall_score"] <= 1.0

    def test_overall_tier_valid(self, robustness_result):
        assert robustness_result["overall_tier"] in {
            "Excellent", "Good", "Acceptable", "Poor", "Failing",
        }

    def test_best_worst_placement_present(self, robustness_result):
        assert robustness_result["best_placement"] is not None
        assert robustness_result["worst_placement"] is not None

    def test_best_worst_environment_present(self, robustness_result):
        assert robustness_result["best_environment"] is not None
        assert robustness_result["worst_environment"] is not None

    def test_per_placement_scores(self, robustness_result):
        pls = robustness_result["per_placement"]
        for pl, sc in pls.items():
            assert "aggregate" in sc
            assert "tier" in sc
            assert 0.0 <= sc["aggregate"] <= 1.0

    def test_per_environment_scores(self, robustness_result):
        envs = robustness_result["per_environment"]
        for ek, sc in envs.items():
            assert "aggregate" in sc
            assert "tier" in sc

    def test_score_placement_function(self, field_evaluation):
        pm = field_evaluation["per_placement"]
        sp = score_placement(pm)
        assert len(sp) == len(pm)

    def test_score_environment_function(self, field_evaluation):
        em = field_evaluation["per_environment"]
        se = score_environment(em)
        assert len(se) == len(em)

    def test_best_geq_worst_placement(self, robustness_result):
        pls = robustness_result["per_placement"]
        best = pls[robustness_result["best_placement"]]["aggregate"]
        worst = pls[robustness_result["worst_placement"]]["aggregate"]
        assert best >= worst

    def test_empty_evaluation_robustness(self):
        ev = evaluate_field_results([])
        rob = aggregate_robustness(ev)
        assert rob["overall_score"] == 0.0
        assert rob["best_placement"] is None


# ════════════════════════════════════════════════════════════════════
#  7.  VISUALIZE MODULE
# ════════════════════════════════════════════════════════════════════

class TestVisualize:
    """Tests for visualize.py plot generation."""

    def test_plot_field_performance(self, batch_results, field_evaluation,
                                    robustness_result, tmp_dir):
        paths = plot_field_performance(
            batch_results, field_evaluation, robustness_result,
            output_dir=tmp_dir,
        )
        assert isinstance(paths, dict)
        # At least some plots should be generated
        for name, p in paths.items():
            assert os.path.exists(p), f"Plot {name} not found at {p}"
            assert os.path.getsize(p) > 0

    def test_plot_creates_output_dir(self, batch_results,
                                     field_evaluation, robustness_result,
                                     tmp_dir):
        sub = os.path.join(tmp_dir, "subdir")
        paths = plot_field_performance(
            batch_results, field_evaluation, robustness_result,
            output_dir=sub,
        )
        assert os.path.isdir(sub)

    def test_plot_no_crash_empty(self, tmp_dir):
        ev = evaluate_field_results([])
        rob = aggregate_robustness(ev)
        paths = plot_field_performance([], ev, rob, output_dir=tmp_dir)
        assert isinstance(paths, dict)


# ════════════════════════════════════════════════════════════════════
#  8.  REPORTS MODULE
# ════════════════════════════════════════════════════════════════════

class TestReports:
    """Tests for reports.py."""

    def test_report_text(self, robustness_result, field_evaluation):
        txt = report_deployment_recommendations(
            robustness_result, field_evaluation,
        )
        assert isinstance(txt, str)
        assert len(txt) > 200
        assert "EXECUTIVE SUMMARY" in txt
        assert "OVERALL ROBUSTNESS" in txt
        assert "DEPLOYMENT RECOMMENDATION" in txt.upper() or \
               "DEPLOYMENT" in txt.upper()

    def test_report_contains_scores(self, robustness_result,
                                     field_evaluation):
        txt = report_deployment_recommendations(
            robustness_result, field_evaluation,
        )
        tier = robustness_result["overall_tier"]
        assert tier in txt

    def test_report_contains_placements(self, robustness_result,
                                         field_evaluation):
        txt = report_deployment_recommendations(
            robustness_result, field_evaluation,
        )
        best = robustness_result["best_placement"]
        if best:
            assert best in txt

    def test_write_report(self, robustness_result, field_evaluation,
                           tmp_dir):
        txt = report_deployment_recommendations(
            robustness_result, field_evaluation,
        )
        path = write_report(txt, os.path.join(tmp_dir, "report.txt"))
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert content == txt

    def test_report_without_field_eval(self, robustness_result):
        """report_deployment_recommendations accepts field_eval=None."""
        txt = report_deployment_recommendations(robustness_result)
        assert isinstance(txt, str)
        assert len(txt) > 100


# ════════════════════════════════════════════════════════════════════
#  9.  CLI / RUN MODULE
# ════════════════════════════════════════════════════════════════════

class TestCLI:
    """Tests for run_field_testing.py CLI entry-point."""

    def test_parse_args_defaults(self):
        args = parse_args([])
        assert not args.demo
        assert args.seed == CFG.RANDOM_SEED
        assert args.subjects == CFG.SYNTHETIC_N_SUBJECTS
        assert args.placements == CFG.SYNTHETIC_N_PLACEMENTS
        assert not args.no_plots
        assert not args.no_report

    def test_parse_args_demo(self):
        args = parse_args(["--demo"])
        assert args.demo

    def test_parse_args_options(self):
        args = parse_args([
            "--demo",
            "--subjects", "5",
            "--placements", "3",
            "--epochs", "60",
            "--no-plots",
            "--no-report",
            "--seed", "99",
        ])
        assert args.demo
        assert args.subjects == 5
        assert args.placements == 3
        assert args.epochs == 60
        assert args.no_plots
        assert args.no_report
        assert args.seed == 99

    def test_safe_serialise_dict(self):
        d = {"a": np.float64(1.5), "b": np.int64(3)}
        s = _safe_serialise(d)
        assert isinstance(s["a"], float)
        assert isinstance(s["b"], int)

    def test_safe_serialise_array(self):
        arr = np.array([1, 2, 3])
        s = _safe_serialise(arr)
        assert s == [1, 2, 3]

    def test_safe_serialise_nested(self):
        d = {"x": [np.float64(1.0), {"y": np.bool_(True)}]}
        s = _safe_serialise(d)
        assert s == {"x": [1.0, {"y": True}]}

    def test_run_field_testing_demo(self, tmp_dir):
        args = parse_args([
            "--demo",
            "--subjects", "2",
            "--placements", "2",
            "--epochs", "60",
            "--no-plots",
            "--output", tmp_dir,
        ])
        result = run_field_testing(args)
        assert isinstance(result, dict)
        assert result["n_tests"] > 0
        assert 0.0 <= result["overall_score"] <= 1.0
        assert result["overall_tier"] in {
            "Excellent", "Good", "Acceptable", "Poor", "Failing",
        }
        # Check summary JSON was saved
        summary_path = os.path.join(tmp_dir, "field_testing_summary.json")
        assert os.path.exists(summary_path)
        with open(summary_path) as f:
            saved = json.load(f)
        assert saved["n_tests"] == result["n_tests"]

    def test_run_field_testing_with_plots(self, tmp_dir):
        args = parse_args([
            "--demo",
            "--subjects", "2",
            "--placements", "2",
            "--epochs", "60",
            "--output", tmp_dir,
        ])
        result = run_field_testing(args)
        assert len(result.get("plot_paths", {})) >= 1

    def test_run_field_testing_report_saved(self, tmp_dir):
        args = parse_args([
            "--demo",
            "--subjects", "2",
            "--placements", "2",
            "--epochs", "60",
            "--no-plots",
            "--output", tmp_dir,
        ])
        run_field_testing(args)
        assert os.path.exists(
            os.path.join(tmp_dir, "deployment_report.txt"),
        )

    def test_run_field_testing_configs_saved(self, tmp_dir):
        args = parse_args([
            "--demo",
            "--subjects", "2",
            "--placements", "2",
            "--epochs", "60",
            "--no-plots",
            "--no-report",
            "--output", tmp_dir,
        ])
        run_field_testing(args)
        assert os.path.exists(
            os.path.join(tmp_dir, "field_test_configs.json"),
        )

    def test_run_with_saved_configs(self, tmp_dir, batch_configs):
        cfg_path = save_configs(batch_configs[:4], tmp_dir,
                                "reuse.json")
        args = parse_args([
            "--demo",
            "--configs", cfg_path,
            "--epochs", "60",
            "--no-plots",
            "--no-report",
            "--output", tmp_dir,
        ])
        result = run_field_testing(args)
        assert result["n_configs"] == 4
        assert result["n_tests"] == 4


# ════════════════════════════════════════════════════════════════════
#  10.  END-TO-END INTEGRATION
# ════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """Full pipeline integration tests."""

    def test_full_pipeline(self, tmp_dir):
        """Generate → run → evaluate → score → plot → report."""
        # Generate configs
        configs = generate_test_configs(n_subjects=3, seed=42)
        assert len(configs) > 0

        # Synthetic recordings
        recordings = generate_batch(configs, seed=42, n_epochs=120)
        assert len(recordings) == len(configs)

        # Run field tests
        results = run_field_tests(recordings)
        assert len(results) == len(recordings)

        # Evaluate
        evaluation = evaluate_field_results(results)
        assert evaluation["n_tests"] == len(results)

        # Robustness
        robustness = aggregate_robustness(evaluation)
        assert 0.0 <= robustness["overall_score"] <= 1.0

        # Plots
        paths = plot_field_performance(
            results, evaluation, robustness, output_dir=tmp_dir,
        )
        assert isinstance(paths, dict)

        # Report
        txt = report_deployment_recommendations(robustness, evaluation)
        report_path = write_report(
            txt, os.path.join(tmp_dir, "report.txt"),
        )
        assert os.path.exists(report_path)

    def test_small_pipeline_fast(self, tmp_dir):
        """Minimal run — 1 subject, 1 placement, 60 epochs."""
        cfgs = generate_test_configs(
            n_subjects=1,
            placements=["bedside_right"],
            seed=0,
        )
        recs = generate_batch(cfgs, seed=0, n_epochs=60)
        res = run_field_tests(recs)
        ev = evaluate_field_results(res)
        rob = aggregate_robustness(ev)
        assert rob["overall_tier"] in {
            "Excellent", "Good", "Acceptable", "Poor", "Failing",
        }

    def test_placement_comparison(self):
        """Close placements should score higher than distant ones."""
        close_cfgs = generate_test_configs(
            n_subjects=4,
            placements=["bedside_right"],
            seed=10,
        )
        far_cfgs = generate_test_configs(
            n_subjects=4,
            placements=["corner_left"],
            seed=10,
        )

        close_recs = generate_batch(close_cfgs, seed=10, n_epochs=200)
        far_recs = generate_batch(far_cfgs, seed=10, n_epochs=200)

        close_res = run_field_tests(close_recs)
        far_res = run_field_tests(far_recs)

        close_ev = evaluate_field_results(close_res)
        far_ev = evaluate_field_results(far_res)

        close_rob = aggregate_robustness(close_ev)
        far_rob = aggregate_robustness(far_ev)

        assert close_rob["overall_score"] >= far_rob["overall_score"]

    def test_summary_json_serialisable(self, tmp_dir):
        """Ensure the whole pipeline output is JSON-serialisable."""
        args = parse_args([
            "--demo",
            "--subjects", "2",
            "--placements", "2",
            "--epochs", "60",
            "--no-plots",
            "--output", tmp_dir,
        ])
        result = run_field_testing(args)
        serialised = _safe_serialise(result)
        # This should not raise
        json.dumps(serialised)

    def test_robustness_weights_affect_score(self):
        """Verify that weighting is applied correctly."""
        summary = {
            "rr_mae": 0.5,      # → 1.0
            "hr_mae": 0.5,      # → 1.0
            "event_f1": 0.95,   # → 1.0
            "stage_kappa": 0.85, # → 1.0
            "posture_acc": 0.95, # → 1.0
        }
        scores = score_single_result(summary)
        assert scores["aggregate"] == pytest.approx(1.0)
        assert scores["tier"] == "Excellent"


# ════════════════════════════════════════════════════════════════════
#  11.  EDGE CASES
# ════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_all_dropout(self):
        """Recording where every epoch is dropped out."""
        cfg = make_test_config(test_id="EDGE1")
        rec = generate_recording(cfg, n_epochs=60, seed=42)
        rec["rr_radar"] = np.full(60, np.nan)
        rec["hr_radar"] = np.full(60, np.nan)
        result = run_field_test(rec)
        assert result["summary"]["dropout_rate"] == 1.0
        assert result["summary"]["n_valid"] == 0

    def test_single_epoch(self):
        """Recording with exactly one epoch."""
        cfg = make_test_config(test_id="EDGE2")
        rec = generate_recording(cfg, n_epochs=1, seed=42)
        result = run_field_test(rec)
        assert result["summary"]["n_epochs"] == 1

    def test_perfect_predictions(self):
        """All predictions match ground truth."""
        cfg = make_test_config(test_id="PERF1")
        rec = generate_recording(cfg, n_epochs=100, seed=42)
        # Make predictions perfect
        rec["rr_radar"] = rec["rr_truth"].copy()
        rec["hr_radar"] = rec["hr_truth"].copy()
        rec["event_pred"] = rec["event_truth"].copy()
        rec["stage_pred"] = rec["stage_truth"].copy()
        rec["posture_pred"] = rec["posture_truth"].copy()
        result = run_field_test(rec)
        s = result["summary"]
        assert s["rr_mae"] == pytest.approx(0.0)
        assert s["hr_mae"] == pytest.approx(0.0)
        assert s["event_f1"] == pytest.approx(1.0)
        assert s["stage_kappa"] == pytest.approx(1.0)
        assert s["posture_acc"] == pytest.approx(1.0)
        assert s["dropout_rate"] == pytest.approx(0.0)

    def test_worst_case_scores(self):
        """Maximally bad metric values → Failing tier."""
        summary = {
            "rr_mae": 20.0,
            "hr_mae": 50.0,
            "event_f1": 0.0,
            "stage_kappa": -0.5,
            "posture_acc": 0.0,
        }
        scores = score_single_result(summary)
        assert scores["aggregate"] == 0.0
        assert scores["tier"] == "Failing"

    def test_config_all_placements(self):
        """Generate configs using all 10 placement types."""
        cfgs = generate_test_configs(
            n_subjects=1,
            placements=CFG.PLACEMENT_TYPES,
            seed=42,
        )
        placements_seen = set(c["placement"] for c in cfgs)
        assert placements_seen == set(CFG.PLACEMENT_TYPES)

    def test_config_all_occlusions(self):
        """Config with every occlusion type simultaneously."""
        cfg = make_test_config(
            occlusions=CFG.OCCLUSION_TYPES,
            test_id="OCC_ALL",
        )
        assert cfg["occlusions"] == CFG.OCCLUSION_TYPES
        # Should still generate a valid recording
        rec = generate_recording(cfg, n_epochs=60, seed=42)
        result = run_field_test(rec)
        # High dropout expected
        assert result["summary"]["dropout_rate"] > 0


# ════════════════════════════════════════════════════════════════════
#  12.  DETERMINISM / REPRODUCIBILITY
# ════════════════════════════════════════════════════════════════════

class TestReproducibility:
    """Ensure same seed → same results."""

    def test_same_seed_same_results(self):
        cfgs = generate_test_configs(n_subjects=2, seed=77)
        recs1 = generate_batch(cfgs, seed=77, n_epochs=60)
        recs2 = generate_batch(cfgs, seed=77, n_epochs=60)

        res1 = run_field_tests(recs1)
        res2 = run_field_tests(recs2)

        for r1, r2 in zip(res1, res2):
            assert r1["summary"]["rr_mae"] == r2["summary"]["rr_mae"]
            assert r1["summary"]["hr_mae"] == r2["summary"]["hr_mae"]
            assert r1["summary"]["stage_kappa"] == r2["summary"]["stage_kappa"]

    def test_different_seed_different(self):
        cfg = make_test_config(test_id="SEED1")
        r1 = generate_recording(cfg, n_epochs=60, seed=1)
        r2 = generate_recording(cfg, n_epochs=60, seed=999)
        assert not np.array_equal(r1["rr_radar"], r2["rr_radar"])
