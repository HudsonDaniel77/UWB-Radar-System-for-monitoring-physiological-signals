"""
UWB Radar-based Vital Sign Monitoring System - Research-Grade Visualization
IEEE Paper Publication Format
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal

# ============================================================================
# SYNTHETIC DATA GENERATION
# ============================================================================

def generate_synthetic_data(duration=300, fs=100):
    """
    Generate realistic synthetic radar data with reference measurements.
    
    Parameters:
    - duration: Data collection duration in seconds
    - fs: Sampling frequency in Hz
    """
    t = np.arange(0, duration, 1/fs)
    n_samples = len(t)
    
    # True vital signs (varying over time)
    true_hr = 70 + 5 * np.sin(2 * np.pi * t / 60)  # 70 ± 5 bpm
    true_rr = 15 + 2 * np.sin(2 * np.pi * t / 120)  # 15 ± 2 breaths/min
    
    # Raw radar signal (combination of heart rate and respiration harmonics)
    hr_freq = true_hr / 60  # Convert bpm to Hz
    rr_freq = true_rr / 60  # Convert breaths/min to Hz
    
    raw_signal = (
        1.0 * np.sin(2 * np.pi * hr_freq * t) +  # HR component
        3.0 * np.sin(2 * np.pi * rr_freq * t) +  # RR component
        0.5 * np.random.randn(n_samples)  # Noise
    )
    
    # Apply low-pass filter
    sos = signal.butter(4, 2, 'low', fs=fs, output='sos')
    filtered_signal = signal.sosfilt(sos, raw_signal)
    
    # Radar estimates with estimation error
    hr_radar = true_hr + np.random.randn(n_samples) * 2  # ±2 bpm noise
    rr_radar = true_rr + np.random.randn(n_samples) * 0.5  # ±0.5 bpm noise
    
    # Reference sensor (gold standard)
    hr_reference = true_hr + np.random.randn(n_samples) * 0.5  # ±0.5 bpm noise
    rr_reference = true_rr + np.random.randn(n_samples) * 0.2  # ±0.2 bpm noise
    
    # Distance (simulating subject movement)
    distance = 1.5 + 0.3 * np.sin(2 * np.pi * t / 120)
    
    # Signal Quality Index (0-1)
    sqi = 0.8 + 0.1 * np.cos(2 * np.pi * t / 180) - 0.05 * np.abs(distance - 1.5)
    sqi = np.clip(sqi, 0, 1)
    
    # Create DataFrame
    df = pd.DataFrame({
        'time': t,
        'raw_signal': raw_signal,
        'filtered_signal': filtered_signal,
        'heart_rate_radar': hr_radar,
        'heart_rate_reference': hr_reference,
        'respiration_rate_radar': rr_radar,
        'respiration_rate_reference': rr_reference,
        'distance': distance,
        'sqi': sqi
    })
    
    return df


# ============================================================================
# PLOT 1: RAW VS FILTERED SIGNAL
# ============================================================================

def plot_raw_vs_filtered(df):
    """Plot raw and filtered signals in two subplots."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 6))
    
    # Raw signal
    axes[0].plot(df['time'], df['raw_signal'], linewidth=1)
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Amplitude (mV)')
    axes[0].set_title('Raw Radar Signal')
    axes[0].grid(True, alpha=0.3)
    
    # Filtered signal
    axes[1].plot(df['time'], df['filtered_signal'], linewidth=1)
    axes[1].set_xlabel('Time (s)')
    axes[1].set_ylabel('Amplitude (mV)')
    axes[1].set_title('Filtered Radar Signal')
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 2: FFT SPECTRUM PLOT
# ============================================================================

