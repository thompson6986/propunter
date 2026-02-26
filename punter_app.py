import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import time  # <--- Fix voor de 'time is not defined' fout

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Betslip Generator Pro", page_icon="⚖️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .slip-card { background-color: #1c2128; border: 1px solid #444c56; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
    .prob-tag { color: #2ecc71; font-weight: bold; font-size: 1.1rem; }
    .odd-box { background: #0d1117; padding: 10px; border-radius: 5px; text-align: center; border: 1px solid #30363d; width: 100px; }
    .meta-text { color: #8b949e; font-size: 0.85rem; margin-top: -5px; }
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

with st.expander("🛠️ Filters & Timeframe", expanded=True):
    f1, f2, f3 = st.columns(3)
    time_limit = f1.selectbox("Starttijd binnen:", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 24 uur"])
    sort_mode = f2.selectbox("Sorteren op:", ["Probability", "Value", "Odds"])
    min_prob_val = f3.slider("Minimale Slaagkans %", 5, 95, 30)

# --- GENERATOR LOGIC ---
if st.button("🚀 GENEREER PROFESSIONELE SLIPS", use_container_width=True):
    with st.spinner("Teams en live odds ophalen..."):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
        
        try:
            # We halen de odds op (API-Football v3)
            res_odds = requests.get(f"{BASE_URL}/odds", headers=headers, params={'date': today})
            data_odds = res_odds.json()

            if data_odds.get('response'):
                matches_pool = []
                now_ts = int(time.time())

                for item in data_odds['response']:
                    # --- TEAM NAMEN EXTRACTIE (V3 Methode) ---
                    # De namen zitten in de 'fixture' metadata of direct onder 'teams'
                    home_team = item.get('teams', {}).get('home', {}).get('name', "Home")
                    away_team = item.get('teams', {}).get('away', {}).get('name', "Away")
                    league_name = item.get('league', {}).get('name', "League")
                    
                    # Tijd berekening
                    kickoff_ts = item['fixture']['timestamp']
                    diff_hours = (kickoff_ts - now_ts) / 3600
                    
                    # Tijd Filter
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
                                    model_prob = round(implied + 5.2, 1) # Value model
                                    
                                    if min_odd_item <= odd <= max_odd_item and model_prob >= min_prob_val:
                                        matches_pool.append({
                                            "teams": f"{home_team} vs {away_team}",
                                            "league": league_name,
                                            "market": f"{bet['name']}: {val['value']}",
                                            "time": datetime.fromtimestamp(kickoff_ts, TIMEZONE).strftime('%H:%M'),
                                            "odd": odd,
                                            "prob": model_prob,
                                            "value": round(model_prob - implied, 1)
                                        })

                # Sorteren
                if sort_mode == "Probability": matches_pool.sort(key=lambda x: x['prob'], reverse=True)
                elif sort_by == "Value": matches_pool.sort(key=lambda x: x['value'], reverse=True)

                st.session_state.slips = [matches_pool[i:i + int(items_per_slip)] for i in range(0, len(matches_pool), int(items_per_slip))]
            else:
                st.warning("Geen data gevonden voor dit tijdslot.")
        except Exception as e:
            st.error(f"Fout: {e}")

# --- DISPLAY ---
if st.session_state.slips:
    for slip in st.session_state.slips[:10]:
        if len(slip) == int(items_per_slip):
            with st.container():
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                total_odd = 1.0
                for m in slip:
                    total_odd *= m['odd']
                    c_info, c_odd = st.columns([4, 1])
                    with c_info:
                        st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                        st.write(f"**{m['market']}**")
                        st.markdown(f"<p class='meta-text'>{m['time']} | {m['teams']} ({m['league']})</p>", unsafe_allow_html=True)
                    with c_odd:
                        st.markdown(f"<div class='odd-box'><h3>{m['odd']}</h3><small>ODDS</small></div>", unsafe_allow_html=True)
                    st.divider()
                
                st.metric("Totaal Odds", f"{round(total_odd, 2)}")
                st.markdown('</div>', unsafe_allow_html=True)
