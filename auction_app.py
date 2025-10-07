import streamlit as st
import pandas as pd

st.set_page_config(page_title="SE VRM Cricket Tournament - Auction", layout="wide")

# --- Page background (sea green -> white) ---
st.markdown("""
<style>
/* Whole app background */
.stApp {
  background: linear-gradient(180deg, #E8FBF8 0%, #FFFFFF 60%);
}
/* Optional: soften the main content width/padding a bit */
.block-container {
  padding-top: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# Theme accents
ACCENT_1 = "#b28dff"   # light purple (gradient)
ACCENT_2 = "#34d0c3"   # sea green (gradient)
DARK_PURPLE = "#4b0082"

# --------------------------- Styles ---------------------------
# NOTE: Streamlit doesn't allow per-button classes. To ensure the team buttons look
# light-purple across browsers/Streamlit versions, we style ALL buttons consistently.
st.markdown(
    f"""
    <style>
      .title-bar {{
        background: linear-gradient(90deg, {ACCENT_1}, {ACCENT_2});
        padding: 14px 18px;
        border-radius: 12px;
        margin-bottom: 12px;
      }}
      .title-bar h2 {{
        margin: 0;
        color: {DARK_PURPLE};      /* dark purple title text */
        font-weight: 800;
      }}

      .bigcard {{
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        background: white;
      }}

      /* Global button style (affects st.button) */
      .stButton > button {{
        background: #e9ddff !important;     /* light-purple */
        color: #2b195e !important;           /* deep purple text */
        border: 1px solid #c9b8ff !important;
        padding: 0.55rem 0.9rem !important;
        border-radius: 10px !important;
      }}
      /* Primary buttons still stand out a bit */
      .stButton > button[kind="primary"] {{
        background: #b28dff !important;      /* a bit darker purple */
        color: white !important;
        border-color: #9e7cf0 !important;
      }}

      /* Small caption text under team buttons */
      .team-meta {{
        font-size: 0.85rem;
        color: #3b3b3b;
        margin-top: 0.35rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="title-bar"><h2>SE VRM Cricket Tournament — Player Auction</h2></div>',
    unsafe_allow_html=True,
)

# --------------------------- State defaults ---------------------------
def _init_defaults():
    ss = st.session_state
    ss.setdefault("tournament_name", "SE VRM Cricket Tournament")
    ss.setdefault("currency_symbol", "₹")
    ss.setdefault("base_increment", 100)
    ss.setdefault("max_players_per_team", 12)
    ss.setdefault("starting_budget", 10000)
    ss.setdefault("current_index", 0)
    ss.setdefault("current_bid", 0)
    ss.setdefault("current_leader", "")
    default_teams = [
        "SE GT",
        "SE AUX and GN",
        "SE SV",
        "SE IT 1",
        "SE IT 2",
        "SE GT GS + Functions",
        "SE STG + SES",
    ]
    ss.setdefault("teams_text", "\n".join(default_teams))

_init_defaults()

# --------------------------- Sidebar ---------------------------
st.sidebar.subheader("Tournament Settings")
st.sidebar.text_input("Tournament Name", key="tournament_name")
st.sidebar.text_input("Currency Symbol", key="currency_symbol")
st.sidebar.number_input("Bid Increment", min_value=1, step=1, key="base_increment")
st.sidebar.number_input("Max Players per Team", min_value=1, step=1, key="max_players_per_team")
st.sidebar.number_input("Budget per Team", min_value=100, step=50, key="starting_budget")

st.sidebar.subheader("Teams & Budgets")
st.sidebar.text_area("Teams (one per line)", key="teams_text")
teams = [t.strip() for t in st.session_state.teams_text.split("\n") if t.strip()]
# de-dupe preserve order
seen = set()
teams = [t for t in teams if not (t in seen or seen.add(t))]

# --------------------------- Data ---------------------------
@st.cache_data
def _load_players():
    df = pd.read_csv("players_newclean.csv")
    df.columns = [c.strip() for c in df.columns]
    for c in ("Sold", "SoldTo", "FinalPrice"):
        if c not in df.columns:
            df[c] = False if c == "Sold" else ("" if c == "SoldTo" else 0)
    return df

if "players_df" not in st.session_state:
    st.session_state.players_df = _load_players().copy()

players_df = st.session_state.players_df  # live table

# budgets map
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

# sidebar actions
if st.sidebar.button("Apply Starting Budget to ALL Teams"):
    for t in teams:
        st.session_state.budgets[t] = st.session_state.starting_budget
    st.sidebar.success("Budgets updated for all teams.")

if st.sidebar.button("Reset Auction (clear results & bids)"):
    st.session_state.current_index = 0
    st.session_state.current_bid = 0
    st.session_state.current_leader = ""
    players_df["Sold"] = False
    players_df["SoldTo"] = ""
    players_df["FinalPrice"] = 0
    st.sidebar.warning("Auction state cleared. (Budgets unchanged.)")

tabs = st.tabs(["Auction Room", "Teams & Budgets", "Results / Export", "Projector View"])

# --------------------------- Helpers ---------------------------
def place_bid(team: str):
    next_bid = (
        st.session_state.current_bid + st.session_state.base_increment
        if st.session_state.current_bid > 0
        else st.session_state.base_increment
    )
    if team in st.session_state.budgets and st.session_state.budgets.get(team, 0) >= next_bid:
        st.session_state.current_bid = next_bid
        st.session_state.current_leader = team
    elif team not in st.session_state.budgets:
        st.warning(f"'{team}' is not an active team. Update the team list and bid again.")
    else:
        st.warning(f"{team} doesn't have enough budget for the next bid.")

def players_bought(team: str) -> int:
    # how many already sold to this team
    return int((players_df["SoldTo"] == team).sum())

def players_left(team: str) -> int:
    return max(st.session_state.max_players_per_team - players_bought(team), 0)

# --------------------------- Auction Room ---------------------------
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
        avail = row.get(
            "Weekend Availability",
            row.get("Are you avaialble to participate on weekends between Nov 1 and Dec 20", ""),
        )
        link = row.get("CricHeroes Link", row.get("link of the cric heroes profile", ""))

        cols = st.columns([2, 1])
        with cols[0]:
            st.write(f"**Player:** {name}")
            st.write(f"**Age Group:** {age_group}")
            # bold value for Primary Strength
            st.write(f"**Primary Strength:** **{primary}**")
            st.write(f"**Weekend Availability (Nov 1–Dec 20):** {avail}")
            if isinstance(link, str) and link.strip():
                st.write(f"[CricHeroes Profile]({link})")
        with cols[1]:
            st.metric("Current Bid", f"{st.session_state.currency_symbol}{st.session_state.current_bid}")
            st.metric("Leading Team", st.session_state.current_leader or "—")

        st.divider()

        # Team bid buttons (purple) + meta lines underneath
        grid = st.columns(3)
        for i, team in enumerate(teams):
            with grid[i % 3]:
                st.button(team, key=f"bid_{i}", on_click=place_bid, args=(team,))
                # meta on a new line, *outside* the button
                filled = players_bought(team)
                total = st.session_state.max_players_per_team
                left = players_left(team)
                budget = st.session_state.budgets.get(team, 0)
                st.markdown(
                    f'<div class="team-meta">Players: <b>{filled}/{total}</b> &nbsp;•&nbsp; '
                    f'Budget left: <b>{st.session_state.currency_symbol}{budget}</b></div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
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
                    players_df.at[st.session_state.current_index, "Sold"] = True
                    players_df.at[st.session_state.current_index, "SoldTo"] = leader
                    players_df.at[st.session_state.current_index, "FinalPrice"] = st.session_state.current_bid
                    st.session_state.budgets[leader] = st.session_state.budgets.get(leader, 0) - st.session_state.current_bid
                    st.session_state.current_index += 1
                    st.session_state.current_bid = 0
                    st.session_state.current_leader = ""
                    st.rerun()
        with c2:
            if st.button("Mark Unsold / Skip"):
                players_df.at[st.session_state.current_index, "Sold"] = False
                players_df.at[st.session_state.current_index, "SoldTo"] = ""
                players_df.at[st.session_state.current_index, "FinalPrice"] = 0
                st.session_state.current_index += 1
                st.session_state.current_bid = 0
                st.session_state.current_leader = ""
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --------------------------- Teams & Budgets ---------------------------
with tabs[1]:
    st.subheader("Teams & Budgets")
    for t in teams:
        st.write(
            f"**{t}** — Players bought: {players_bought(t)} / {st.session_state.max_players_per_team}  "
            f"— Budget Remaining: {st.session_state.currency_symbol}{st.session_state.budgets.get(t, 0)}"
        )
    st.caption("Use 'Apply Starting Budget to ALL Teams' in the sidebar to push the new starting budget to every team.")

# --------------------------- Results / Export ---------------------------
with tabs[2]:
    st.subheader("Results & Export")
    st.dataframe(players_df, use_container_width=True)
    export = players_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Auction Results (CSV)", export, file_name="auction_results.csv", mime="text/csv")

# --------------------------- Projector View ---------------------------
with tabs[3]:
    st.markdown('<div class="projector bigcard">', unsafe_allow_html=True)
    st.header(st.session_state.tournament_name)
    st.write("Live Player & Bidding")
    if st.session_state.current_index < len(players_df):
        row = players_df.iloc[st.session_state.current_index]
        name = row.get("Name", "")
        primary = row.get("Primary Strength", row.get("Primary strength", ""))
        st.subheader(name)
        st.write(f"**Primary Strength:** **{primary}**")
        st.metric("Current Bid", f"{st.session_state.currency_symbol}{st.session_state.current_bid}")
        st.metric("Leading", st.session_state.current_leader or "—")
    else:
        st.success("Auction complete!")
    st.markdown("</div>", unsafe_allow_html=True)
