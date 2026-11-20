# Small HTML pieces and chart styling for the dashboard.
# Status colours match .streamlit/config.toml.

import html

import streamlit as st

COLORS = {
    "healthy": "#1E8E5A",
    "watch": "#B7791F",
    "alarm": "#C2412D",
    "accent": "#1B86A8",
    "muted": "#6B7A85",
    "grid": "rgba(120, 140, 150, 0.18)",
    "trace": "#14212B",
}

FONT = "IBM Plex Sans, sans-serif"

CSS = """
<style>
:root {
  --bm-ink: #14212B; --bm-muted: #5D6C77; --bm-line: #D3DBDF; --bm-panel: #FFFFFF;
  --bm-empty: #E3E9EC; --bm-ok: #1E8E5A; --bm-watch: #B7791F; --bm-alarm: #C2412D;
  --bm-ok-bg: #E6F4EC; --bm-watch-bg: #FBF1DE; --bm-alarm-bg: #FBE7E3;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bm-ink: #E3EAEE; --bm-muted: #9AABB6; --bm-line: #2A3842; --bm-panel: #17222A;
    --bm-empty: #22303A; --bm-ok: #4CC08A; --bm-watch: #E0A84A; --bm-alarm: #E8705C;
    --bm-ok-bg: #16302A; --bm-watch-bg: #33291A; --bm-alarm-bg: #3A1E1A;
  }
}
.bm-eyebrow { font-family: "IBM Plex Mono", monospace; font-size: 0.75rem; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--bm-muted); margin-bottom: -0.6rem; }

/* status banner: colour carries the state, the dot pulses a few times when it changes to alarm */
.bm-status { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 0.9rem 1.1rem;
  border-radius: 6px; border: 1px solid var(--bm-line); background: var(--bm-panel); }
.bm-status.healthy { background: var(--bm-ok-bg); border-color: transparent; }
.bm-status.watch { background: var(--bm-watch-bg); border-color: transparent; }
.bm-status.alarm { background: var(--bm-alarm-bg); border-color: transparent; }
.bm-dot { position: relative; width: 14px; height: 14px; border-radius: 50%; flex: none; }
.healthy .bm-dot { background: var(--bm-ok); } .watch .bm-dot { background: var(--bm-watch); }
.alarm .bm-dot { background: var(--bm-alarm); }
.alarm .bm-dot::after, .watch .bm-dot::after { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: inherit; animation: bm-ping 1.4s cubic-bezier(0.16, 1, 0.3, 1) 3; }
@keyframes bm-ping { from { transform: scale(1); opacity: 0.6; } to { transform: scale(2.6); opacity: 0; } }
.bm-state { font-weight: 600; font-size: 1.35rem; letter-spacing: -0.01em;
  line-height: 1.1; color: var(--bm-ink); }
.bm-sub { font-size: 0.9rem; color: var(--bm-muted); }
.bm-side { margin-left: auto; text-align: right; font-size: 0.9rem; color: var(--bm-muted); }
.bm-side b { color: var(--bm-ink); font-weight: 600; }

/* 50 day ribbon: one cell per recording, filled up to the selected day */
.bm-ribbon { display: grid; grid-template-columns: repeat(50, minmax(0, 1fr)); gap: 3px; margin-top: 0.2rem; }
.bm-cell { height: 22px; border-radius: 2px; background: var(--bm-empty); }
.bm-cell.healthy { background: var(--bm-ok); } .bm-cell.watch { background: var(--bm-watch); }
.bm-cell.alarm { background: var(--bm-alarm); }
.bm-cell.today { outline: 2px solid var(--bm-ink); outline-offset: 1px; animation: bm-land 220ms cubic-bezier(0.16, 1, 0.3, 1); }
@keyframes bm-land { from { transform: scaleY(0.4); } to { transform: scaleY(1); } }
.bm-axis { position: relative; height: 1.1rem; display: flex; justify-content: space-between; font-family: "IBM Plex Mono", monospace;
  font-size: 0.72rem; color: var(--bm-muted); margin-top: 0.35rem; }
.bm-legend { display: flex; gap: 1.1rem; flex-wrap: wrap; font-size: 0.82rem; color: var(--bm-muted); margin-top: 0.4rem; }
.bm-legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px;
  margin-right: 6px; vertical-align: -1px; background: var(--c); }

@media (prefers-reduced-motion: reduce) {
  .alarm .bm-dot::after, .watch .bm-dot::after { animation: none; }
  .bm-cell.today { animation: none; }
}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header(eyebrow, title, text):
    st.markdown(f'<div class="bm-eyebrow">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(text)


def status_banner(level, state, sub, side=""):
    side_html = f'<div class="bm-side">{side}</div>' if side else ""
    st.markdown(
        f'<div class="bm-status {level}" role="status"><div class="bm-dot"></div>'
        f'<div><div class="bm-state">{html.escape(state)}</div><div class="bm-sub">{html.escape(sub)}</div></div>'
        f"{side_html}</div>",
        unsafe_allow_html=True,
    )


def day_ribbon(levels, day, alarm_day):
    cells = []
    for d, level in enumerate(levels, start=1):
        cls = level if d <= day else ""
        if d == day:
            cls += " today"
        cells.append(f'<div class="bm-cell {cls}" title="Day {d}: {level if d <= day else "not yet recorded"}"></div>')
    alarm_label = ""
    if alarm_day:
        left = (alarm_day - 0.5) / len(levels) * 100
        alarm_label = (f'<span style="position:absolute; left:{left:.1f}%; transform:translateX(-50%); '
                       f'color:var(--bm-alarm)">&#9650; alarm day {alarm_day}</span>')
    st.markdown(
        f'<div class="bm-ribbon" aria-label="Status for each day up to day {day}">{"".join(cells)}</div>'
        f'<div class="bm-axis"><span>day 1</span>{alarm_label}<span>day {len(levels)}</span></div>'
        '<div class="bm-legend"><span style="--c: var(--bm-ok)">healthy</span>'
        '<span style="--c: var(--bm-watch)">watch</span><span style="--c: var(--bm-alarm)">alarm</span>'
        '<span style="--c: var(--bm-empty)">not yet recorded</span></div>',
        unsafe_allow_html=True,
    )


def style_chart(fig, title, height):
    fig.update_layout(
        title=dict(text=title, font=dict(family=FONT, size=17, weight=600)),
        font=dict(family=FONT, size=13),
        height=height,
        margin=dict(t=56, b=10, l=10, r=10),
        hoverlabel=dict(font_family=FONT),
    )
    fig.update_xaxes(gridcolor=COLORS["grid"], zeroline=False)
    fig.update_yaxes(gridcolor=COLORS["grid"], zeroline=False)
    return fig
