import numpy as np
import matplotlib.pyplot as plt

SAMPLE_RATE = 10_000
DURATION = 1.0
SHAFT_SPEED = 30
FAULT_RATE = 107
NOISE = 0.3

t = np.arange(0, DURATION, 1 / SAMPLE_RATE)

rng = np.random.default_rng(seed=1)
shaft = 0.2 * np.sin(2 * np.pi * SHAFT_SPEED * t)
healthy = shaft + NOISE * rng.standard_normal(len(t))

clicks = np.zeros(len(t))
click_times = np.arange(0, DURATION, 1 / FAULT_RATE)
for start in click_times:
    since_click = t - start
    ringing = since_click >= 0
    clicks[ringing] += (
        2.0
        * np.exp(-800 * since_click[ringing])
        * np.sin(2 * np.pi * 3000 * since_click[ringing])
    )
faulty = healthy + clicks

def rms(signal):
    return np.sqrt(np.mean(signal ** 2))

def kurtosis(signal):
    centered = signal - np.mean(signal)
    return np.mean(centered ** 4) / np.mean(centered ** 2) ** 2

print("              RMS    Kurtosis")
print(f"Healthy     {rms(healthy):.2f}      {kurtosis(healthy):.2f}")
print(f"Faulty      {rms(faulty):.2f}      {kurtosis(faulty):.2f}")

show = t < 0.1
fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, sharey=True)

top.plot(t[show], healthy[show], color="tab:green", linewidth=0.8)
top.set_title("Healthy bearing")
top.set_ylabel("Vibration")

bottom.plot(t[show], faulty[show], color="tab:red", linewidth=0.8)
bottom.set_title("Bearing with a damaged spot")
bottom.set_ylabel("Vibration")
bottom.set_xlabel("Time (seconds)")

plt.tight_layout()
plt.savefig("stage1_signals.png", dpi=120)
print("\nSaved chart to stage1_signals.png")
plt.show()
