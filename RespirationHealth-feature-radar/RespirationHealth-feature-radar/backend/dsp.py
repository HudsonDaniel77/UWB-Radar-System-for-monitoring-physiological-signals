import numpy as np
from scipy import signal

def remove_static_clutter(complex_data):
    """
    MTI Filtering: Subtracts the mean (clutter) from the signal.
    """
    return complex_data - np.mean(complex_data, axis=0)

def extract_phase(complex_value):
    """Returns the phase of a complex number."""
    return np.angle(complex_value)

def unwrap_phase(phase_array):
    """Unwraps phase to remove 2pi jumps."""
    return np.unwrap(phase_array)

def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(data, lowcut, highcut, fs, order=2):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = signal.lfilter(b, a, data)
    return y

def get_fft_spectrum(time_signal, fs):
    """
    Computes the FFT magnitude spectrum.
    """
    n = len(time_signal)
    if n < 8: return [], []
    
    # Detrend to remove DC
    sig = signal.detrend(time_signal)
    
    # Apply Hanning window
    win = np.hanning(n)
    sig = sig * win
    
    freqs = np.fft.rfftfreq(n, 1/fs)
    fft_mag = np.abs(np.fft.rfft(sig))
    
    return freqs.tolist(), fft_mag.tolist()

def estimate_rate(time_signal, fs, lowcut, highcut):
    """
    Estimates the dominant frequency (bpm) within a specific band.
    """
    n = len(time_signal)
    if n < 32: return 0, 0
    
    # Detrend
    time_signal = signal.detrend(time_signal)
    
    # FFT
    freqs = np.fft.rfftfreq(n, 1/fs)
    fft_mag = np.abs(np.fft.rfft(time_signal))
    
    # Filter frequencies to the band of interest
    mask = (freqs >= lowcut) & (freqs <= highcut)
    if not np.any(mask): return 0, 0
    
    masked_freqs = freqs[mask]
    masked_mag = fft_mag[mask]
    
    peak_idx = np.argmax(masked_mag)
    dominant_freq = masked_freqs[peak_idx]
    
    # SNR calculation (Ratio of peak power to mean power in the band)
    snr = masked_mag[peak_idx] / (np.mean(fft_mag) + 1e-6)
    
    return int(dominant_freq * 60), snr
