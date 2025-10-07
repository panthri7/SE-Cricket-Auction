import streamlit as st
import pandas as pd
import time

st.set_page_config(page_title="SE VRM Cricket Tournament - Auction", layout="wide")

# Theme accents (light purple & sea green)
ACCENT_1 = "#b28dff"
ACCENT_2 = "#34d0c3"

st.markdown(
    f"""
    <style>
    .title-bar {{
        background: linear-gradient(90deg, {ACCENT_1}, {ACCENT_2});
        color: white;
        padding: 14px 18px;
        border-radius: 12px;
        margin-bottom: 12px;
    }}
    .bigcard {{
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        background: white;
    }}
    .projector h1, .projector h2, .projector h3 {{
        margin: 0;
    }}
    </style>
    """, unsafe_allow_html=True
)

st.markdown('<div class="title-bar"><h2>SE VRM Cricket Tournament — Player Auction</h2></div>', unsafe_allow_html=True)

# ---------- State defaults ----------
def _init_defaults():
    ss = st.session_state
    ss.setdefault("tournament_name", "SE VRM Cricket Tournament")
    ss.setdefault("currency_symbol", "₹")
    ss.setdefault("base_increment", 100)
    ss.setdefault("timer_secs", 45)
    ss.setdefault("max_players_per_team", 12)
    ss.setdefault("starting_budget", 10000)
    ss.setdefault("time_left", ss["timer_secs"])
    ss.setdefault("is_running", False)
    ss.setdefault("current_index", 0)
    ss.setdefault("current_bid", 0)
    ss.setdefault("current_leader", "")
    default_teams = [
        "SE PT",
        "SE AUX and GN",
        "SE SV",
        "SE IT 1",
        "SE IT 2",
        "SE GT GS + Functions",
        "SE STG + SES",
    ]
    ss.setdefault("teams_text", "\n".join(default_teams))

_init_defaults()

# ---------- Sidebar (bound directly to session_state keys) ----------
st.sidebar.subheader("Tournament Settings")
st.sidebar.text_input("Tournament Name", key="tournament_name")
st.sidebar.text_input("Currency Symbol", key="currency_symbol")
st.sidebar.number_input("Bid Increment", min_value=1, step=1, key="base_increment")
st.sidebar.number_input("Timer per Player (sec)", min_value=10, step=1, key="timer_secs")
st.sidebar.number_input("Max Players per Team", min_value=1, step=1, key="max_players_per_team")
st.sidebar.number_input("Budget per Team", min_value=100, step=50, key="starting_budget")

st.sidebar.subheader("Teams & Budgets")
st.sidebar.text_area("Teams (one per line)", key="teams_text")
teams = [t.strip() for t in st.session_state.teams_text.split("\n") if t.strip()]
seen = set()
teams = [t for t in teams if not (t in seen or seen.add(t))]

# Load players - keep a single live copy in session_state
@st.cache_data
def _load_players():
    df = pd.read_csv("players_clean.csv")
    df.columns = [c.strip() for c in df.columns]
    for c in ("Sold","SoldTo","FinalPrice"):
        if c not in df.columns:
            df[c] = False if c=="Sold" else ("" if c=="SoldTo" else 0)
    return df

if "players_df" not in st.session_state:
    st.session_state.players_df = _load_players().copy()

players_df = st.session_state.players_df  # reference the live table

# ---------- Budgets alignment ----------
if "budgets" not in st.session_state:
    st.session_state.budgets = {t: st.session_state.starting_budget for t in teams}
else:
    for t in teams:
        if t not in st.session_state.budgets:
            st.session_state.budgets[t] = st.session_state.starting_budget
    for t in list(st.session_state.budgets.keys()):
        if t not in teams:
            if st.session_state.current_leader == t:
                st.session_state.current_leader = ""
            del st.session_state.budgets[t]

# Apply buttons
if st.sidebar.button("Apply Starting Budget to ALL Teams"):
    for t in teams:
        st.session_state.budgets[t] = st.session_state.starting_budget
    st.sidebar.success("Budgets updated for all teams.")

if st.sidebar.button("Reset Auction (clear results & bids)"):
    st.session_state.current_index = 0
    st.session_state.current_bid = 0
    st.session_state.current_leader = ""
    st.session_state.time_left = int(st.session_state.timer_secs)
    st.session_state.is_running = False
    # reset results in the live df
    players_df["Sold"] = False
    players_df["SoldTo"] = ""
    players_df["FinalPrice"] = 0
    st.sidebar.warning("Auction state cleared. (Budgets unchanged.)")

# If timer setting changed and not running, sync time_left so Enter applies immediately
if not st.session_state.is_running:
    st.session_state.time_left = int(st.session_state.timer_secs)

tabs = st.tabs(["Auction Room", "Teams & Budgets", "Results / Export", "Projector View"])

