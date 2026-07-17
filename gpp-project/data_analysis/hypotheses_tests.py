"""
Hypothesis Tests for Radar Vital Signs Project

Includes:
  H1: Calibration Shift Test (Paired test)
  H2: HR differences between High vs Low SQI (Group test)
  H3: Association between HR_Class and Stress_Class (Chi-Square)

Outputs JSON dict (printable) for React frontend.
"""

import os
import json
import numpy as np
import pandas as pd
from scipy import stats

BASE_DIR = os.path.dirname(__file__)
FINAL_STATS = os.path.join(BASE_DIR, "final_run_stats.csv")


# ------------------------------------------------------------
# Load Data
# ------------------------------------------------------------
def load_data():
    if not os.path.exists(FINAL_STATS):
        raise FileNotFoundError("final_run_stats.csv not found")

    df = pd.read_csv(FINAL_STATS)

    # Ensure everything is numeric where required
    numeric_cols = [
        "Avg_HR_clean", "Final_Accurate_HR", "SQI"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Avg_HR_clean", "Final_Accurate_HR"])

    return df


# ------------------------------------------------------------
# H1: Calibration Shift Test
# ------------------------------------------------------------
def calibration_shift_test(df):
    before = df["Avg_HR_clean"]
    after = df["Final_Accurate_HR"]

    # Test normality of differences
    diff = after - before
    sh_stat, sh_p = stats.shapiro(diff)

    if sh_p > 0.05:
        stat, p = stats.ttest_rel(after, before)
        method = "paired_t_test"
    else:
        stat, p = stats.wilcoxon(after, before)
        method = "wilcoxon_test"

    interpretation = (
        "Calibration significantly shifted HR values"
        if p < 0.05 else
        "Calibration did NOT significantly shift HR values"
    )

    return {
        "test_name": "Calibration Shift Test",
        "method": method,
        "p_value": float(p),
        "mean_difference": float(diff.mean()),
        "interpretation": interpretation
    }


# ------------------------------------------------------------
# H2: HR vs SQI Group Comparison
# ------------------------------------------------------------
def hr_vs_sqi_test(df):
    df2 = df.dropna(subset=["SQI"])

    df2["SQI_Group"] = df2["SQI"].apply(lambda x: "High" if x >= 200 else "Low")

    high = df2[df2["SQI_Group"] == "High"]["Final_Accurate_HR"]
    low = df2[df2["SQI_Group"] == "Low"]["Final_Accurate_HR"]

    # Normality check
    sh_h = stats.shapiro(high)[1]
    sh_l = stats.shapiro(low)[1]

    if sh_h > 0.05 and sh_l > 0.05:
        stat, p = stats.ttest_ind(high, low)
        method = "independent_t_test"
    else:
        stat, p = stats.mannwhitneyu(high, low)
        method = "mann_whitney_u"

    interpretation = (
        "HR differs significantly between High and Low SQI groups"
        if p < 0.05 else
        "No significant difference between High and Low SQI groups"
    )

    return {
        "test_name": "HR vs SQI Test",
        "method": method,
        "p_value": float(p),
        "mean_High_SQI": float(high.mean() if len(high) > 0 else 0),
        "mean_Low_SQI": float(low.mean() if len(low) > 0 else 0),
        "interpretation": interpretation
    }


# ------------------------------------------------------------
# H3: HR_Class vs Stress_Class Association Test
# ------------------------------------------------------------
def association_hr_stress(df):
    if "HR_Class" not in df.columns or "Stress_Class" not in df.columns:
        return {
            "test_name": "HR vs Stress Chi-Square Test",
            "error": "HR_Class or Stress_Class missing. Train classifier first."
        }

    df3 = df.dropna(subset=["HR_Class", "Stress_Class"])

    table = pd.crosstab(df3["HR_Class"], df3["Stress_Class"])

    chi2, p, dof, exp = stats.chi2_contingency(table)

    interpretation = (
        "HR Class and Stress Class are dependent (associated)"
        if p < 0.05 else
        "HR Class and Stress Class are independent (not associated)"
    )

    return {
        "test_name": "HR Class vs Stress Class Association",
        "method": "chi_square_test",
        "p_value": float(p),
        "degrees_of_freedom": int(dof),
        "interpretation": interpretation,
        "contingency_table": table.to_dict()
    }


# ------------------------------------------------------------
# Run All Tests
# ------------------------------------------------------------
def run_all_tests():
    df = load_data()

    results = {
        "CalibrationShift": calibration_shift_test(df),
        "HR_vs_SQI": hr_vs_sqi_test(df),
        "Association_HR_Stress": association_hr_stress(df)
    }

    return results


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if __name__ == "__main__":
    results = run_all_tests()
    print(json.dumps(results, indent=2))
