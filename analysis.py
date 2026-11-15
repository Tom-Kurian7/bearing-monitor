# Envelope analysis and fault diagnosis for the CWRU drive end bearing recordings.

import urllib.request
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.signal import butter, filtfilt, hilbert

RECORDINGS = {
    "97.mat": {"known": "healthy", "sample_rate": 48_000},
    "105.mat": {"known": "inner ring damage", "sample_rate": 12_000},
    "130.mat": {"known": "outer ring damage", "sample_rate": 12_000},
    "118.mat": {"known": "ball damage", "sample_rate": 12_000},
}

# SKF 6205 fault frequencies as multiples of shaft speed (from CWRU)
HIT_RATE_PER_TURN = {
    "outer ring": 3.5848,
    "inner ring": 5.4152,
    "ball": 4.7135,
}

# A fault peak has to be this many times above the median background to count.
# Picked from these recordings, would need tuning on more data.
ALARM_LEVEL = 8

DATA_FOLDER = Path(__file__).parent / "data"
DOWNLOAD_FROM = "https://engineering.case.edu/sites/default/files/"


def get_file(name):
    path = DATA_FOLDER / name
    if path.exists():
        return path
    DATA_FOLDER.mkdir(exist_ok=True)
    try:
        request = urllib.request.Request(DOWNLOAD_FROM + name, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as reply:
            path.write_bytes(reply.read())
    except Exception as problem:
        raise FileNotFoundError(
            f"Could not download {name}. Download it from "
            f"{DOWNLOAD_FROM}{name} and put it in {DATA_FOLDER}"
        ) from problem
    return path


def load_recording(path):
    contents = loadmat(path)
    signal = None
    rpm = 1797.0
    for name, value in contents.items():
        if name.endswith("_DE_time"):
            signal = value.ravel()
        if name.endswith("RPM"):
            rpm = float(value.ravel()[0])
    return signal, rpm


def envelope_spectrum(signal, sample_rate):
    # Bandpass around the resonance the impacts excite, then demodulate
    # with the Hilbert transform so the envelope pulses at the fault rate.
    b, a = butter(4, [2000, 5000], btype="bandpass", fs=sample_rate)
    ringing_only = filtfilt(b, a, signal)
    envelope = np.abs(hilbert(ringing_only))
    envelope = envelope - np.mean(envelope)
    strength = np.abs(np.fft.rfft(envelope)) / len(envelope)
    freqs = np.fft.rfftfreq(len(envelope), 1 / sample_rate)
    # Normalize to the median background so scores read as "x above background"
    in_range = (freqs >= 20) & (freqs <= 500)
    return freqs, strength / np.median(strength[in_range])


def check_each_part(freqs, stands_out, rpm):
    turns_per_second = rpm / 60
    results = {}
    for part, per_turn in HIT_RATE_PER_TURN.items():
        expected = per_turn * turns_per_second
        # +-1.5% search window since rolling elements slip a little
        window = (freqs >= expected * 0.985) & (freqs <= expected * 1.015)
        results[part] = (expected, float(stands_out[window].max()))
    return results


def diagnose(results):
    # More than one part over the alarm usually means the fault frequency is
    # weak or smeared (common for ball faults), so don't guess the part.
    over_alarm = [part for part, (_, score) in results.items() if score >= ALARM_LEVEL]
    if len(over_alarm) == 0:
        return "healthy"
    if len(over_alarm) == 1:
        return over_alarm[0] + " damage"
    return "damaged, part unclear"


def analyze(name):
    info = RECORDINGS[name]
    signal, rpm = load_recording(get_file(name))
    centered = signal - np.mean(signal)
    freqs, stands_out = envelope_spectrum(signal, info["sample_rate"])
    results = check_each_part(freqs, stands_out, rpm)
    top_part = max(results, key=lambda part: results[part][1])
    return {
        "recording": name,
        "known": info["known"],
        "rpm": rpm,
        "shake": float(np.sqrt(np.mean(signal ** 2))),
        "spiky": float(np.mean(centered ** 4) / np.mean(centered ** 2) ** 2),
        "freqs": freqs,
        "stands_out": stands_out,
        "results": results,
        "finding": diagnose(results),
        "top_part": top_part,
        "top_score": results[top_part][1],
    }
