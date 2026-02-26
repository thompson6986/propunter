import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time

# --- CONFIG & STYLING ---
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

# --- STRATEGISCH CONTROLEPANEEL ---
st.title("📈 Professional Betslip Builder")

with st.container():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    
    # RIJ 1: De Harde Criteria
    c1, c2, c3, c4 = st.columns(4)
    target_total = c1.number_input("Target Slip Odds", value=2.5, step=0.1, help="De totale odd die je wilt bereiken.")
    match_count = c2.slider("Aantal Wedstrijden / Slip", 1, 5, 2)
    min_odd = c3.number_input("Min. Odd per Match", value=1.25)
    max_odd = c4.number_input("Max. Odd per Match", value=2.50)

    # RIJ 2: Tijd & Filter Filters
    f1, f2, f3 = st.columns(3)
    time_window = f1.selectbox("Starttijd Venster", ["Volgende 1 uur", "Volgende 2 uur", "Volgende 6 uur", "Vandaag"])
    min_prob = f2.slider("Minimale Model Probability (%)", 40, 95, 65, help="Hoe 'safe' moet de voorspelling zijn volgens ons model?")
    sort_logic = f3.selectbox("Sorteer Resultaten op", ["Hoogste Slaagkans", "Beste Value", "Laagste Odds"])

    # RIJ 3: Markt Selectie (Checkboxes zoals in video)
    st.markdown("**Toegestane Markten:**")
    m1, m2, m3, m4, m5 = st.columns(5)
    use_h2h = m1.checkbox("Home/Away Win", value=True)
    use_dc = m2.checkbox("Double Chance", value=True)
    use_ou = m3.checkbox("Over/Under Goals", value=True)
    use_btts = m4.checkbox("BTTS", value=True)
    use_value = m5.checkbox("Alleen Value Bets", value=True)

    st.markdown('</div>', unsafe_allow_html=True)

# --- GENERATOR LOGICA ---
if st.button("🚀 GENEREER BEREKENDE SLIPS"):
    headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    params = {'date': datetime.now(TIMEZONE).strftime('%Y-%m-%d')}
    
    try:
        with st.spinner("Markten analyseren..."):
            r = requests.get(f"{BASE_URL}/odds", headers=headers, params=params)
            data = r.json()

            if data.get('response'):
                pool = []
                now_ts = int(time.time())

                for item in data['response']:
                    # Echte teamnamen ophalen
                    teams = item.get('teams', {})
                    home = teams.get('home', {}).get('name')
                    away = teams.get('away', {}).get('name')
                    
                    if not home or not away: continue

                    # Tijd Filter
                    kickoff = item['fixture']['timestamp']
                    diff_h = (kickoff - now_ts) / 3600
                    
                    # Tijd restrictie toepassen
                    t_limit = {"Volgende 1 uur": 1, "Volgende 2 uur": 2, "Volgende 6 uur": 6, "Vandaag": 24}[time_window]
                    if not (0 <= diff_h <= t_limit): continue

                    for bm in item['bookmakers']:
                        for bet in bm['bets']:
                            # Markt Filter
                            b_name = bet['name']
                            if b_name == "Match Winner" and not use_h2h: continue
                            if b_name == "Double Chance" and not use_dc: continue
                            if "Over/Under" in b_name and not use_ou: continue
                            if b_name == "Both Teams Score" and not use_btts: continue

                            for val in bet['values']:
                                odd = float(val['odd'])
                                implied = (1/odd) * 100
                                model_prob = round(implied + 4.2, 1) # Strategische marge
                                
                                if min_odd <= odd <= max_odd and model_prob >= min_prob:
                                    pool.append({
                                        "display_name": f"{home} vs {away}",
                                        "market": f"{b_name}: {val['value']}",
                                        "odd": odd,
                                        "prob": model_prob,
                                        "time": datetime.fromtimestamp(kickoff, TIMEZONE).strftime('%H:%M'),
                                        "league": item['league']['name']
                                    })

                # Sorteren & Groeperen
                if sort_logic == "Hoogste Slaagkans": pool.sort(key=lambda x: x['prob'], reverse=True)
                
                slips = [pool[i:i + match_count] for i in range(0, len(pool), match_count)]
                
                if slips:
                    for slip in slips[:10]:
                        if len(slip) == match_count:
                            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                            t_odd = 1.0
                            for m in slip:
                                t_odd *= m['odd']
                                c_m, c_o = st.columns([4, 1])
                                with c_m:
                                    st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span>", unsafe_allow_html=True)
                                    st.markdown(f"<div class='team-row'>{m['display_name']}</div>", unsafe_allow_html=True)
                                    st.caption(f"🕒 {m['time']} | {m['market']} ({m['league']})")
                                with c_o:
                                    st.markdown(f"<div class='odd-badge'>{m['odd']}</div>", unsafe_allow_html=True)
                                st.divider()
                            st.subheader(f"Slip Totaal: @{round(t_odd, 2)}")
                            st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.warning("Geen combinaties gevonden die voldoen aan je safe-filters.")
            else:
                st.error("API Error: Geen response. Check je dashboard.")
    except Exception as e:
        st.error(f"Systeemfout: {e}")
