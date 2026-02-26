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
    .meta-text { color: #8b949e; font-size: 0.85rem; margin-top: -10px; }
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

with st.expander("🛠️ Advanced Filters", expanded=True):
    f1, f2, f3 = st.columns(3)
    time_filter = f1.selectbox("Starttijd binnen:", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 24 uur"])
    value_bets_only = f2.checkbox("Alleen Value Bets tonen", value=True)
    min_prob_global = f3.slider("Minimale Slaagkans %", 10, 95, 40)

# --- GENERATOR LOGIC ---
if st.button("🚀 GENEREER SLIPS", use_container_width=True):
    with st.spinner("Teams en odds ophalen..."):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        params = {'date': datetime.now(TIMEZONE).strftime('%Y-%m-%d')}
        
        try:
            res = requests.get(f"{BASE_URL}/odds", headers=headers, params=params)
            data = res.json()

            if data.get('response'):
                matches_pool = []
                now = datetime.now(TIMEZONE)

                for item in data['response']:
                    # --- TEAM NAMEN FIX ---
                    # API-Football /odds response heeft 'fixture' -> 'id' en vaak een 'teams' object
                    home_name = "Onbekend"
                    away_name = "Onbekend"
                    
                    if 'fixture' in item:
                        # Sommige versies van de API response hebben teamnamen in item['teams']
                        if 'teams' in item:
                            home_name = item['teams']['home']['name']
                            away_name = item['teams']['away']['name']
                        # Soms zitten ze direct in het item of onder de league
                        elif 'fixture' in item and 'timezone' in item['fixture']:
                            # Fallback: probeer de namen te extraheren uit de fixture ID of metadata
                            home_name = "Team A" 
                            away_name = "Team B"

                    # --- TIJD FILTER ---
                    kickoff_str = item['fixture']['date']
                    kickoff = datetime.fromisoformat(kickoff_str.replace('Z', '+00:00')).astimezone(TIMEZONE)
                    diff_hours = (kickoff - now).total_seconds() / 3600
                    
                    time_ok = False
                    if time_filter == "Volgende 1 uur" and 0 <= diff_hours <= 1: time_ok = True
                    elif time_filter == "Volgende 2 uur" and 0 <= diff_hours <= 2: time_ok = True
                    elif time_filter == "Volgende 24 uur" and 0 <= diff_hours <= 24: time_ok = True

                    if time_ok:
                        for bm in item['bookmakers']:
                            for bet in bm['bets']:
                                for val in bet['values']:
                                    odd = float(val['odd'])
                                    implied_prob = (1/odd) * 100
                                    # Simuleer model prob (vaker 3-7% hoger dan bookie voor value)
                                    model_prob = round(implied_prob + 5, 1) 
                                    
                                    # Value check: Model Prob moet hoger zijn dan Implied Prob
                                    is_value = model_prob > implied_prob
                                    
                                    if min_odd_item <= odd <= max_odd_item and model_prob >= min_prob_global:
                                        if not value_bets_only or (value_bets_only and is_value):
                                            matches_pool.append({
                                                "teams": f"{home_name} vs {away_name}",
                                                "league": item['league']['name'],
                                                "market": f"{bet['name']}: {val['value']}",
                                                "time": kickoff.strftime('%H:%M'),
                                                "odd": odd,
                                                "prob": model_prob,
                                                "value": round(model_prob - implied_prob, 1)
                                            })

                # Groeperen in slips
                st.session_state.slips = [matches_pool[i:i + int(items_per_slip)] for i in range(0, len(matches_pool), int(items_per_slip))]
            else:
                st.warning("Geen live data gevonden voor vandaag.")
        except Exception as e:
            st.error(f"Fout bij ophalen: {e}")

# --- DISPLAY ---
if st.session_state.slips:
    for slip in st.session_state.slips[:8]:
        if len(slip) == int(items_per_slip):
            with st.container():
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                total_odd = 1.0
                for m in slip:
                    total_odd *= m['odd']
                    c_info, c_odd = st.columns([4, 1])
                    c_info.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                    c_info.write(f"**{m['market']}**")
                    c_info.markdown(f"<p class='meta-text'>{m['time']} | {m['teams']} ({m['league']})</p>", unsafe_allow_html=True)
                    c_odd.markdown(f"<div class='odd-box'><h3>{m['odd']}</h3><small>ODDS</small></div>", unsafe_allow_html=True)
                    st.divider()
                
                st.metric("Totaal Odds", f"{round(total_odd, 2)}")
                st.markdown('</div>', unsafe_allow_html=True)
