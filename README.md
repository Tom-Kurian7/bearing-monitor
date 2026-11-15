# Bearing Monitor

A small condition monitoring app. It reads bearing vibration recordings, finds signs of damage, names the damaged part, and tracks each warning as a case in a SQL database.

I built it to understand how monitoring and diagnostics teams catch bearing problems before they turn into failures.
I also wanted to get a small understanding of what type of work is done in the industry side. 

**Live demo:** https://bearing-monitor-tom.streamlit.app/

![Dashboard](dashboard_preview.png)

## What it does

1. **Finds damage.** A damaged bearing makes a tiny impact every time a ball rolls over the bad spot. The app filters for the ringing those impacts cause, takes the outline of it (the envelope), and looks at how often the outline repeats. This is called envelope analysis.
2. **Names the part.** The outer ring, inner ring and balls each get hit at their own rate, set by the bearing's shape and the shaft speed. The app checks for a strong pulse at each rate.
3. **Logs a case.** Every warning is saved as a case in a SQLite database. A case is later closed as a real issue or a false alarm.
4. **Shows every bearing at a glance.** Each recording gets a status card: green for healthy, red when the damaged part is named, yellow when it is damaged but the part is unclear. Click a card to see its spectrum and scores.
5. **Tracks the results.** The dashboard shows open cases, closed cases, and the actionable rate, which is the share of closed cases that were real issues.

## Results

Tested on four recordings from the Case Western Reserve University (CWRU) bearing lab, where the true condition of each bearing is known.

| Recording | True condition | App says | Right? |
|---|---|---|---|
| 97.mat | healthy | healthy | yes |
| 105.mat | inner ring damage | inner ring damage | yes |
| 130.mat | outer ring damage | outer ring damage | yes |
| 118.mat | ball damage | damaged, part unclear | partly |

The ball fault is the weak spot. The app can tell something is wrong, but it cannot name the part. A damaged ball spins and tumbles, so its bad spot does not hit the rings on every turn.

![Diagnosis chart](stage3_diagnosis.png)

## Limits

- The data is from a lab test rig. It is not wind turbine data and not company data.
- The lab bearing is a small ball bearing. Large machines like wind turbines mostly use roller bearings. The method carries over, but the numbers do not.
- Four recordings is a small test. It shows the method works. It does not show how accurate it is in general.
- The alarm level (8 times above background) was picked by looking at these recordings. It would need tuning on more data.

## How to run it

You need Python 3.

```
pip install -r requirements.txt
streamlit run app.py
```

The first run downloads the four recordings from the CWRU Bearing Data Center into a `data` folder.

## Files

| File | What it is |
|---|---|
| `app.py` | The dashboard (Streamlit and Plotly) |
| `analysis.py` | The bearing math: filtering, envelope, hit rates, diagnosis |
| `database.py` | The SQL: creates the case table, adds, closes and counts cases |
| `stage1_signal.py` | Learning step 1: make a fake healthy and damaged signal |
| `stage2_find_fault.py` | Learning step 2: find the hit rate automatically |
| `stage3_real_data.py` | Learning step 3: run the method on the real recordings |

## What I would do next

- Test on many more recordings to get a real accuracy number and tune the alarm level.
- Track one bearing over its whole life to see how early the app catches the failure.
- Put a vibration sensor on a small wind turbine I am building and monitor it with this app.

## Credits

- Data: [Case Western Reserve University Bearing Data Center](https://engineering.case.edu/bearingdatacenter)
- I was new to Vibration Analysis when I started this, and I used an AI assistant to help me understand some parts of the theory as well as coding. 
