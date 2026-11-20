# Streamlit dashboard. Run with: streamlit run app.py

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis
import database
import ui
import wind_analysis

st.set_page_config(page_title="Bearing Monitor", page_icon=":material/vibration:", layout="wide")
database.create_table()
ui.inject_css()


# Cached so each recording is only analyzed once per session
@st.cache_data(show_spinner="Analyzing recording...")
def analyze(name):
    return analysis.analyze(name)


ui.header(
    "Condition monitoring · bearing vibration",
    "Bearing Monitor",
    "Finds bearing damage from vibration and tracks each warning as a case. "
    "Wind turbine tab: field data from a 2 MW turbine's high-speed shaft bearing. "
    "Lab tab: test rig recordings from Case Western Reserve University.",
)

numbers = database.summary()
tile1, tile2, tile3, tile4 = st.columns(4)
tile1.metric("Open cases", numbers["open"])
tile2.metric("Closed cases", numbers["closed"])
tile3.metric("Real issues found", numbers["real_issues"])
if numbers["closed"] > 0:
    rate = f"{100 * numbers['real_issues'] / numbers['closed']:.0f}%"
else:
    rate = "n/a"
tile4.metric("Actionable rate", rate, help="Of the closed cases, the share that were real issues.")

STATUS = {
    "healthy": ("ok", ":material/check_circle:"),
    "damaged, part unclear": ("unclear", ":material/warning:"),
}


def status_of(finding):
    return STATUS.get(finding, ("damaged", ":material/error:"))


def select(recording):
    st.session_state["selected"] = recording


def lab_tab():
    try:
        results = {name: analyze(name) for name in analysis.RECORDINGS}
    except FileNotFoundError as problem:
        st.error(str(problem))
        return

    # Which bearing card is open in the details section
    if "selected" not in st.session_state:
        st.session_state["selected"] = next(iter(analysis.RECORDINGS))

    st.subheader("Bearing status")
    st.write("Four lab recordings with known damage. Green is healthy, yellow is damaged but the part is unclear, red names the damaged part. Click a bearing for details.")

    cards = st.columns(len(results))
    for card, (name, res) in zip(cards, results.items()):
        level, icon = status_of(res["finding"])
        with card.container(border=True):
            st.markdown(f"**{name}**")
            if level == "ok":
                st.success(res["finding"].capitalize(), icon=icon)
            elif level == "unclear":
                st.warning(res["finding"].capitalize(), icon=icon)
            else:
                st.error(res["finding"].capitalize(), icon=icon)
            st.caption(f"Strongest fault peak: {res['top_score']:.0f}x")
            st.button(
                "Viewing" if st.session_state["selected"] == name else "View details",
                key=f"view_{name}",
                on_click=select,
                args=(name,),
                type="primary" if st.session_state["selected"] == name else "secondary",
                width="stretch",
            )

    if st.button("Log cases for damaged bearings"):
        new_cases = 0
        for name, res in results.items():
            if res["finding"] != "healthy" and not database.has_case(name):
                database.open_case(name, res["finding"], res["top_score"])
                new_cases += 1
        damaged = sum(res["finding"] != "healthy" for res in results.values())
        st.session_state["scan_message"] = (
            f"Scanned {len(results)} recordings: {len(results) - damaged} healthy, {damaged} damaged. "
            f"Opened {new_cases} new case(s). Healthy bearings don't get a case."
        )
        st.rerun()

    if "scan_message" in st.session_state:
        st.success(st.session_state["scan_message"])

    name = st.session_state["selected"]
    result = results[name]
    st.subheader(f"Details: {name}")

    if result["finding"] == "healthy":
        st.success("App says: healthy", icon=":material/check_circle:")
    elif result["finding"] == "damaged, part unclear":
        st.warning("App says: damaged, part unclear", icon=":material/warning:")
    else:
        st.error(f"App says: {result['finding']}", icon=":material/error:")
    st.write(f"Known condition from the lab: **{result['known']}**")

    col1, col2, col3 = st.columns(3)
    col1.metric("Shake level (RMS)", f"{result['shake']:.2f}")
    col2.metric("Spikiness (kurtosis)", f"{result['spiky']:.1f}", help="About 3 is normal. Higher means impacts.")
    col3.metric("Shaft speed", f"{result['rpm']:.0f} rpm")

    scores = pd.DataFrame(
        [
            {
                "Part": part,
                "Expected hit rate (Hz)": round(expected, 1),
                "Times above background": round(score),
                "Over alarm level": "yes" if score >= analysis.ALARM_LEVEL else "no",
            }
            for part, (expected, score) in result["results"].items()
        ]
    )
    st.dataframe(scores, hide_index=True)

    MARKER_STYLE = {
        "outer ring": ("#2a78d6", "solid"),
        "inner ring": ("#eb6834", "dash"),
        "ball": ("#1baf7a", "dot"),
    }
    show = result["freqs"] <= 250
    top_of_chart = float(result["stands_out"][show].max()) * 1.05

    chart = go.Figure()
    for part, (expected, score) in result["results"].items():
        color, dash = MARKER_STYLE[part]
        chart.add_trace(
            go.Scatter(
                x=[expected, expected],
                y=[0, top_of_chart],
                mode="lines",
                line=dict(color=color, dash=dash, width=2),
                name=f"{part} hit rate ({expected:.0f} Hz)",
                hoverinfo="skip",
            )
        )
    chart.add_trace(
        go.Scatter(
            x=result["freqs"][show],
            y=result["stands_out"][show],
            mode="lines",
            line=dict(color="#7a7974", width=1.2),
            name="this recording",
            hovertemplate="%{x:.1f} Hz<br>%{y:.0f}x above background<extra></extra>",
        )
    )
    chart.update_layout(
        title="Where this recording pulses, compared with the three expected hit rates",
        font=dict(family=ui.FONT),
        xaxis_title="Pulses per second (Hz)",
        yaxis_title="Times above background",
        yaxis_range=[0, top_of_chart],
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, x=0),
        margin=dict(t=50, b=10),
        height=420,
    )
    st.plotly_chart(chart)
    st.caption(
        f"A tall peak sitting on a coloured line means that part is damaged. "
        f"Anything {analysis.ALARM_LEVEL}x or more above the background counts."
    )


