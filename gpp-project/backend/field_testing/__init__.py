"""
field_testing
─────────────
Real-world field testing & deployment evaluation pipeline for the
Radarix radar-based sleep monitoring system.

Sub-modules
───────────
config           – constants, placement/environment types, scoring thresholds
test_config      – generate / save / load structured test configurations
synthetic_data   – synthetic field-test data for offline development
field_runner     – run_field_test() orchestrator
metrics          – MAE, drift, CI, cross-session agreement
robustness       – per-placement / per-environment / aggregate scoring
visualize        – dark-themed field performance plots
reports          – human-readable deployment recommendations
run_field_testing – CLI entry-point
"""
