# Wind turbine high-speed shaft bearing monitoring.
#
# Data: 2 MW wind turbine, high-speed shaft bearing, one 6 s vibration
# recording per day for 50 days (97,656 Hz). An inner race fault developed
# and the bearing failed. Source: Eric Bechhoefer / GPMS via MathWorks,
# CC BY-NC-SA 4.0.
#
# The raw files are ~215 MB, so build_features() turns them into a small
# wind_features.npz that the app loads.

import glob
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.signal import butter, filtfilt, hilbert

FS = 97_656
BAND = (4_000, 20_000)

# Bearing geometry isn't published, so the inner race fault order was found
# from the data: a peak at ~9.32x shaft speed with 1x shaft sidebands that
# grows as the bearing degrades.
INNER_RACE_ORDER = 9.32

# Alarm logic works on the median of the last 3 days so one noisy
# recording doesn't flip the status.
WATCH_LEVEL = 8
ALARM_LEVEL = 12
SMOOTH_DAYS = 3

SPECTRUM_MAX_HZ = 600
FEATURES_FILE = Path(__file__).parent / "wind_features.npz"


def features(vibration, tach):
    # Tach gives 2 pulses per shaft revolution. Only use pulses that overlap
    # the 6 s vibration recording.
    pulses = tach[tach <= len(vibration) / FS]
    shaft_hz = 1 / np.diff(pulses).mean() / 2

    b, a = butter(4, BAND, btype="bandpass", fs=FS)
    envelope = np.abs(hilbert(filtfilt(b, a, vibration)))
    envelope = envelope - envelope.mean()
    strength = np.abs(np.fft.rfft(envelope * np.hanning(len(envelope))))
    freqs = np.fft.rfftfreq(len(envelope), 1 / FS)

    keep = freqs <= SPECTRUM_MAX_HZ
    background = np.median(strength[(freqs >= 5) & keep])
    spectrum = strength[keep] / background

    fault_hz = INNER_RACE_ORDER * shaft_hz
    window = (freqs[keep] >= fault_hz * 0.985) & (freqs[keep] <= fault_hz * 1.015)

    centered = vibration - vibration.mean()
    return {
        "shaft_hz": shaft_hz,
        "rms": float(np.sqrt(np.mean(vibration ** 2))),
        "kurtosis": float(np.mean(centered ** 4) / np.mean(centered ** 2) ** 2),
        "ir_score": float(spectrum[window].max()),
        "spectrum": spectrum.astype(np.float32),
        "freqs": freqs[keep],
    }


def build_features(data_folder):
    files = sorted(glob.glob(str(Path(data_folder) / "data-*.mat")))
    rows = [features(m["vibration"].ravel(), m["tach"].ravel()) for m in map(loadmat, files)]
    np.savez_compressed(
        FEATURES_FILE,
        dates=np.array([Path(f).stem[5:13] for f in files]),
        shaft_hz=np.array([r["shaft_hz"] for r in rows]),
        rms=np.array([r["rms"] for r in rows]),
        kurtosis=np.array([r["kurtosis"] for r in rows]),
        ir_score=np.array([r["ir_score"] for r in rows]),
        freqs=rows[0]["freqs"],
        spectra=np.array([r["spectrum"][: len(rows[0]["freqs"])] for r in rows]),
    )


def load_features():
    data = dict(np.load(FEATURES_FILE))
    scores = data["ir_score"]
    data["smoothed"] = np.array(
        [np.median(scores[max(0, i - SMOOTH_DAYS + 1): i + 1]) for i in range(len(scores))]
    )
    data["day"] = np.arange(1, len(scores) + 1)
    return data


def first_alarm_day(data):
    # Alarm once the smoothed score is over ALARM_LEVEL two days in a row.
    # After that it stays in alarm, the same way a case stays open.
    over = data["smoothed"] >= ALARM_LEVEL
    for i in range(1, len(over)):
        if over[i] and over[i - 1]:
            return int(data["day"][i])
    return None


def status_on(data, day):
    alarm_day = first_alarm_day(data)
    if alarm_day is not None and day >= alarm_day:
        return "inner race fault"
    i = day - 1
    recent_peak = data["ir_score"][max(0, i - SMOOTH_DAYS + 1): i + 1].max()
    if data["smoothed"][i] >= WATCH_LEVEL or recent_peak >= ALARM_LEVEL:
        return "watch"
    return "healthy"


if __name__ == "__main__":
    # Download the raw data first:
    # git clone https://github.com/mathworks/WindTurbineHighSpeedBearingPrognosis-Data
    import sys
    build_features(sys.argv[1])
    print("Saved", FEATURES_FILE)
