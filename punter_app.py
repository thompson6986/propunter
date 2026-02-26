import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

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

# --- HEADER & SETTINGS (BSG Style) ---
st.title("⚖️ Betslip Generator")

c1, c2, c3, c4 = st.columns(4)
target_odds = c1.number_input("Target Odds", value=2.5, step=0.1)
items_per_slip = c2.number_input("Items /Slip", value=2, min_value=1)
min_odd_item = c3.number_input("Min Odds /Item", value=1.2)
max_odd_item = c4.number_input("Max Odds /Item", value=3.0)

with st.expander("🛠️ Filters & Timeframe", expanded=True):
    f1, f2, f3 = st.columns(3)
    # Tijdfilter opties zoals gevraagd
    time_limit = f1.selectbox("Starttijd binnen:", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 24 uur"])
    sort_mode = f2.selectbox("Sorteren op:", ["Probability", "Value", "Odds"])
    min_prob_val = f3.slider("Minimale Slaagkans %", 5, 95, 30)

# --- GENERATOR LOGIC ---
if st.button("🚀 GENEREER PROFESSIONELE SLIPS", use_container_width=True):
    with st.spinner("Teams en live odds synchroniseren..."):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
        
        try:
            # 1. Haal de ODDS op
            res_odds = requests.get(f"{BASE_URL}/odds", headers=headers, params={'date': today})
            # 2. Haal de FIXTURES op (voor de teamnamen)
            res_fix = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today})
            
            data_odds = res_odds.json()
            data_fix = res_fix.json()

            if data_odds.get('response') and data_fix.get('response'):
                # Maak een map van fixture_id -> teamnamen
                fixture_map = {}
                for f in data_fix['response']:
                    fixture_map[f['fixture']['id']] = {
                        'home': f['teams']['home']['name'],
                        'away': f['teams']['away']['name'],
                        'league': f['league']['name'],
                        'timestamp': f['fixture']['timestamp']
                    }

                matches_pool = []
                now_ts = int(time.time())

                for item in data_odds['response']:
                    fix_id = item['fixture']['id']
                    
                    if fix_id in fixture_map:
                        f_info = fixture_map[fix_id]
                        
                        # TIJD FILTER BEREKENING
                        diff_hours = (f_info['timestamp'] - now_ts) / 3600
                        
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
                                        # Model Probability simulatie (Value logic)
                                        model_prob = round(implied + 4.5, 1)
                                        
                                        if min_odd_item <= odd <= max_odd_item and model_prob >= min_prob_val:
                                            matches_pool.append({
                                                "teams": f"{f_info['home']} vs {f_info['away']}",
                                                "league": f_info['league'],
                                                "market": f"{bet['name']}: {val['value']}",
                                                "time": datetime.fromtimestamp(f_info['timestamp'], TIMEZONE).strftime('%H:%M'),
                                                "odd": odd,
                                                "prob": model_prob,
                                                "value": round(model_prob - implied, 1)
                                            })

                # Sorteren
                if sort_mode == "Probability": matches_pool.sort(key=lambda x: x['prob'], reverse=True)
                elif sort_mode == "Value": matches_pool.sort(key=lambda x: x['value'], reverse=True)

                # Slips bouwen
                st.session_state.slips = [matches_pool[i:i + int(items_per_slip)] for i in range(0, len(matches_pool), int(items_per_slip))]
            else:
                st.warning("Geen data gevonden voor dit tijdslot.")
        except Exception as e:
            st.error(f"Fout: {e}")

# --- DISPLAY (BSG LOOK) ---
if st.session_state.slips:
    for slip in st.session_state.slips[:10]:
        if len(slip) == int(items_per_slip):
            with st.container():
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                total_odd = 1.0
                avg_val = 0
                for m in slip:
                    total_odd *= m['odd']
                    avg_val += m['value']
                    c_info, c_odd = st.columns([4, 1])
                    with c_info:
                        st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                        st.write(f"**{m['market']}**")
                        st.markdown(f"<p class='meta-text'>{m['time']} | {m['teams']} ({m['league']})</p>", unsafe_allow_html=True)
                    with c_odd:
                        st.markdown(f"<div class='odd-box'><h3>{m['odd']}</h3><small>ODDS</small></div>", unsafe_allow_html=True)
                    st.divider()
                
                v1, v2 = st.columns(2)
                v1.metric("Totaal Odds", f"{round(total_odd, 2)}")
                v2.metric("Value Score", f"+{round(avg_val/len(slip), 1)}%")
                st.markdown('</div>', unsafe_allow_html=True)
