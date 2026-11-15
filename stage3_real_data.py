import sys
import urllib.request
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat
from scipy.signal import butter, filtfilt, hilbert

RECORDINGS = [
    ("97.mat", "healthy", 48_000),
    ("105.mat", "inner ring damage", 12_000),
    ("130.mat", "outer ring damage", 12_000),
    ("118.mat", "ball damage", 12_000),
]
HIT_RATE_PER_TURN = {
    "outer ring": 3.5848,
    "inner ring": 5.4152,
    "ball": 4.7135,
}

ALARM_LEVEL = 8

DATA_FOLDER = Path(__file__).parent / "data"
DOWNLOAD_FROM = "https://engineering.case.edu/sites/default/files/"


def get_file(name):
    path = DATA_FOLDER / name
    if path.exists():
        return path
    DATA_FOLDER.mkdir(exist_ok=True)
    print(f"Downloading {name} ...")
    try:
        request = urllib.request.Request(DOWNLOAD_FROM + name, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as reply:
            path.write_bytes(reply.read())
    except Exception as problem:
        print(f"\nCould not download {name} ({problem}).")
        print("Download it in your browser from:")
        print(f"  {DOWNLOAD_FROM}{name}")
        print(f"Then put it in this folder and run again:\n  {DATA_FOLDER}")
        sys.exit(1)
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
    b, a = butter(4, [2000, 5000], btype="bandpass", fs=sample_rate)
    ringing_only = filtfilt(b, a, signal)
    envelope = np.abs(hilbert(ringing_only))
    envelope = envelope - np.mean(envelope)
    strength = np.abs(np.fft.rfft(envelope)) / len(envelope)
    freqs = np.fft.rfftfreq(len(envelope), 1 / sample_rate)
    in_range = (freqs >= 20) & (freqs <= 500)
    return freqs, strength / np.median(strength[in_range])


def check_each_part(freqs, stands_out, rpm):
    turns_per_second = rpm / 60
    results = {}
    for part, per_turn in HIT_RATE_PER_TURN.items():
        expected = per_turn * turns_per_second
        window = (freqs >= expected * 0.985) & (freqs <= expected * 1.015)
        results[part] = (expected, stands_out[window].max())
    return results


def diagnose(results):
    over_alarm = [part for part, (_, score) in results.items() if score >= ALARM_LEVEL]
    if len(over_alarm) == 0:
        return "healthy"
    if len(over_alarm) == 1:
        return over_alarm[0] + " damage"
    return "damaged, part unclear"


def grade(truth, answer):
    if answer == truth:
        return "yes"
    if truth != "healthy" and answer != "healthy":
        return "partly"
    return "no"


print(f"{'File':<9}{'Truth':<20}{'Shake':>6}{'Spiky':>7}{'Outer':>8}{'Inner':>8}{'Ball':>7}   {'App says':<23}Right?")
panels = []
for name, truth, sample_rate in RECORDINGS:
    signal, rpm = load_recording(get_file(name))
    shake = np.sqrt(np.mean(signal ** 2))
    centered = signal - np.mean(signal)
    spiky = np.mean(centered ** 4) / np.mean(centered ** 2) ** 2
    freqs, stands_out = envelope_spectrum(signal, sample_rate)
    results = check_each_part(freqs, stands_out, rpm)
    answer = diagnose(results)
    scores = "".join(f"{results[part][1]:>7.0f}x" for part in HIT_RATE_PER_TURN)
    print(f"{name:<9}{truth:<20}{shake:>6.2f}{spiky:>7.1f}{scores}   {answer:<23}{grade(truth, answer)}")
    panels.append((name, truth, answer, freqs, stands_out, results))

print(f"\nOuter, Inner and Ball show how many times the pulse stands above the background.")
print(f"Anything at {ALARM_LEVEL}x or more counts as damage.")

MARKER_STYLE = {
    "outer ring": ("#2a78d6", "-"),
    "inner ring": ("#eb6834", "--"),
    "ball": ("#1baf7a", ":"),
}
fig, axes = plt.subplots(2, 2, figsize=(12, 7.5))
for ax, (name, truth, answer, freqs, stands_out, results) in zip(axes.ravel(), panels):
    show = freqs <= 250
    for part, (expected, score) in results.items():
        color, dashes = MARKER_STYLE[part]
        ax.axvline(expected, color=color, linestyle=dashes, linewidth=1.6, label=f"{part} hit rate")
        if score >= ALARM_LEVEL:
            ax.annotate(
                f"{part}: {score:.0f}x",
                xy=(expected, score),
                xytext=(6, -2),
                textcoords="offset points",
                color="#0b0b0b",
                va="top",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.5),
            )
    ax.plot(freqs[show], stands_out[show], color="#3a3a38", linewidth=0.9)
    ax.set_title(f"{name}   Truth: {truth}\nApp says: {answer}", fontsize=10, loc="left")
    ax.set_xlim(0, 250)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Pulses per second (Hz)")
    ax.set_ylabel("Times above background")
    ax.spines[["top", "right"]].set_visible(False)

handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
fig.suptitle("Where each recording pulses, compared with the three expected hit rates")
plt.tight_layout(rect=(0, 0.05, 1, 0.97))
plt.savefig("stage3_diagnosis.png", dpi=120)
print("Saved chart to stage3_diagnosis.png")
plt.show()
