import streamlit as st
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Elite V90", page_icon="📝", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .builder-panel { background: #1c2128; border: 2px dashed #30363d; padding: 20px; border-radius: 12px; margin-bottom: 25px; }
    .selection-row { display: flex; justify-content: space-between; padding: 10px; background: #0d1117; border-radius: 8px; margin-bottom: 8px; border: 1px solid #30363d; }
    .total-box { background: #23863622; border: 1px solid #238636; padding: 15px; border-radius: 10px; text-align: center; font-size: 1.2rem; }
    .delete-btn { color: #f85149; cursor: pointer; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
if not firebase_admin._apps and "firebase" in st.secrets:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)
db = firestore.client() if firebase_admin._apps else None

# --- SESSION STATE VOOR BUILDER ---
if 'my_selections' not in st.session_state:
    st.session_state.my_selections = []

# --- APP TABS ---
t1, t2, t3 = st.tabs(["🚀 MIJN BETSLIP BUILDER", "📊 DEEP ANALYSIS", "📈 TRACKER"])

with t1:
    st.header("📝 Custom Betslip Builder")
    st.markdown('<div class="builder-panel">', unsafe_allow_html=True)
    
    if not st.session_state.my_selections:
        st.info("Voeg selecties toe vanuit de 'Deep Analysis' tab om je slip te bouwen.")
    else:
        total_odd = 1.0
        for i, sel in enumerate(st.session_state.my_selections):
            total_odd *= sel['odd']
            st.markdown(f'''
                <div class="selection-row">
                    <div><b>{sel['match']}</b><br><small>{sel['market']}</small></div>
                    <div style="text-align:right;"><b>@{sel['odd']}</b></div>
                </div>
            ''', unsafe_allow_html=True)
            if st.button(f"Verwijder", key=f"del_{i}"):
                st.session_state.my_selections.pop(i)
                st.rerun()

        st.markdown(f'''
            <div class="total-box">
                Totaal Odd: <b>@{total_odd:.2f}</b><br>
                <small>Potentiële winst bij €10: €{total_odd * 10:.2f}</small>
            </div>
        ''', unsafe_allow_html=True)
        
        if st.button("🔥 BEVESTIG DEZE COMBINATIE", use_container_width=True):
            if db:
                db.collection("saved_slips").add({
                    "user_id": "punter_01",
                    "timestamp": datetime.now(TIMEZONE),
                    "total_odd": round(total_odd, 2),
                    "matches": st.session_state.my_selections,
                    "stake": 10.0,
                    "status": "OPEN"
                })
                st.session_state.my_selections = []
                st.success("Combinatie opgeslagen in je Tracker!")
    st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.header("🔍 Deep Analysis")
    # In de analyse-tab voegen we nu een "+" knop toe i.p.v. direct bevestigen
    # VOORBEELD LOGICA:
    # if st.button("➕ Voeg toe aan slip", key=f"add_{f_id}"):
    #     st.session_state.my_selections.append({
    #         "match": f"{h} vs {a}", "market": "Over 1.5", "odd": 1.35
    #     })
    #     st.toast("Toegevoegd aan builder!")
    st.info("Klik op de '+' knop bij een match om deze naar je Builder (Tab 1) te sturen.")