@st.cache_data
def wind_data():
    return wind_analysis.load_features()


def wind_tab():
    data = wind_data()
    days = len(data["day"])
    alarm_day = wind_analysis.first_alarm_day(data)
    baseline_rms = data["rms"][:10].mean()

    st.write(
        "Field data from the high-speed shaft bearing of a 2 MW wind turbine: one 6 second "
        "vibration recording a day for 50 days. An inner race fault developed and the bearing failed. "
        "Slide through the days to see what the app would have known at each point."
    )
    day = st.slider("Day", 1, days, days, key="wind_day")
    i = day - 1
    date = pd.to_datetime(data["dates"][i]).strftime("%b %d, %Y")
    state = wind_analysis.status_on(data, day)

    level = {"healthy": "healthy", "watch": "watch"}.get(state, "alarm")
    headline = {"healthy": "Healthy", "watch": "Watch: fault peak rising"}.get(state, "Inner race fault")
    side = ""
    if alarm_day is not None and day >= alarm_day:
        side = f"Alarm since <b>day {alarm_day}</b><br>{day - alarm_day} days in alarm"
    ui.status_banner(level, headline, f"Day {day} of {days} · {date} · {data['shaft_hz'][i] * 60:.0f} rpm", side)

    levels = [{"healthy": "healthy", "watch": "watch"}.get(wind_analysis.status_on(data, d), "alarm") for d in data["day"]]
    ui.day_ribbon(levels, day, alarm_day if alarm_day is not None and day >= alarm_day else None)

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fault score (3 day median)", f"{data['smoothed'][i]:.0f}x",
                help=f"Inner race peak in the envelope spectrum vs background. Watch at {wind_analysis.WATCH_LEVEL}x, alarm at {wind_analysis.ALARM_LEVEL}x.")
    col2.metric("Vibration level (RMS)", f"{data['rms'][i]:.2f}",
                f"{100 * (data['rms'][i] / baseline_rms - 1):+.0f}% vs first 10 days", delta_color="off")
    col3.metric("Spikiness (kurtosis)", f"{data['kurtosis'][i]:.2f}", help="About 3 is normal. Higher means impacts.")
    col4.metric("Shaft speed", f"{data['shaft_hz'][i] * 60:.0f} rpm")

    if alarm_day is not None and day >= alarm_day:
        j = alarm_day - 1
        st.info(
            f"Alarm raised on day {alarm_day} ({pd.to_datetime(data['dates'][j]).strftime('%b %d')}), "
            f"{days - alarm_day} days before the last recording. On that day the overall vibration level was "
            f"{100 * (data['rms'][j] / baseline_rms - 1):+.0f}% vs the first 10 days, so RMS alone would not have caught it.",
            icon=":material/notifications:",
        )

    shown = data["day"] <= day
    trend = go.Figure()
    trend.add_hline(y=wind_analysis.ALARM_LEVEL, line=dict(color=ui.COLORS["alarm"], dash="dash", width=1.5),
                    annotation_text=f"alarm {wind_analysis.ALARM_LEVEL}x", annotation_position="top right")
    trend.add_hline(y=wind_analysis.WATCH_LEVEL, line=dict(color=ui.COLORS["watch"], dash="dot", width=1.5),
                    annotation_text=f"watch {wind_analysis.WATCH_LEVEL}x", annotation_position="bottom right")
    trend.add_trace(go.Scatter(
        x=data["day"][shown], y=data["ir_score"][shown], mode="markers", name="daily score",
        marker=dict(color="#9AA5B0", size=8, line=dict(width=1, color="rgba(255,255,255,0.7)")), hovertemplate="day %{x}<br>%{y:.0f}x<extra></extra>",
    ))
    trend.add_trace(go.Scatter(
        x=data["day"][shown], y=data["smoothed"][shown], mode="lines", name="3 day median",
        line=dict(color=ui.COLORS["accent"], width=3, shape="spline", smoothing=0.4), hovertemplate="day %{x}<br>%{y:.0f}x<extra></extra>",
    ))
    if alarm_day is not None and day >= alarm_day:
        trend.add_vline(x=alarm_day, line=dict(color=ui.COLORS["alarm"], width=1),
                        annotation_text=f"alarm, day {alarm_day}", annotation_position="top left")
    trend.update_layout(
        xaxis=dict(title="Day", range=[0.5, days + 0.5]),
        yaxis=dict(title="Times above background", range=[0, max(60, data["ir_score"].max() * 1.05)]),
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, x=0),
    )
    ui.style_chart(trend, "Inner race fault score over time", 380)
    st.plotly_chart(trend)

    rms_chart = go.Figure(go.Scatter(
        x=data["day"][shown], y=data["rms"][shown], mode="lines+markers",
        line=dict(color="#54616D", width=2), marker=dict(size=6), hovertemplate="day %{x}<br>%{y:.2f}<extra></extra>",
    ))
    rms_chart.update_layout(
        xaxis=dict(title="Day", range=[0.5, days + 0.5]),
        yaxis=dict(title="RMS", range=[0, data["rms"].max() * 1.15]),
        showlegend=False,
    )
    ui.style_chart(rms_chart, "Overall vibration level (RMS) over time", 260)
    st.plotly_chart(rms_chart)
    st.caption("The fault score climbs weeks before the overall vibration level moves. That gap is the warning time.")

    shaft = data["shaft_hz"][i]
    fault_hz = wind_analysis.INNER_RACE_ORDER * shaft
    spectrum = go.Figure()
    for hz, text, dash in [(fault_hz, "inner race", "dash"), (fault_hz - shaft, "sideband", "dot"),
                           (fault_hz + shaft, "sideband", "dot"), (2 * fault_hz, "2x inner race", "dash")]:
        spectrum.add_vline(x=hz, line=dict(color="#E07A3F", dash=dash, width=1.5),
                           annotation_text=text, annotation_position="top")
    spectrum.add_trace(go.Scatter(
        x=data["freqs"], y=data["spectra"][i], mode="lines", line=dict(color="#54616D", width=1),
        hovertemplate="%{x:.1f} Hz<br>%{y:.0f}x<extra></extra>",
    ))
    spectrum.update_layout(
        xaxis=dict(title="Frequency (Hz)", range=[0, wind_analysis.SPECTRUM_MAX_HZ]),
        yaxis=dict(title="Times above background", rangemode="tozero"),
        showlegend=False,
    )
    ui.style_chart(spectrum, f"Envelope spectrum, day {day}", 360)
    spectrum.update_layout(margin=dict(t=70))
    st.plotly_chart(spectrum)
    st.caption(
        f"Inner race fault frequency is {wind_analysis.INNER_RACE_ORDER}x shaft speed ({fault_hz:.0f} Hz today). "
        "An inner race fault also shows sidebands one shaft speed either side, because the damaged spot turns with the shaft."
    )

    name = "Turbine HSS bearing"
    if state != "healthy" and not database.has_case(name):
        if st.button("Log case for this turbine"):
            database.open_case(name, f"{state} (day {day})", float(data["smoothed"][i]))
            st.rerun()
    elif database.has_case(name):
        st.caption("A case for this turbine is already in the case log.")


