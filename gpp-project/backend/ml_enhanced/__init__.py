"""
ml_enhanced
───────────
Advanced Machine Learning & Deep Learning enhancement pipeline for
radar-based sleep diagnostics.

Modules
───────
config                 – hyper-parameters, feature lists, model defaults
feature_engineering    – normalisation, HRV / RRV, spectral features
dataset                – data loading, windowing, stratified splits
models/                – classical ML + deep learning architectures
training               – training loops, cross-validation, early stopping
evaluation             – metrics, comparison tables, ROC curves
hyperparameter_tuning  – grid search / Bayesian optimisation
inference              – load model → predict enhanced events
visualize              – dark-themed publication-ready plots
run_training           – CLI entry-point
"""
