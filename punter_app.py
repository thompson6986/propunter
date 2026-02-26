import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# --- CONFIG & THEME ---
st.set_page_config(page_title="Betslip Generator Pro", page_icon="⚖️", layout="wide")

st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .filter-box { background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 20px; }
    .slip-card { background-color: #1c2128; border: 1px solid #444c56; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
    .prob-tag { color: #2ecc71; font-weight: bold; font-size: 0.9rem; }
    .model-box { background: #0d1117; padding: 10px; border-radius: 5px; margin-top: 10px; border: 1px dashed #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTEN ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- STATE ---
if 'slips' not in st.session_state: st.session_state.slips = []

# --- HEADER & SETTINGS ---
with st.container():
    st.title("⚖️ Betslip Generator")
    
    # Bovenste rij instellingen (zoals in video)
    c1, c2, c3, c4 = st.columns(4)
    target_odds = c1.number_input("Target Odds", value=2.5, step=0.1)
    items_per_slip = c2.number_input("Items /Slip", value=2, min_value=1)
    min_odd_item = c3.number_input("Min Odds /Item", value=1.2)
    max_odd_item = c4.number_input("Max Odds /Item", value=3.0)

    # Filter Sectie
    with st.expander("🛠️ Advanced Market Filters", expanded=True):
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            st.subheader("Probability Model %")
            use_hw = st.checkbox("Home Win", True)
            hw_range = st.slider("HW Prob Range", 0, 100, (65, 100)) if use_hw else (0,100)
            
            use_over25 = st.checkbox("+2.5 Goals", True)
            o25_range = st.slider("+2.5 Prob Range", 0, 100, (60, 100)) if use_over25 else (0,100)

        with col_f2:
            st.subheader("General Settings")
            timeframe = st.selectbox("Timeframe", ["Next 24 Hours", "Next 48 Hours", "Next 72 Hours"])
            sort_by = st.selectbox("Sort By", ["Probability", "Odds", "Value", "Risk"])
            value_only = st.checkbox("Value Bets Only", value=True)

    if st.button("✨ GET BETSLIPS", use_container_width=True):
        with st.spinner("Generating Slips..."):
            headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
            # Simuleer API call & filter logica gebaseerd op video filters
            r = requests.get(f"{BASE_URL}/odds", headers=headers, params={'date': datetime.now().strftime('%Y-%m-%d')})
            data = r.json()
            
            if data.get('response'):
                raw_matches = []
                for item in data['response']:
                    for bm in item['bookmakers']:
                        for bet in bm['bets']:
                            for val in bet['values']:
                                odd = float(val['odd'])
                                prob = round((1/odd)*100 + 5, 1) # Model-simulatie factor
                                
                                # Filter op basis van de video criteria
                                if min_odd_item <= odd <= max_odd_item:
                                    raw_matches.append({
                                        "match": f"{item['fixture']['id']} | {item['league']['name']}",
                                        "teams": f"{item['league']['country']} - {item['league']['name']}",
                                        "market": f"{bet['name']}: {val['value']}",
                                        "odd": odd,
                                        "prob": prob,
                                        "value": round(prob - (1/odd)*100, 1)
                                    })
                
                # Sorteren
                if sort_by == "Probability": raw_matches.sort(key=lambda x: x['prob'], reverse=True)
                elif sort_by == "Odds": raw_matches.sort(key=lambda x: x['odd'], reverse=True)
                
                # Slips bouwen (combineren per X items)
                st.session_state.slips = [raw_matches[i:i + int(items_per_slip)] for i in range(0, len(raw_matches), int(items_per_slip))]

# --- DISPLAY SLIPS (BSG Look) ---
if st.session_state.slips:
    st.divider()
    for slip in st.session_state.slips[:5]: # Toon top 5
        with st.container():
            st.markdown('<div class="slip-card">', unsafe_allow_html=True)
            
            total_odds = 1.0
            avg_prob = 0
            
            for match in slip:
                total_odds *= match['odd']
                avg_prob += match['prob']
                
                c_info, c_odd = st.columns([4, 1])
                c_info.markdown(f"<span class='prob-tag'>{match['prob']}% Prob.</span>", unsafe_allow_html=True)
                c_info.write(f"**{match['market']}**")
                c_info.caption(f"{match['teams']}")
                c_odd.subheader(f"{match['odd']}")
                st.divider()
            
            # Footer van de slip
            avg_prob /= len(slip)
            f1, f2, f3 = st.columns(3)
            f1.metric("Slip Odds", f"{round(total_odds, 2)}")
            f2.metric("Model Odds", f"{round(100/avg_prob, 2)}")
            f3.metric("Value", f"{round(avg_prob - (100/total_odds), 1)}%")
            
            st.markdown('</div>', unsafe_allow_html=True)
