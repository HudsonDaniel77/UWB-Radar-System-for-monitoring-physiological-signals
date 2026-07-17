"""
ml_enhanced/hyperparameter_tuning.py
────────────────────────────────────
Grid search and Bayesian optimisation for classical ML models.

Deep-learning models use Keras callbacks (early stopping, LR
scheduling) instead of external HPO.
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional

from sklearn.model_selection import GridSearchCV, StratifiedKFold

from . import config as CFG
from .models.classical import build_classical_model

# Optional: scikit-optimize for Bayesian search
try:
    from skopt import BayesSearchCV  # type: ignore
    from skopt.space import Integer, Real, Categorical  # type: ignore
    _HAS_SKOPT = True
except ImportError:
    _HAS_SKOPT = False


# ────────────────────────────────────────────────────────────────────
#  DEFAULT PARAM GRIDS
# ────────────────────────────────────────────────────────────────────

PARAM_GRIDS = {
    "random_forest": {
        "model__n_estimators": [200, 400, 600],
        "model__max_depth":    [10, 20, 30, None],
        "model__min_samples_leaf": [2, 4, 8],
    },
    "svm": {
        "model__C":      [1, 10, 100],
        "model__kernel": ["rbf", "poly"],
        "model__gamma":  ["scale", "auto"],
    },
    "xgboost": {
        "model__n_estimators":  [200, 400, 600],
        "model__max_depth":     [4, 6, 8, 12],
        "model__learning_rate": [0.01, 0.05, 0.10],
        "model__subsample":     [0.8, 0.9, 1.0],
    },
}

BAYES_SPACES = {
    "random_forest": {
        "model__n_estimators":     Integer(100, 800),
        "model__max_depth":        Integer(5, 40),
        "model__min_samples_leaf": Integer(1, 10),
    },
    "svm": {
        "model__C":     Real(0.1, 100, prior="log-uniform"),
        "model__gamma": Categorical(["scale", "auto"]),
    },
    "xgboost": {
        "model__n_estimators":  Integer(100, 800),
        "model__max_depth":     Integer(3, 15),
        "model__learning_rate": Real(0.005, 0.3, prior="log-uniform"),
        "model__subsample":     Real(0.6, 1.0),
    },
} if _HAS_SKOPT else {}


# ────────────────────────────────────────────────────────────────────
#  GRID SEARCH
# ────────────────────────────────────────────────────────────────────

def grid_search(
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    param_grid: Optional[Dict] = None,
    cv: int = CFG.TUNING_CV_FOLDS,
    scoring: str = "f1_macro",
    seed: int = CFG.RANDOM_SEED,
    n_classes: int = 2,
    **kwargs,
) -> Dict:
    """
    Run grid-search cross-validation for *model_type*.

    Returns dict with best_params, best_score, cv_results.
    """
    model = build_classical_model(model_type, n_classes=n_classes, seed=seed)
    pipeline = model.pipeline

    if param_grid is None:
        param_grid = PARAM_GRIDS.get(model_type, {})

    if not param_grid:
        return {"best_params": {}, "best_score": 0.0, "error": "no param grid"}

    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=seed)
    gs = GridSearchCV(
        pipeline,
        param_grid,
        cv=skf,
        scoring=scoring,
        refit=True,
        n_jobs=-1,
        verbose=0,
    )
    gs.fit(X, y)

    return {
        "model_type":  model_type,
        "best_params": gs.best_params_,
        "best_score":  round(float(gs.best_score_), 4),
        "best_model":  gs.best_estimator_,
        "cv_results":  _summarise_cv(gs.cv_results_),
    }


# ────────────────────────────────────────────────────────────────────
#  BAYESIAN SEARCH  (requires scikit-optimize)
# ────────────────────────────────────────────────────────────────────

def bayesian_search(
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    search_space: Optional[Dict] = None,
    n_iter: int = CFG.TUNING_N_ITER,
    cv: int = CFG.TUNING_CV_FOLDS,
    scoring: str = "f1_macro",
    seed: int = CFG.RANDOM_SEED,
    n_classes: int = 2,
    **kwargs,
) -> Dict:
    """
    Bayesian hyper-parameter optimisation via ``BayesSearchCV``.

    Falls back to grid search if scikit-optimize is not installed.
    """
    if not _HAS_SKOPT:
        return grid_search(model_type, X, y, cv=cv, scoring=scoring,
                           seed=seed, n_classes=n_classes, **kwargs)

    model = build_classical_model(model_type, n_classes=n_classes, seed=seed)
    pipeline = model.pipeline

    if search_space is None:
        search_space = BAYES_SPACES.get(model_type, {})
    if not search_space:
        return {"best_params": {}, "best_score": 0.0,
                "error": "no search space"}

    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=seed)
    bs = BayesSearchCV(
        pipeline,
        search_space,
        n_iter=n_iter,
        cv=skf,
        scoring=scoring,
        refit=True,
        n_jobs=-1,
        verbose=0,
        random_state=seed,
    )
    bs.fit(X, y)

    return {
        "model_type":  model_type,
        "best_params": dict(bs.best_params_),
        "best_score":  round(float(bs.best_score_), 4),
        "best_model":  bs.best_estimator_,
        "cv_results":  _summarise_cv(bs.cv_results_),
    }


# ────────────────────────────────────────────────────────────────────
#  UNIFIED ENTRY POINT
# ────────────────────────────────────────────────────────────────────

def tune_model(
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    method: str = CFG.TUNING_METHOD,
    **kwargs,
) -> Dict:
    """
    Tune hyper-parameters using either grid or Bayesian search.
    """
    method = method.lower()
    if method == "bayesian":
        return bayesian_search(model_type, X, y, **kwargs)
    return grid_search(model_type, X, y, **kwargs)


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _summarise_cv(cv_results: Dict) -> List[Dict]:
    """Extract a small summary from sklearn's cv_results_ dict."""
    rows: List[Dict] = []
    n = len(cv_results.get("params", []))
    for i in range(min(n, 20)):         # keep top 20
        rows.append({
            "params":    cv_results["params"][i],
            "mean_score": round(float(cv_results["mean_test_score"][i]), 4),
            "std_score":  round(float(cv_results["std_test_score"][i]), 4),
            "rank":       int(cv_results["rank_test_score"][i]),
        })
    rows.sort(key=lambda r: r["rank"])
    return rows
