import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis
import database

st.set_page_config(page_title="Bearing Monitor", layout="wide")
database.create_table()


@st.cache_data(show_spinner="Analyzing recording...")
def analyze(name):
    return analysis.analyze(name)


st.title("Bearing Monitor")
st.caption(
    "Finds bearing damage from vibration and tracks each warning as a case. "
    "Data: public lab test rig recordings from Case Western Reserve University. "
    "This is not wind turbine or company data."
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


try:
    results = {name: analyze(name) for name in analysis.RECORDINGS}
except FileNotFoundError as problem:
    st.error(str(problem))
    st.stop()

if "selected" not in st.session_state:
    st.session_state["selected"] = next(iter(analysis.RECORDINGS))

st.header("1. Bearing status")
st.write("Green is healthy, yellow is damaged but the part is unclear, red names the damaged part. Click a bearing for details.")

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
st.header(f"2. Details: {name}")

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

st.header("3. Case log")
cases = database.list_cases()

if cases.empty:
    st.info("No cases yet. Press 'Scan all recordings' above.")
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
