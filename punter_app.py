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
        border-radius: 8px; 
        padding: 25px; 
        margin-bottom: 20px; 
    }
    .prob-tag { 
        color: #2ecc71; 
        font-weight: bold; 
        font-size: 1.2rem; 
        display: block;
        margin-bottom: 5px;
    }
    .market-title {
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .odd-box { 
        background: #0d1117; 
        padding: 15px; 
        border-radius: 8px; 
        text-align: center; 
        border: 1px solid #30363d; 
        min-width: 110px;
    }
    .odd-val { font-size: 1.5rem; font-weight: bold; color: #ffffff; }
    .meta-text { color: #8b949e; font-size: 1rem; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTEN ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- STATE ---
if 'slips' not in st.session_state: st.session_state.slips = []

# --- HEADER & SETTINGS ---
st.title("⚖️ Betslip Generator")

c1, c2, c3, c4 = st.columns(4)
target_odds = c1.number_input("Target Odds", value=2.5, step=0.1)
items_per_slip = c2.number_input("Items /Slip", value=2, min_value=1)
min_odd_item = c3.number_input("Min Odds /Item", value=1.2)
max_odd_item = c4.number_input("Max Odds /Item", value=3.0)

with st.expander("🛠️ Filters (1h / 2h)", expanded=True):
    f1, f2, f3 = st.columns(3)
    time_limit = f1.selectbox("Starttijd binnen:", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 24 uur"])
    sort_mode = f2.selectbox("Sorteer op:", ["Probability", "Value", "Odds"])
    min_prob_val = f3.slider("Minimale Slaagkans %", 5, 95, 30)

# --- GENERATOR LOGIC ---
if st.button("🚀 GENEREER SLIPS", use_container_width=True):
    with st.spinner("Teams en live odds synchroniseren..."):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
        
        try:
            res_odds = requests.get(f"{BASE_URL}/odds", headers=headers, params={'date': today})
            data_odds = res_odds.json()

            if data_odds.get('response'):
                matches_pool = []
                now_ts = int(time.time())

                for item in data_odds['response']:
                    # --- TEAM NAMEN DIRECT UIT RESPONSE ---
                    # De /odds endpoint v3 bevat teams object
                    teams = item.get('teams', {})
                    home = teams.get('home', {}).get('name', "Home")
                    away = teams.get('away', {}).get('name', "Away")
                    league = item.get('league', {}).get('name', "League")
                    
                    # TIJD CHECK
                    kickoff_ts = item['fixture']['timestamp']
                    diff_hours = (kickoff_ts - now_ts) / 3600
                    
                    time_ok = False
                    if time_limit == "Volgende 1 uur" and 0 <= diff_hours <= 1: time_ok = True
                    elif time_limit == "Volgende 2 uur" and 0 <= diff_hours <= 2: time_ok = True
                    elif time_limit == "Volgende 24 uur" and 0 <= diff_hours <= 24: time_ok = True

                    if time_ok:
                        for bm in item['bookmakers']:
                            for bet in bm['bets']:
                                for val in bet['values']:
                                    odd = float(val['odd'])
                                    implied = (1/odd)*100
                                    # Value Model
                                    model_prob = round(implied + 5.5, 1) 
                                    
                                    if min_odd_item <= odd <= max_odd_item and model_prob >= min_prob_val:
                                        matches_pool.append({
                                            "teams": f"{home} vs {away}",
                                            "league": league,
                                            "market": f"{bet['name']}: {val['value']}",
                                            "time": datetime.fromtimestamp(kickoff_ts, TIMEZONE).strftime('%H:%M'),
                                            "odd": odd,
                                            "prob": model_prob,
                                            "value": round(model_prob - implied, 1)
                                        })

                if sort_mode == "Probability": matches_pool.sort(key=lambda x: x['prob'], reverse=True)
                st.session_state.slips = [matches_pool[i:i + int(items_per_slip)] for i in range(0, len(matches_pool), int(items_per_slip))]
            else:
                st.warning("Geen data gevonden voor dit tijdslot.")
        except Exception as e:
            st.error(f"Fout: {e}")

# --- DISPLAY (EXACT BSG LOOK) ---
if st.session_state.slips:
    for slip in st.session_state.slips[:8]:
        if len(slip) == int(items_per_slip):
            with st.container():
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                
                for m in slip:
                    c_info, c_odd = st.columns([4, 1.2])
                    with c_info:
                        st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                        st.markdown(f"<div class='market-title'>{m['market']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<p class='meta-text'>{m['time']} | {m['teams']} ({m['league']})</p>", unsafe_allow_html=True)
                    with c_odd:
                        st.markdown(f"""
                            <div class='odd-box'>
                                <div class='odd-val'>{m['odd']}</div>
                                <div style='color:#8b949e; font-size:0.8rem;'>ODDS</div>
                            </div>
                        """, unsafe_allow_html=True)
                    st.divider()
                st.markdown('</div>', unsafe_allow_html=True)