wind, lab = st.tabs(["Wind turbine (field data)", "Lab bearings (CWRU)"])
with wind:
    wind_tab()
with lab:
    lab_tab()

st.header("Case log")
cases = database.list_cases()

if cases.empty:
    st.info("No cases yet. Log one from either tab.")
else:
    st.dataframe(cases, hide_index=True)

    open_cases = cases[cases["status"] == "open"]
    if not open_cases.empty:
        st.subheader("Close a case")
        with st.form("close_case", clear_on_submit=True):
            labels = {
                row["id"]: f"Case {row['id']}: {row['recording']}, {row['finding']}"
                for _, row in open_cases.iterrows()
            }
            case_id = st.selectbox("Case", list(labels), format_func=lambda i: labels[i])
            outcome = st.radio("What did it turn out to be?", ["real issue", "false alarm"], horizontal=True)
            action = st.text_input("Action taken", placeholder="Replaced bearing at next planned stop")
            if st.form_submit_button("Close case"):
                database.close_case(int(case_id), outcome, action)
                st.rerun()

with st.expander("Reset the demo"):
    st.write("Deletes every case so you can start the demo again from empty.")
    if st.button("Delete all cases"):
        database.delete_all_cases()
        st.session_state.pop("scan_message", None)
        st.rerun()
