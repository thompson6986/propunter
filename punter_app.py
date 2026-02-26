import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import time

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Betslip Generator Pro", page_icon="⚖️", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .slip-card { background-color: #1c2128; border: 1px solid #444c56; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
    .prob-tag { color: #2ecc71; font-weight: bold; font-size: 1.1rem; }
    .odd-box { background: #0d1117; padding: 10px; border-radius: 5px; text-align: center; border: 1px solid #30363d; }
    .meta-text { color: #8b949e; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTEN ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- STATE ---
if 'slips' not in st.session_state: st.session_state.slips = []

# --- HEADER & ADVANCED SETTINGS ---
st.title("⚖️ Betslip Generator")

# Top Row Settings
c1, c2, c3, c4 = st.columns(4)
target_odds = c1.number_input("Target Odds", value=2.5, step=0.1)
items_per_slip = c2.number_input("Items /Slip", value=2, min_value=1)
min_odd_item = c3.number_input("Min Odds /Item", value=1.2)
max_odd_item = c4.number_input("Max Odds /Item", value=3.0)

with st.expander("🛠️ Advanced Filters & Timeframe", expanded=True):
    f1, f2, f3 = st.columns(3)
    # Tijdsloten zoals gevraagd
    time_filter = f1.selectbox("Starttijd binnen:", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 24 uur", "Volgende 72 uur"])
    sort_by = f2.selectbox("Sorteer op:", ["Probability", "Odds", "Value"])
    min_prob_global = f3.slider("Minimale Slaagkans %", 10, 95, 40)

# --- GENERATOR LOGIC ---
if st.button("🚀 GENEREER SLIPS", use_container_width=True):
    with st.spinner("Markten analyseren..."):
        headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
        
        # We halen fixtures op om de exacte teams en tijden te krijgen
        params = {'date': datetime.now(TIMEZONE).strftime('%Y-%m-%d')}
        res = requests.get(f"{BASE_URL}/odds", headers=headers, params=params)
        data = res.json()

        if data.get('response'):
            matches_pool = []
            now = datetime.now(TIMEZONE)

            for item in data['response']:
                # Tijd Filter Logica
                kickoff = datetime.fromisoformat(item['fixture']['date'].replace('+00:00', '')).replace(tzinfo=pytz.UTC).astimezone(TIMEZONE)
                hours_until = (kickoff - now).total_seconds() / 3600
                
                valid_time = False
                if time_filter == "Volgende 1 uur" and 0 <= hours_until <= 1: valid_time = True
                elif time_filter == "Volgende 2 uur" and 0 <= hours_until <= 2: valid_time = True
                elif time_filter == "Volgende 24 uur" and 0 <= hours_until <= 24: valid_time = True
                elif time_filter == "Volgende 72 uur": valid_time = True

                if valid_time:
                    # Teams ophalen uit de fixture data
                    home = item['fixture'].get('home', 'Home Team') # Fallback als key verschilt
                    away = item['fixture'].get('away', 'Away Team')
                    # Bij API-Football zit team info vaak in 'teams' object
                    if 'teams' in item:
                        home = item['teams']['home']['name']
                        away = item['teams']['away']['name']

                    for bm in item['bookmakers']:
                        for bet in bm['bets']:
                            for val in bet['values']:
                                odd = float(val['odd'])
                                prob = round((1/odd)*100 + 3, 1) # Berekende kans

                                if min_odd_item <= odd <= max_odd_item and prob >= min_prob_global:
                                    matches_pool.append({
                                        "teams": f"{home} vs {away}",
                                        "league": item['league']['name'],
                                        "market": f"{bet['name']}: {val['value']}",
                                        "time": kickoff.strftime('%H:%M'),
                                        "odd": odd,
                                        "prob": prob
                                    })

            # Sorteren en groeperen
            if sort_by == "Probability": matches_pool.sort(key=lambda x: x['prob'], reverse=True)
            
            # Maak slips op basis van Items/Slip
            st.session_state.slips = [matches_pool[i:i + int(items_per_slip)] for i in range(0, len(matches_pool), int(items_per_slip))]
            if not st.session_state.slips:
                st.warning("Geen wedstrijden gevonden voor dit tijdslot. Probeer een ruimer timeframe.")
        else:
            st.error("Geen data ontvangen van API. Check je limiet.")

# --- DISPLAY (BSG LOOK) ---
if st.session_state.slips:
    for slip in st.session_state.slips[:8]:
        if len(slip) == int(items_per_slip):
            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
            
            t_odd = 1.0
            t_prob = 0
            
            for m in slip:
                t_odd *= m['odd']
                t_prob += m['prob']
                
                col_m, col_o = st.columns([4, 1])
                with col_m:
                    st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                    st.write(f"**{m['market']}**")
                    st.markdown(f"<p class='meta-text'>{m['time']} | {m['teams']} ({m['league']})</p>", unsafe_allow_html=True)
                with col_o:
                    st.markdown(f"<div class='odd-box'><h3>{m['odd']}</h3><small>ODDS</small></div>", unsafe_allow_html=True)
                st.divider()

            # Slip Footer
            v1, v2, v3 = st.columns(3)
            v1.metric("Total Odds", f"{round(t_odd, 2)}")
            v2.metric("Avg Prob.", f"{round(t_prob/len(slip), 1)}%")
            v3.metric("Value Score", f"{round((t_prob/len(slip)) - (100/t_odd), 1)}%")
            
            st.markdown('</div>', unsafe_allow_html=True)