def plot_fft_spectrum(df, fs=100):
    """Compute and plot FFT of filtered signal."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    signal_data = df['filtered_signal'].values
    n_fft = len(signal_data)
    freqs = np.fft.fftfreq(n_fft, 1/fs)
    magnitude = np.abs(np.fft.fft(signal_data))
    
    # Use only positive frequencies
    positive_idx = freqs > 0
    freqs = freqs[positive_idx]
    magnitude = magnitude[positive_idx]
    
    # Convert to Hz and normalize
    magnitude = magnitude / np.max(magnitude)
    
    ax.plot(freqs, magnitude, linewidth=1)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Normalized Magnitude')
    ax.set_title('FFT Spectrum of Filtered Signal')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 3])
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 3: FEATURE EXTRACTION VISUALIZATION
# ============================================================================

def plot_feature_extraction(df, fs=100):
    """Show peak detection on FFT spectrum."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    signal_data = df['filtered_signal'].values
    n_fft = len(signal_data)
    freqs = np.fft.fftfreq(n_fft, 1/fs)
    magnitude = np.abs(np.fft.fft(signal_data))
    
    # Positive frequencies only
    positive_idx = freqs > 0
    freqs = freqs[positive_idx]
    magnitude = magnitude[positive_idx]
    magnitude = magnitude / np.max(magnitude)
    
    # Detect peaks
    peaks, _ = signal.find_peaks(magnitude, height=0.1, distance=10)
    
    ax.plot(freqs, magnitude, linewidth=1, label='FFT Magnitude')
    ax.plot(freqs[peaks], magnitude[peaks], marker='o', linestyle='none', 
            markersize=6, label='Detected Peaks')
    
    # Annotate expected HR and RR ranges
    ax.axvline(df['heart_rate_radar'].mean() / 60, color='gray', 
               linestyle='--', alpha=0.5, label='Mean HR Freq')
    ax.axvline(df['respiration_rate_radar'].mean() / 60, color='gray', 
               linestyle=':', alpha=0.5, label='Mean RR Freq')
    
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Normalized Magnitude')
    ax.set_title('Feature Extraction: Peak Detection in FFT Spectrum')
    ax.set_xlim([0, 3])
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 4: HEART RATE COMPARISON
# ============================================================================

def plot_heart_rate_comparison(df):
    """Plot radar vs reference heart rate over time."""
    fig, ax = plt.subplots(figsize=(12, 5))
    
    ax.plot(df['time'], df['heart_rate_radar'], label='Radar Estimate', 
            linewidth=1.5, alpha=0.8)
    ax.plot(df['time'], df['heart_rate_reference'], label='Reference (ECG)', 
            linewidth=1.5, alpha=0.8)
    
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Heart Rate (bpm)')
    ax.set_title('Heart Rate: Radar vs Reference')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 5: RESPIRATION RATE COMPARISON
# ============================================================================

def plot_respiration_rate_comparison(df):
    """Plot radar vs reference respiration rate over time."""
    fig, ax = plt.subplots(figsize=(12, 5))
    
    ax.plot(df['time'], df['respiration_rate_radar'], label='Radar Estimate', 
            linewidth=1.5, alpha=0.8)
    ax.plot(df['time'], df['respiration_rate_reference'], label='Reference', 
            linewidth=1.5, alpha=0.8)
    
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Respiration Rate (breaths/min)')
    ax.set_title('Respiration Rate: Radar vs Reference')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 6: ERROR DISTRIBUTION HISTOGRAM
# ============================================================================

def plot_error_histogram(df):
    """Plot histogram of heart rate estimation errors."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    hr_error = df['heart_rate_radar'] - df['heart_rate_reference']
    
    ax.hist(hr_error, bins=30, edgecolor='black', alpha=0.7)
    ax.axvline(hr_error.mean(), color='red', linestyle='--', 
               linewidth=2, label=f'Mean: {hr_error.mean():.2f} bpm')
    ax.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    
    ax.set_xlabel('Heart Rate Error (Radar - Reference) [bpm]')
    ax.set_ylabel('Frequency')
    ax.set_title('Heart Rate Estimation Error Distribution')
    ax.grid(True, alpha=0.3, axis='y')
    ax.legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 7: BLAND-ALTMAN PLOT
# ============================================================================

def plot_bland_altman(df):
    """Bland-Altman plot for heart rate agreement analysis."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    hr_radar = df['heart_rate_radar'].values
    hr_ref = df['heart_rate_reference'].values
    
    mean_hr = (hr_radar + hr_ref) / 2
    diff_hr = hr_radar - hr_ref
    
    # Calculate statistics
    mean_diff = np.mean(diff_hr)
    std_diff = np.std(diff_hr)
    upper_limit = mean_diff + 1.96 * std_diff
    lower_limit = mean_diff - 1.96 * std_diff
    
    # Plot
    ax.scatter(mean_hr, diff_hr, alpha=0.5, s=20)
    ax.axhline(mean_diff, color='red', linestyle='-', linewidth=2, 
               label=f'Mean Bias: {mean_diff:.2f} bpm')
    ax.axhline(upper_limit, color='red', linestyle='--', linewidth=1.5, 
               label=f'+1.96 SD: {upper_limit:.2f}')
    ax.axhline(lower_limit, color='red', linestyle='--', linewidth=1.5, 
               label=f'-1.96 SD: {lower_limit:.2f}')
    ax.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)
    
    ax.set_xlabel('Mean Heart Rate (bpm)')
    ax.set_ylabel('Difference (Radar - Reference) [bpm]')
    ax.set_title('Bland-Altman Plot: Heart Rate Agreement')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 8: DISTANCE VS ACCURACY
