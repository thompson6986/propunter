import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import random

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Professional Parlay Builder", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #238636; color: white; border-radius: 8px; height: 3em; font-weight: bold; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 25px; }
    .slip-card { background-color: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #238636; }
    .prob-tag { color: #3fb950; font-weight: bold; font-size: 1.2rem; }
    .team-row { font-size: 1.1rem; font-weight: 600; color: #adbac7; margin: 10px 0; }
    .odd-badge { background: #21262d; padding: 8px 15px; border-radius: 6px; border: 1px solid #30363d; font-weight: bold; color: #58a6ff; font-size: 1.2rem; }
    </style>
    """, unsafe_allow_html=True)

# --- API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- STRATEGISCH CONTROLEPANEEL ---
st.title("📈 Unique-Match Parlay Builder")

with st.container():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    target_total = c1.number_input("Target Slip Odds", value=2.5, step=0.1)
    match_count = c2.slider("Aantal Unieke Matchen / Slip", 1, 5, 2)
    min_odd_val = c3.number_input("Min. Odd per Match", value=1.20)
    max_odd_val = c4.number_input("Max. Odd per Match", value=3.00)

    f1, f2, f3 = st.columns(3)
    time_window = f1.selectbox("Starttijd (Enkel Toekomst)", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 6 uur", "Vandaag"])
    min_prob_val = f2.slider("Minimale Zekerheid (%)", 30, 95, 55)
    st.markdown('</div>', unsafe_allow_html=True)

# --- GENERATOR LOGICA ---
if st.button("🚀 GENEREER PARLAYS"):
    try:
        with st.spinner("Scannen op toekomstige unieke wedstrijden..."):
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            fix_res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) # NS = Not Started
            fix_data = fix_res.json()

            if not fix_data.get('response'):
                st.warning("Geen aankomende wedstrijden gevonden.")
            else:
                now_ts = int(time.time())
                t_limit = {"Volgende 1 uur": 1, "Volgende 2 uur": 2, "Volgende 6 uur": 6, "Vandaag": 24}[time_window]
                
                # Verzamel odds per unieke wedstrijd
                match_pool = []
                for f in fix_data['response']:
                    ts = f['fixture']['timestamp']
                    diff_h = (ts - now_ts) / 3600
                    
                    # Alleen strikt in de toekomst en binnen venster
                    if 0.05 <= diff_h <= t_limit: 
                        f_id = f['fixture']['id']
                        
                        # Haal odds voor deze specifieke fixture
                        odd_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                        o_data = odd_res.json()
                        
                        if o_data.get('response'):
                            best_bet_for_match = None
                            highest_prob = 0
                            
                            for bm in o_data['response'][0]['bookmakers']:
                                for bet in bm['bets']:
                                    for val in bet['values']:
                                        odd = float(val['odd'])
                                        prob = round((1/odd) * 100 + 4.5, 1) # Model kans
                                        
                                        if min_odd_val <= odd <= max_odd_item and prob >= min_prob_val:
                                            # We bewaren alleen de 'beste' bet per wedstrijd voor de pool
                                            if prob > highest_prob:
                                                highest_prob = prob
                                                best_bet_for_match = {
                                                    "fixture_id": f_id,
                                                    "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                                                    "market": f"{bet['name']}: {val['value']}",
                                                    "odd": odd,
                                                    "prob": prob,
                                                    "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M'),
                                                    "league": f['league']['name']
                                                }
                            if best_bet_for_match:
                                match_pool.append(best_bet_for_match)

                # Bouw slips met unieke fixture_ids
                if len(match_pool) < match_count:
                    st.info("Niet genoeg unieke wedstrijden gevonden voor je criteria.")
                else:
                    # Sorteer op prob en maak combinaties
                    match_pool.sort(key=lambda x: x['prob'], reverse=True)
                    
                    # We maken slips door telkens X unieke matchen te pakken
                    slips = [match_pool[i:i + match_count] for i in range(0, len(match_pool), match_count)]
                    
                    for slip in slips[:10]:
                        if len(slip) == match_count:
                            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                            total_odd = 1.0
                            for m in slip:
                                total_odd *= m['odd']
                                c_m, c_o = st.columns([4, 1])
                                with c_m:
                                    st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                                    st.markdown(f"<div class='team-row'>{m['match']}</div>", unsafe_allow_html=True)
                                    st.caption(f"🕒 {m['time']} | {m['market']} ({m['league']})")
                                with c_o:
                                    st.markdown(f"<div class='odd-badge'>{m['odd']}</div>", unsafe_allow_html=True)
                                st.divider()
                            st.subheader(f"Slip Totaal: @{round(total_odd, 2)}")
                            st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Fout: {e}")
