import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Pro Punter Dashboard", page_icon="⚽", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #238636; color: white; border-radius: 8px; font-weight: bold; height: 3em; }
    .control-panel { background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 25px; }
    .slip-card { background-color: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #238636; }
    .prob-tag { color: #3fb950; font-weight: bold; font-size: 1.2rem; }
    .team-row { font-size: 1.15rem; font-weight: 600; color: #adbac7; margin: 10px 0; }
    .odd-badge { background: #21262d; padding: 8px 15px; border-radius: 6px; border: 1px solid #30363d; font-weight: bold; color: #58a6ff; font-size: 1.1rem; }
    .status-live { color: #f85149; font-weight: bold; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    </style>
    """, unsafe_allow_html=True)

# --- DB & API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

if "firebase" in st.secrets and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client() if firebase_admin._apps else None

# --- STATE ---
if 'generated_slips' not in st.session_state: st.session_state.generated_slips = []

# --- TABS ---
t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 Live Portfolio & Cash-out"])

# --- TAB 1: GENERATOR ---
with t1:
    st.title("🚀 Professional Parlay Generator")
    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        match_count = c1.slider("Unieke Matchen per Slip", 1, 5, 2)
        min_odd_val = c2.number_input("Min. Odd / Match", value=1.20)
        max_odd_val = c3.number_input("Max. Odd / Match", value=2.50)
        time_window = c4.selectbox("Tijdvenster", ["1 uur", "2 uur", "6 uur", "Vandaag"])

        m1, m2, m3, m4 = st.columns(4)
        allow_winner = m1.checkbox("Match Winner (1X2)", value=True)
        allow_dc = m2.checkbox("Double Chance", value=True)
        allow_ou = m3.checkbox("Over/Under Goals", value=True)
        allow_btts = m4.checkbox("BTTS", value=False)
        
        min_prob_val = st.slider("Minimale Zekerheid (%)", 30, 95, 60)
        user_id = st.text_input("User ID (om slips op te slaan)", value="punter_01")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 GENEREER NIEUWE SLIPS"):
        try:
            with st.spinner("Scannen op professionele markten..."):
                today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
                fix_res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': today, 'status': 'NS'}) 
                fix_data = fix_res.json()

                if fix_data.get('response'):
                    now_ts = int(time.time())
                    t_hrs = {"1 uur": 1, "2 uur": 2, "6 uur": 6, "Vandaag": 24}[time_window]
                    
                    match_pool = []
                    for f in fix_data['response']:
                        ts = f['fixture']['timestamp']
                        if 0.01 <= (ts - now_ts)/3600 <= t_hrs:
                            f_id = f['fixture']['id']
                            o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id})
                            o_data = o_res.json()
                            
                            if o_data.get('response'):
                                best_match_bet = None
                                highest_p = 0
                                for bm in o_data['response'][0]['bookmakers']:
                                    for bet in bm['bets']:
                                        b_name = bet['name']
                                        is_allowed = (b_name == "Match Winner" and allow_winner) or \
                                                     (b_name == "Double Chance" and allow_dc) or \
                                                     ("Over/Under" in b_name and allow_ou) or \
                                                     (b_name == "Both Teams Score" and allow_btts)
                                        
                                        if is_allowed:
                                            for val in bet['values']:
                                                if any(x in val['value'] for x in ["Asian", "Half"]): continue
                                                odd = float(val['odd'])
                                                prob = round((1/odd)*100 + 4.5, 1)
                                                if min_odd_val <= odd <= max_odd_val and prob >= min_prob_val:
                                                    if prob > highest_p:
                                                        highest_p = prob
                                                        best_match_bet = {
                                                            "fixture_id": f_id,
                                                            "match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", 
                                                            "market": f"{b_name}: {val['value']}", 
                                                            "odd": odd, "prob": prob, 
                                                            "time": datetime.fromtimestamp(ts, TIMEZONE).strftime('%H:%M')
                                                        }
                                if best_match_bet: match_pool.append(best_match_bet)
                    
                    match_pool.sort(key=lambda x: x['prob'], reverse=True)
                    st.session_state.generated_slips = [match_pool[i:i + match_count] for i in range(0, len(match_pool), match_count)]
        except Exception as e: st.error(f"Fout: {e}")

    # Toon Slips
    if st.session_state.generated_slips:
        for i, slip in enumerate(st.session_state.generated_slips[:8]):
            if len(slip) == match_count:
                st.markdown('<div class="slip-card">', unsafe_allow_html=True)
                total_o = 1.0
                for m in slip:
                    total_o *= m['odd']
                    st.markdown(f"<span class='prob-tag'>{m['prob']}% Prob.</span> <span class='team-row'>{m['match']}</span>", unsafe_allow_html=True)
                    st.caption(f"{m['time']} | {m['market']} | @{m['odd']}")
                
                final_odd = round(total_o, 2)
                st.markdown(f"**Totaal Odds: @{final_odd}**")
                if st.button(f"💾 Sla Slip {i+1} op", key=f"save_{i}"):
                    if db:
                        db.collection("saved_slips").add({
                            "user_id": user_id, "timestamp": datetime.now(TIMEZONE),
                            "total_odd": final_odd, "matches": slip, "status": "Open"
                        })
                        st.success("Opgeslagen in je portfolio!")
                st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: LIVE TRACKER & CASHOUT ---
with t2:
    st.title("📡 Live Tracker & Cash-out")
    if db:
        try:
            # Query met DESCENDING sortering
            saved = (db.collection("saved_slips")
                     .where("user_id", "==", user_id)
                     .order_by("timestamp", direction=firestore.Query.DESCENDING)
                     .limit(10).get())
            
            if not saved:
                st.info("Sla eerst een slip op in de Generator tab.")
            else:
                f_ids = []
                docs_data = []
                for doc in saved:
                    d = doc.to_dict(); d['id'] = doc.id; docs_data.append(d)
                    for m in d['matches']: f_ids.append(m['fixture_id'])
                
                live_updates = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []):
                            live_updates[f['fixture']['id']] = f

                for s in docs_data:
                    with st.expander(f"Slip @{s['total_odd']} | {s['timestamp'].strftime('%d/%m %H:%M')}"):
                        win_count = 0
                        total_matches = len(s['matches'])
                        
                        for m in s['matches']:
                            f_id = m['fixture_id']
                            f_data = live_updates.get(f_id)
                            st.write(f"**{m['match']}** ({m['market']})")
                            
                            if f_data:
                                score = f"{f_data['goals']['home']} - {f_data['goals']['away']}"
                                status = f_data['fixture']['status']['short']
                                if status in ['1H', '2H', 'HT']:
                                    st.markdown(f"<span class='status-live'>LIVE {score}</span>", unsafe_allow_html=True)
                                elif status == 'FT':
                                    win_count += 1
                                    st.write(f"🏁 Eindstand: {score}")
                                else:
                                    st.caption(f"Status: {status} | Score: {score}")
                        
                        # BEREKEN CASHOUT (Voorbeeld inzet €10)
                        if win_count > 0:
                            cash_val = round((10 * s['total_odd']) * (win_count / total_matches) * 0.82, 2)
                            st.success(f"💰 Voorgestelde Cash-out: €{max(cash_val, 1.0)}")
                        
                        if st.button("🗑️ Verwijder Slip", key=f"del_{s['id']}"):
                            db.collection("saved_slips").document(s['id']).delete()
                            st.rerun()
        except Exception as e:
            st.warning("Database index wordt nog opgebouwd in Firebase. Probeer het over 2 minuten opnieuw voor de Live Tracker.")