# ============================================================================

def plot_distance_vs_accuracy(df):
    """Plot absolute heart rate error vs subject distance."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    abs_error = np.abs(df['heart_rate_radar'] - df['heart_rate_reference'])
    
    ax.scatter(df['distance'], abs_error, alpha=0.5, s=20)
    
    # Fit trend line
    z = np.polyfit(df['distance'], abs_error, 2)
    p = np.poly1d(z)
    x_trend = np.linspace(df['distance'].min(), df['distance'].max(), 100)
    ax.plot(x_trend, p(x_trend), linewidth=2, label='Polynomial Fit')
    
    ax.set_xlabel('Distance (m)')
    ax.set_ylabel('Absolute Heart Rate Error (bpm)')
    ax.set_title('Heart Rate Accuracy vs Distance')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 9: SIGNAL QUALITY INDEX VISUALIZATION
# ============================================================================

def plot_sqi_visualization(df):
    """Plot SQI over time and histogram."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 7))
    
    # SQI over time
    axes[0].plot(df['time'], df['sqi'], linewidth=1)
    axes[0].fill_between(df['time'], df['sqi'], alpha=0.3)
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Signal Quality Index')
    axes[0].set_title('Signal Quality Index Over Time')
    axes[0].set_ylim([0, 1])
    axes[0].grid(True, alpha=0.3)
    
    # SQI histogram
    axes[1].hist(df['sqi'], bins=20, edgecolor='black', alpha=0.7)
    axes[1].axvline(df['sqi'].mean(), color='red', linestyle='--', 
                    linewidth=2, label=f'Mean: {df["sqi"].mean():.3f}')
    axes[1].set_xlabel('Signal Quality Index')
    axes[1].set_ylabel('Frequency')
    axes[1].set_title('Distribution of Signal Quality Index')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 10: LATENCY / PROCESSING TIME
# ============================================================================

def plot_latency_breakdown():
    """Bar chart showing processing time breakdown."""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Simulated processing times (milliseconds)
    stages = ['Signal\nAcquisition', 'Filtering', 'FFT\nComputation', 
              'Peak\nDetection', 'Post-\nProcessing', 'Total']
    times = [5, 8, 15, 12, 10, 50]
    
    colors_default = plt.cm.tab10(np.linspace(0, 1, len(stages)))
    
    bars = ax.bar(stages, times, edgecolor='black', alpha=0.8)
    
    # Add value labels on bars
    for bar, time in zip(bars, times):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{time} ms',
                ha='center', va='bottom', fontsize=9)
    
    ax.set_ylabel('Processing Time (ms)')
    ax.set_title('System Latency Breakdown')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim([0, max(times) * 1.15])
    
    plt.tight_layout()
    return fig


# ============================================================================
# PLOT 11: FAILURE CASE VISUALIZATION
# ============================================================================