# ------ Auction Room ------
with tabs[0]:
    st.markdown('<div class="bigcard">', unsafe_allow_html=True)
    st.subheader("Live Auction")

    if st.session_state.current_index >= len(players_df):
        st.success("All players processed! Go to Results / Export tab.")
    else:
        row = players_df.iloc[st.session_state.current_index]
        name = row.get("Name", "")
        age_group = row.get("Age Group", "")
        primary = row.get("Primary Strength", row.get("Primary strength", ""))
        avail = row.get("Weekend Availability", row.get("Are you avaialble to participate on weekends between Nov 1 and Dec 20", ""))
        link = row.get("CricHeroes Link", row.get("link of the cric heroes profile", ""))

        cols = st.columns([2,1])
        with cols[0]:
            st.write(f"**Player:** {name}")
            st.write(f"**Age Group:** {age_group}")
            st.write(f"**Primary Strength:** {primary}")
            st.write(f"**Weekend Availability (Nov 1–Dec 20):** {avail}")
            if isinstance(link, str) and link.strip():
                st.write(f"[CricHeroes Profile]({link})")
        with cols[1]:
            st.metric("Current Bid", f"{st.session_state.currency_symbol}{st.session_state.current_bid}")
            st.metric("Leading Team", st.session_state.current_leader or "—")

        st.divider()

        # Bid buttons
        bid_cols = st.columns(3)
        def place_bid(team):
            next_bid = st.session_state.current_bid + st.session_state.base_increment if st.session_state.current_bid > 0 else st.session_state.base_increment
            if team in st.session_state.budgets and st.session_state.budgets.get(team, 0) >= next_bid:
                st.session_state.current_bid = next_bid
                st.session_state.current_leader = team
            elif team not in st.session_state.budgets:
                st.warning(f"'{team}' is not an active team. Update the team list and bid again.")
            else:
                st.warning(f"{team} doesn't have enough budget for the next bid.")

        for i, team in enumerate(teams):
            with bid_cols[i % 3]:
                st.button(f"Bid for {team}", key=f"bid_{i}", on_click=place_bid, args=(team,))

        st.divider()
        colA, colB, colC, colD, colE = st.columns(5)
        with colA:
            if st.button("Start/Resume Timer"):
                st.session_state.is_running = True
        with colB:
            if st.button("Pause Timer"):
                st.session_state.is_running = False
        with colC:
            if st.button("Reset Timer"):
                st.session_state.time_left = int(st.session_state.timer_secs)
                st.session_state.is_running = False
        with colD:
            btn_disabled = not bool(st.session_state.current_leader)
            if st.button("Sell to Leading Team", type="primary", disabled=btn_disabled):
                leader = (st.session_state.current_leader or "").strip()
                if not leader:
                    st.warning("No leading team yet. Place a bid first.")
                elif leader not in st.session_state.budgets:
                    st.warning("Leading team is no longer in the teams list. Please bid again after updating teams.")
                    st.session_state.current_leader = ""
                    st.session_state.current_bid = 0
                else:
                    # finalize sale into the LIVE df (persists across reruns)
                    players_df.at[st.session_state.current_index, "Sold"] = True
                    players_df.at[st.session_state.current_index, "SoldTo"] = leader
                    players_df.at[st.session_state.current_index, "FinalPrice"] = st.session_state.current_bid
                    st.session_state.budgets[leader] = st.session_state.budgets.get(leader, 0) - st.session_state.current_bid
                    # reset for next player
                    st.session_state.current_index += 1
                    st.session_state.current_bid = 0
                    st.session_state.current_leader = ""
                    st.session_state.time_left = int(st.session_state.timer_secs)
                    st.session_state.is_running = False
                    # rerun so Results tab shows fresh data immediately
                    st.rerun()
        with colE:
            if st.button("Mark Unsold / Skip"):
                players_df.at[st.session_state.current_index, "Sold"] = False
                players_df.at[st.session_state.current_index, "SoldTo"] = ""
                players_df.at[st.session_state.current_index, "FinalPrice"] = 0
                st.session_state.current_index += 1
                st.session_state.current_bid = 0
                st.session_state.current_leader = ""
                st.session_state.time_left = int(st.session_state.timer_secs)
                st.session_state.is_running = False
                st.rerun()

        # ----- WORKING COUNTDOWN -----
        # Decrement once per second while running, then rerun to refresh the UI.
        if st.session_state.is_running and st.session_state.time_left > 0:
            time.sleep(1)
            st.session_state.time_left -= 1
            st.rerun()
        elif st.session_state.is_running and st.session_state.time_left <= 0:
            st.session_state.is_running = False
            st.warning("⏳ Time's up!")

        st.info(f"Timer: {st.session_state.time_left}s")
        st.caption("Timer runs in real time. Pause/Reset from the controls above.")

    st.markdown('</div>', unsafe_allow_html=True)

# ------ Teams & Budgets ------
with tabs[1]:
    st.subheader("Teams & Budgets")
    for t in teams:
        st.write(f"**{t}** — Budget Remaining: {st.session_state.currency_symbol}{st.session_state.budgets.get(t, 0)}")
    st.caption("Use 'Apply Starting Budget to ALL Teams' in the sidebar to push the new starting budget to every team.")

# ------ Results / Export ------
with tabs[2]:
    st.subheader("Results & Export")
    st.dataframe(players_df, use_container_width=True)
    export = players_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Auction Results (CSV)", export, file_name="auction_results.csv", mime="text/csv")

# ------ Projector View ------
with tabs[3]:
    st.markdown('<div class="projector bigcard">', unsafe_allow_html=True)
    st.header(st.session_state.tournament_name)
    st.write("Live Player & Bidding")
    if st.session_state.current_index < len(players_df):
        row = players_df.iloc[st.session_state.current_index]
        name = row.get("Name", "")
        primary = row.get("Primary Strength", row.get("Primary strength", ""))
        st.subheader(name)
        st.write(f"**Primary Strength:** {primary}")
        st.metric("Current Bid", f"{st.session_state.currency_symbol}{st.session_state.current_bid}")
        st.metric("Leading", st.session_state.current_leader or "—")
    else:
        st.success("Auction complete!")
    st.markdown('</div>', unsafe_allow_html=True)
