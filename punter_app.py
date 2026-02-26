import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import time

# --- CONFIG & STYLING (Vastgehouden design) ---
st.set_page_config(page_title="Professional Betslip Builder", page_icon="📈", layout="wide")
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
st.title("📈 Professional Betslip Builder")

with st.container():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    target_total = c1.number_input("Target Slip Odds", value=2.5, step=0.1)
    match_count = c2.slider("Aantal Wedstrijden / Slip", 1, 5, 2)
    min_odd_val = c3.number_input("Min. Odd per Match", value=1.10)
    max_odd_val = c4.number_input("Max. Odd per Match", value=4.00)

    f1, f2, f3 = st.columns(3)
    time_window = f1.selectbox("Starttijd Venster", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 6 uur", "Vandaag"])
    min_prob_val = f2.slider("Minimale Model Probability (%)", 30, 95, 50)
    sort_logic = f3.selectbox("Sorteer op", ["Slaagkans", "Odds"])
    st.markdown('</div>', unsafe_allow_html=True)

# --- GENERATOR LOGICA (Fixtures-First) ---
if st.button("🚀 GENEREER BEREKENDE SLIPS"):
    try:
        with st.spinner("Live fixtures en odds synchroniseren..."):
            # 1. Haal fixtures van vandaag op om teamnamen te garanderen
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            fix_res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today})
            fix_data = fix_res.json()

            if not fix_data.get('response'):
                st.warning("Geen wedstrijden gevonden voor vandaag in de API.")
            else:
                now_ts = int(time.time())
                t_limit = {"Volgende 1 uur": 1, "Volgende 2 uur": 2, "Volgende 6 uur": 6, "Vandaag": 24}[time_window]
                
                # Filter relevante fixtures
                valid_fixtures = []
                for f in fix_data['response']:
                    ts = f['fixture']['timestamp']
                    diff_h = (ts - now_ts) / 3600
                    if 0 <= diff_h <= t_limit:
                        valid_fixtures.append(f)

                if not valid_fixtures:
                    st.info(f"Geen wedstrijden die starten binnen: {time_window}")
                else:
                    # 2. Haal odds op voor de gefilterde fixtures
                    pool = []
                    # We pakken de top 20 fixtures om API-limieten per scan te respecteren
                    for f in valid_fixtures[:20]:
                        f_id = f['fixture']['id']
                        home = f['teams']['home']['name']
                        away = f['teams']['away']['name']
                        league = f['league']['name']
                        kickoff = datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')

                        odd_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                        odd_data = odd_res.json()

                        if odd_data.get('response'):
                            for bm in odd_data['response'][0]['bookmakers']:
                                if bm['name'] in ['Bet365', '1xBet', 'Bwin']:
                                    for bet in bm['bets']:
                                        for val in bet['values']:
                                            odd = float(val['odd'])
                                            prob = round((1/odd) * 100 + 5, 1) # Model calculatie
                                            
                                            if min_odd_val <= odd <= max_odd_val and prob >= min_prob_val:
                                                pool.append({
                                                    "match": f"{home} vs {away}",
                                                    "market": f"{bet['name']}: {val['value']}",
                                                    "odd": odd,
                                                    "prob": prob,
                                                    "time": kickoff,
                                                    "league": league
                                                })

                    # 3. Slips bouwen
                    if sort_logic == "Slaagkans": pool.sort(key=lambda x: x['prob'], reverse=True)
                    
                    slips = [pool[i:i + match_count] for i in range(0, len(pool), match_count)]
                    
                    for slip in slips[:8]:
                        if len(slip) == match_count:
                            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                            t_odd = 1.0
                            for m in slip:
                                t_odd *= m['odd']
                                c_m, c_o = st.columns([4, 1])
                                with c_m:
                                    st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                                    st.markdown(f"<div class='team-row'>{m['match']}</div>", unsafe_allow_html=True)
                                    st.caption(f"🕒 {m['time']} | {m['market']} ({m['league']})")
                                with c_o:
                                    st.markdown(f"<div class='odd-badge'>{m['odd']}</div>", unsafe_allow_html=True)
                                st.divider()
                            st.subheader(f"Totaal Odds: @{round(t_odd, 2)}")
                            st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Systeemfout: {e}")