def plot_failure_case_comparison(df):
    """Compare clean vs noisy signal segments."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 6))
    
    # Clean segment (high SQI)
    clean_idx = df['sqi'] > 0.85
    clean_time = df.loc[clean_idx, 'time'].values
    clean_signal = df.loc[clean_idx, 'filtered_signal'].values
    
    # Noisy segment (low SQI)
    noisy_idx = df['sqi'] < 0.70
    noisy_time = df.loc[noisy_idx, 'time'].values
    noisy_signal = df.loc[noisy_idx, 'filtered_signal'].values
    
    # Plot clean signal
    if len(clean_time) > 0:
        axes[0].plot(clean_time, clean_signal, linewidth=1)
        axes[0].set_ylabel('Amplitude (mV)')
        axes[0].set_title('Clean Signal Segment (High SQI > 0.85)')
        axes[0].grid(True, alpha=0.3)
    
    # Plot noisy signal
    if len(noisy_time) > 0:
        axes[1].plot(noisy_time, noisy_signal, linewidth=1)
        axes[1].set_xlabel('Time (s)')
        axes[1].set_ylabel('Amplitude (mV)')
        axes[1].set_title('Degraded Signal Segment (Low SQI < 0.70)')
        axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Generate all research-grade plots."""
    print("Generating synthetic data...")
    df = generate_synthetic_data(duration=300, fs=100)
    
    print("Creating plots...")
    
    # Generate all plots
    fig1 = plot_raw_vs_filtered(df)
    fig1.savefig('Raw_vs_Filtered_Signal.png', dpi=300, bbox_inches='tight')
    print("✓ Raw vs Filtered Signal")
    
    fig2 = plot_fft_spectrum(df)
    fig2.savefig('FFT_Spectrum.png', dpi=300, bbox_inches='tight')
    print("✓ FFT Spectrum")
    
    fig3 = plot_feature_extraction(df)
    fig3.savefig('Feature_Extraction.png', dpi=300, bbox_inches='tight')
    print("✓ Feature Extraction")
    
    fig4 = plot_heart_rate_comparison(df)
    fig4.savefig('Heart_Rate_Comparison.png', dpi=300, bbox_inches='tight')
    print("✓ Heart Rate Comparison")
    
    fig5 = plot_respiration_rate_comparison(df)
    fig5.savefig('Respiration_Rate_Comparison.png', dpi=300, bbox_inches='tight')
    print("✓ Respiration Rate Comparison")
    
    fig6 = plot_error_histogram(df)
    fig6.savefig('Error_Histogram.png', dpi=300, bbox_inches='tight')
    print("✓ Error Distribution Histogram")
    
    fig7 = plot_bland_altman(df)
    fig7.savefig('Bland_Altman_Plot.png', dpi=300, bbox_inches='tight')
    print("✓ Bland-Altman Plot")
    
    fig8 = plot_distance_vs_accuracy(df)
    fig8.savefig('Distance_vs_Accuracy.png', dpi=300, bbox_inches='tight')
    print("✓ Distance vs Accuracy")
    
    fig9 = plot_sqi_visualization(df)
    fig9.savefig('Signal_Quality_Index.png', dpi=300, bbox_inches='tight')
    print("✓ Signal Quality Index")
    
    fig10 = plot_latency_breakdown()
    fig10.savefig('Latency_Breakdown.png', dpi=300, bbox_inches='tight')
    print("✓ Processing Time Breakdown")
    
    fig11 = plot_failure_case_comparison(df)
    fig11.savefig('Failure_Case_Visualization.png', dpi=300, bbox_inches='tight')
    print("✓ Failure Case Visualization")
    
    print("\n✓ All plots generated successfully!")
    print("PNG files saved as:")
    print("  - Raw_vs_Filtered_Signal.png")
    print("  - FFT_Spectrum.png")
    print("  - Feature_Extraction.png")
    print("  - Heart_Rate_Comparison.png")
    print("  - Respiration_Rate_Comparison.png")
    print("  - Error_Histogram.png")
    print("  - Bland_Altman_Plot.png")
    print("  - Distance_vs_Accuracy.png")
    print("  - Signal_Quality_Index.png")
    print("  - Latency_Breakdown.png")
    print("  - Failure_Case_Visualization.png")
    
    plt.close('all')


if __name__ == '__main__':
    main()
