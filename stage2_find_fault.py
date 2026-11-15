import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, hilbert

SAMPLE_RATE = 10_000
DURATION = 1.0
TRUE_FAULT_RATE = 107
ALARM_LEVEL = 8


def make_signal(fault_rate=None):
    t = np.arange(0, DURATION, 1 / SAMPLE_RATE)
    rng = np.random.default_rng(seed=1)
    signal = 0.2 * np.sin(2 * np.pi * 30 * t)
    signal = signal + 0.3 * rng.standard_normal(len(t))

    if fault_rate is not None:
        for start in np.arange(0, DURATION, 1 / fault_rate):
            since_click = t - start
            ringing = since_click >= 0
            signal[ringing] += (
                2.0
                * np.exp(-800 * since_click[ringing])
                * np.sin(2 * np.pi * 3000 * since_click[ringing])
            )
    return t, signal


def spectrum(signal):
    strength = np.abs(np.fft.rfft(signal)) / len(signal)
    freqs = np.fft.rfftfreq(len(signal), 1 / SAMPLE_RATE)
    return freqs, strength


def envelope_spectrum(signal):
    b, a = butter(4, [2000, 4000], btype="bandpass", fs=SAMPLE_RATE)
    ringing_only = filtfilt(b, a, signal)
    envelope = np.abs(hilbert(ringing_only))
    envelope = envelope - np.mean(envelope)
    return spectrum(envelope)


def find_fault(signal):
    freqs, strength = envelope_spectrum(signal)
    search = (freqs >= 20) & (freqs <= 500)
    biggest = np.argmax(strength[search])
    peak_freq = freqs[search][biggest]
    stands_out = strength[search][biggest] / np.median(strength[search])
    return peak_freq, stands_out, stands_out > ALARM_LEVEL


t, healthy = make_signal()
t, faulty = make_signal(fault_rate=TRUE_FAULT_RATE)

print("Bearing    Strongest pulse   Stands out by   Result")
for name, signal in [("Healthy", healthy), ("Damaged", faulty)]:
    rate, stands_out, alarm = find_fault(signal)
    result = "FAULT" if alarm else "ok"
    print(f"{name:<10} {rate:>8.0f} Hz      {stands_out:>8.1f}x        {result}")

detected, _, _ = find_fault(faulty)
print(f"\nTrue fault rate: {TRUE_FAULT_RATE} Hz, detected: {detected:.0f} Hz")

fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7))
freqs, strength = spectrum(faulty)
top.plot(freqs, strength, color="tab:gray", linewidth=0.8)
top.set_title("Raw spectrum, damaged bearing")
top.set_xlabel("Frequency (Hz)")
top.set_ylabel("Strength")
freqs_h, strength_h = envelope_spectrum(healthy)
freqs_f, strength_f = envelope_spectrum(faulty)
bottom.plot(freqs_f, strength_f, color="tab:red", linewidth=1.0, label="Damaged")
bottom.plot(freqs_h, strength_h, color="tab:green", linewidth=1.0, label="Healthy")
bottom.axvline(detected, color="black", linestyle="--", linewidth=0.8)
bottom.annotate(
    f"Detected: {detected:.0f} hits per second",
    xy=(detected, strength_f.max()),
    xytext=(detected + 20, strength_f.max() * 0.9),
)
bottom.set_xlim(0, 500)
bottom.set_title("Envelope spectrum")
bottom.set_xlabel("Pulses per second (Hz)")
bottom.set_ylabel("Strength")
bottom.legend()

plt.tight_layout()
plt.savefig("stage2_spectrum.png", dpi=120)
print("Saved chart to stage2_spectrum.png")
plt.show()
