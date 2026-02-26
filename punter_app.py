import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter Live Tracker", page_icon="⚽", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .live-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
    .status-live { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    .status-won { color: #3fb950; font-weight: bold; }
    .status-lost { color: #f85149; font-weight: bold; }
    .score-box { background: #0d1117; padding: 5px 10px; border-radius: 5px; font-family: monospace; font-size: 1.2rem; }
    </style>
    """, unsafe_allow_html=True)

# --- API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- FUNCTIE: LIVE SCORES OPHALEN ---
def get_live_updates(fixture_ids):
    if not fixture_ids: return {}
    ids_str = "-".join(map(str, fixture_ids))
    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': ids_str})
    data = res.json()
    updates = {}
    if data.get('response'):
        for f in data['response']:
            updates[f['fixture']['id']] = {
                "status": f['fixture']['status']['short'],
                "elapsed": f['fixture']['status']['elapsed'],
                "goals_home": f['goals']['home'],
                "goals_away": f['goals']['away'],
                "score_str": f"{f['goals']['home']} - {f['goals']['away']}"
            }
    return updates

# --- UI TABS ---
t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 Live Tracker & Portfolio"])

with t1:
    st.info("De generator blijft zoals in V38 (gebruik de knop om slips op te slaan).")
    # [Generator code van V38 blijft hier actief voor het aanmaken van slips]

with t2:
    st.header("📡 Live Portfolio Tracker")
    
    # Simulatie van database (voor demo doeleinden, koppel dit aan je Firebase in de V38 code)
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = [] # Hier komen de opgeslagen slips in

    if not st.session_state.portfolio:
        st.info("Nog geen actieve slips in je portfolio. Sla een slip op in de Generator tab.")
    else:
        # Verzamel alle unieke fixture IDs uit je portfolio
        all_f_ids = []
        for slip in st.session_state.portfolio:
            for m in slip['matches']:
                all_f_ids.append(m['fixture_id'])
        
        # Haal één keer alle live data op voor alle matchen in je lijst
        live_data = get_live_updates(list(set(all_f_ids)))

        for idx, slip in enumerate(st.session_state.portfolio):
            with st.expander(f"Slip @{slip['total_odd']} - {slip['timestamp']}"):
                slip_active = True
                
                for m in slip['matches']:
                    f_id = m['fixture_id']
                    f_live = live_data.get(f_id, {"status": "NS", "score_str": "0 - 0", "elapsed": 0})
                    
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.write(f"**{m['match']}**")
                        st.caption(f"{m['market']} (@{m['odd']})")
                    
                    with c2:
                        status = f_live['status']
                        if status in ['1H', '2H', 'HT']:
                            st.markdown(f"<span class='status-live'>LIVE {f_live['elapsed']}'</span>", unsafe_allow_html=True)
                            st.markdown(f"<span class='score-box'>{f_live['score_str']}</span>", unsafe_allow_html=True)
                        elif status == 'FT':
                            st.write("🏁 Finished")
                            st.markdown(f"<span class='score-box'>{f_live['score_str']}</span>", unsafe_allow_html=True)
                        else:
                            st.write(f"🕒 Start: {m['time']}")
                    
                    with c3:
                        # Eenvoudige settlement logica (voor Match Winner Home)
                        if status == 'FT':
                            home_g = f_live['goals_home']
                            away_g = f_live['goals_away']
                            
                            # Check of de markt gewonnen is (voorbeeld voor Home win)
                            won = False
                            if "Home" in m['market'] and home_g > away_g: won = True
                            elif "Away" in m['market'] and away_g > home_g: won = True
                            elif "Draw" in m['market'] and home_g == away_g: won = True
                            # Voeg hier meer logica toe voor Over/Under
                            
                            if won: st.markdown("<span class='status-won'>✅ WON</span>", unsafe_allow_html=True)
                            else: st.markdown("<span class='status-lost'>❌ LOST</span>", unsafe_allow_html=True)
                        else:
                            st.write("⏳ In afwachting")
                
                if st.button("Verwijder uit Portfolio", key=f"del_{idx}"):
                    st.session_state.portfolio.pop(idx)
                    st.rerun()

    if st.button("🔄 Handmatig Vernieuwen"):
        st.rerun()
