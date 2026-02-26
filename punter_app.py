import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Dashboard", page_icon="📈", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .bankroll-container { background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; margin-bottom: 25px; border-top: 4px solid #1f6feb; }
    .bet-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-bottom: 12px; position: relative; }
    .status-badge { position: absolute; top: 10px; right: 10px; background: #238636; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; }
    .win-amount { color: #3fb950; font-weight: bold; font-size: 1.1rem; }
    .match-time { color: #8b949e; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
@st.cache_resource
def init_db():
    if not firebase_admin._apps and "firebase" in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None
db = init_db()

# --- APP TABS ---
t1, t2, t3 = st.tabs(["📊 TRACKER & FINANCES", "🔍 DEEP ANALYSIS", "🏟️ LIVESCORE"])

with t1:
    # 1. Bankroll Sectie
    START_CAPITAL = 1200.00
    if db:
        docs = db.collection("saved_slips").where("user_id", "==", "punter_01").get()
        total_staked = sum([doc.to_dict().get('stake', 0) for doc in docs])
        current_balance = START_CAPITAL - total_staked
        
        st.markdown(f'''
            <div class="bankroll-container">
                <div style="display:flex; justify-content: space-around; text-align:center;">
                    <div><small>START SALDO</small><br><b>€{START_CAPITAL:.2f}</b></div>
                    <div><small>OPENSTAANDE INZET</small><br><b style="color:#f1e05a;">€{total_staked:.2f}</b></div>
                    <div><small>BESCHIKBAAR</small><br><b style="color:#58a6ff; font-size:1.5rem;">€{current_balance:.2f}</b></div>
                </div>
            </div>
        ''', unsafe_allow_html=True)

    # 2. Betslip Overzicht
    st.subheader("📝 Jouw Actieve Betslips")
    if db:
        active_bets = db.collection("saved_slips").where("user_id", "==", "punter_01").order_by("timestamp", direction=firestore.Query.DESCENDING).get()
        
        if not active_bets:
            st.info("Nog geen bets geplaatst voor vandaag.")
        
        for bet in active_bets:
            b = bet.to_dict()
            m = b['matches'][0]
            odd = float(b.get('total_odd', 1.0))
            stake = float(b.get('stake', 10.0))
            potential_win = stake * odd
            
            # Formatteer tijd als die beschikbaar is
            start_time = b.get('start_time', "Niet gespecificeerd")
            
            st.markdown(f'''
                <div class="bet-card">
                    <span class="status-badge">LIVE / OPEN</span>
                    <div class="match-time">🕒 Start: {start_time}</div>
                    <div style="font-size: 1.1rem; margin: 5px 0;"><b>{m['match']}</b></div>
                    <div style="color: #58a6ff;">Markt: {m.get('market', 'Match Result')} (@{odd})</div>
                    <hr style="border: 0.5px solid #30363d; margin: 10px 0;">
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <span>Inzet: €{stake:.2f}</span>
                        <span>Mogelijke Winst: <span class="win-amount">€{potential_win:.2f}</span></span>
                    </div>
                </div>
            ''', unsafe_allow_html=True)

with t2:
    st.header("🔍 Deep Analysis Engine")
    # Hier de verbeterde analyse code die ook de 'start_time' opslaat bij bevestiging
    if st.button("SCAN EUROPESE AVOND", use_container_width=True):
        # ... (API Logica om fixtures op te halen) ...
        # Zorg dat fixture['fixture']['timestamp'] wordt omgezet naar leesbaar uur
        pass

    # VOORBEELD HOE DE BEVESTIG KNOP NU WERKT:
    # Bij bevestiging voegen we nu de 'start_time' toe:
    # db.collection("saved_slips").add({
    #    "start_time": datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M'),
    #    "potential_payout": item['odd'] * 10.0,
    #    ...
    # })
