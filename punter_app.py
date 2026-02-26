import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Betslip Generator Pro", page_icon="⚖️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .slip-card { 
        background-color: #1c2128; 
        border: 1px solid #444c56; 
        border-radius: 12px; 
        padding: 25px; 
        margin-bottom: 25px; 
    }
    .prob-tag { 
        color: #2ecc71; 
        font-weight: bold; 
        font-size: 1.1rem; 
        margin-bottom: 8px;
        display: block;
    }
    .market-text { font-size: 1.2rem; font-weight: 600; color: #adbac7; }
    .teams-text { font-size: 1rem; color: #768390; margin-top: 4px; }
    .odd-box { 
        background: #22272e; 
        padding: 12px; 
        border-radius: 8px; 
        text-align: center; 
        border: 1px solid #444c56; 
        min-width: 90px;
    }
    .odd-val { font-size: 1.4rem; font-weight: bold; color: #539bf5; }
    </style>
    """, unsafe_allow_html=True)

# --- API CONSTANTEN ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- STATE ---
if 'slips' not in st.session_state: st.session_state.slips = []

# --- INTERFACE ---
st.title("⚖️ Betslip Generator")

c1, c2, c3, c4 = st.columns(4)
target_odds = c1.number_input("Target Odds", value=2.5, step=0.1)
items_per_slip = c2.number_input("Items /Slip", value=2, min_value=1)
min_odd = c3.number_input("Min Odds /Item", value=1.2)
max_odd = c4.number_input("Max Odds /Item", value=3.0)

with st.expander("🛠️ Tijd & Filters", expanded=True):
    f1, f2 = st.columns(2)
    time_limit = f1.selectbox("Starttijd binnen:", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 24 uur"])
    min_prob = f2.slider("Minimale Slaagkans %", 10, 95, 40)

# --- GENERATOR LOGICA ---
if st.button("🚀 GENEREER SLIPS", use_container_width=True):
    with st.spinner("Echte teamnamen en odds synchroniseren..."):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        params = {'date': datetime.now(TIMEZONE).strftime('%Y-%m-%d')}
        
        try:
            r = requests.get(f"{BASE_URL}/odds", headers=headers, params=params)
            data = r.json()

            if data.get('response'):
                matches_pool = []
                now_ts = int(time.time())

                for item in data['response']:
                    # --- CRUCIALE FIX: ECHTE TEAMNAMEN ---
                    # Bij API-Football V3 zitten de namen in response[i]['teams']
                    home = item.get('teams', {}).get('home', {}).get('name', "Onbekend")
                    away = item.get('teams', {}).get('away', {}).get('name', "Onbekend")
                    league = item.get('league', {}).get('name', "Competitie")
                    
                    # Tijd Filter
                    kickoff_ts = item['fixture']['timestamp']
                    diff_h = (kickoff_ts - now_ts) / 3600
                    
                    time_ok = False
                    if time_limit == "Volgende 1 uur" and 0 <= diff_h <= 1: time_ok = True
                    elif time_limit == "Volgende 2 uur" and 0 <= diff_h <= 2: time_ok = True
                    elif time_limit == "Volgende 24 uur" and 0 <= diff_h <= 24: time_ok = True

                    if time_ok and home != "Onbekend":
                        for bm in item['bookmakers']:
                            for bet in bm['bets']:
                                for val in bet['values']:
                                    odd = float(val['odd'])
                                    prob = round((1/odd)*100 + 4.8, 1) # Berekende kans
                                    
                                    if min_odd <= odd <= max_odd and prob >= min_prob:
                                        matches_pool.append({
                                            "teams": f"{home} vs {away}",
                                            "league": league,
                                            "market": f"{bet['name']}: {val['value']}",
                                            "time": datetime.fromtimestamp(kickoff_ts, TIMEZONE).strftime('%H:%M'),
                                            "odd": odd,
                                            "prob": prob
                                        })

                matches_pool.sort(key=lambda x: x['prob'], reverse=True)
                st.session_state.slips = [matches_pool[i:i + int(items_per_slip)] for i in range(0, len(matches_pool), int(items_per_slip))]
            else:
                st.warning("Geen data gevonden voor dit tijdslot.")
        except Exception as e:
            st.error(f"Fout: {e}")

# --- DISPLAY (DE LOOK UIT DE VIDEO) ---
if st.session_state.slips:
    for slip in st.session_state.slips[:10]:
        if len(slip) == int(items_per_slip):
            with st.container():
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                for m in slip:
                    c_info, c_odd = st.columns([4, 1])
                    with c_info:
                        st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                        st.markdown(f"<div class='market-text'>{m['market']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='teams-text'>{m['time']} | {m['teams']} ({m['league']})</div>", unsafe_allow_html=True)
                    with c_odd:
                        st.markdown(f"""
                            <div class='odd-box'>
                                <div class='odd-val'>{m['odd']}</div>
                                <div style='color:#768390; font-size:0.7rem;'>ODDS</div>
                            </div>
                        """, unsafe_allow_html=True)
                    st.divider()
                st.markdown('</div>', unsafe_allow_html=True)
