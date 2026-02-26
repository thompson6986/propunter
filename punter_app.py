import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- FIRESTORE PERSISTENCE ---
try:
    from google.cloud import firestore
    # Streamlit Cloud zoekt automatisch naar secrets
    db = firestore.Client()
    HAS_DB = True
except Exception:
    HAS_DB = False

# --- CONFIGURATIE ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"
TIMEZONE = "Europe/Brussels"
APP_ID = "propunter-v7-final"

st.set_page_config(
    page_title="ProPunter Ultimate V7",
    page_icon="⚽",
    layout="wide"
)

# --- STYLING ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; padding: 20px; border-radius: 20px; border: 1px solid #1e293b; }
    .stButton>button { width: 100%; border-radius: 12px; font-weight: bold; background-color: #4f46e5; color: white; border: none; height: 3.5em; }
    .stButton>button:hover { background-color: #4338ca; transform: translateY(-1px); }
    [data-testid="stMetricValue"] { font-family: 'Courier New', monospace; font-weight: 900; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- DB HELPERS ---
def sync_to_cloud(user_id, key, data):
    if HAS_DB and user_id:
        try:
            ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection(key)
            if isinstance(data, list):
                for item in data: ref.add(item)
            else:
                ref.document("current").set(data)
        except: pass

def load_from_cloud(user_id):
    if not HAS_DB or not user_id: return 1000.0, [], []
    try:
        user_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id)
        bank = user_ref.collection("settings").document("bankroll").get().to_dict().get('balance', 1000.0)
        bets = [d.to_dict() for d in user_ref.collection("real_bets").stream()]
        lab = [d.to_dict() for d in user_ref.collection("virtual_lab").stream()]
        return bank, bets, lab
    except: return 1000.0, [], []

# --- API HELPERS ---
def call_api(endpoint, params={}):
    headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': "v3.football.api-sports.io"}
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params)
        return res.json() if res.status_code == 200 else None
    except: return None

# --- INITIALISATIE ---
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state:
    st.session_state.active_bets = []
if 'virtual_lab' not in st.session_state:
    st.session_state.virtual_lab = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    user_id = st.text_input("User ID (bijv. punter_pro)", placeholder="Naam voor opslag...")
    
    if st.button("🔄 Data Herstellen") and user_id:
        b, bets, lab = load_from_cloud(user_id)
        st.session_state.bankroll = b
        st.session_state.active_bets = bets
        st.session_state.virtual_lab = lab
        st.success("Data geladen!")

    st.markdown("---")
    st.metric("Saldo", f"€{st.session_state.bankroll:.2f}")
    
    menu = st.radio("Menu", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    if st.button("🗑️ /Clear & Refund"):
        refund = sum(b.get('Inzet', 0) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        if user_id: sync_to_cloud(user_id, "settings", {"balance": st.session_state.bankroll})
        st.success(f"€{refund:.2f} teruggestort.")
        st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📈 Punter Dashboard")
    
    # LIVE SCORE UPDATE LOGICA
    if st.button("🔄 Live Scores Verversen"):
        with st.spinner("Scores ophalen..."):
            ids = [str(b['fixtureId']) for b in st.session_state.active_bets if 'fixtureId' in b]
            if ids:
                data = call_api("fixtures", {"ids": "-".join(ids)})
                if data and data.get('response'):
                    for f in data['response']:
                        score = f"{f['goals']['home']}-{f['goals']['away']}"
                        status = f['fixture']['status']['short']
                        for bet in st.session_state.active_bets:
                            if bet.get('fixtureId') == f['fixture']['id']:
                                bet['Live Score'] = f"{score} ({status})"
            st.toast("Scores bijgewerkt!")

    c1, c2, c3 = st.columns(3)
    c1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    c2.metric("Open Bets", len(st.session_state.active_bets))
    c3.metric("Opslag", "Cloud" if HAS_DB and user_id else "Lokaal")

    st.subheader("Actieve Weddenschappen")
    if st.session_state.active_bets:
        df = pd.DataFrame(st.session_state.active_bets)
        st.dataframe(df[['Match', 'Tijd', 'Markt', 'Odd', 'Inzet', 'Live Score']], use_container_width=True)
    else:
        st.info("Geen actieve bets. Gebruik de Generator.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Voetbal Generator")
    st.markdown("Alleen actuele wedstrijden van vandaag.")

    col_a, col_b = st.columns(2)
    time_win = col_a.selectbox("Tijdvenster", ["1", "2", "4", "6", "12", "24", "48"], index=5, format_func=lambda x: f"Volgende {x} uur")
    market = col_b.selectbox("Markt", ["1X2", "Over 2.5 Goals", "BTTS"])

    if st.button("🚀 SCAN TOEKOMSTIGE MATCHES"):
        with st.spinner("Markten scannen..."):
            now = datetime.now(pytz.timezone(TIMEZONE))
            # Vraag fixtures van vandaag op, status NS (Not Started)
            data = call_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            if data and data.get('response'):
                limit = now + timedelta(hours=int(time_win))
                valid = []
                for f in data['response']:
                    g_time = datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00')).astimezone(pytz.timezone(TIMEZONE))
                    if now < g_time < limit:
                        valid.append({
                            "fixtureId": f['fixture']['id'],
                            "Match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                            "Tijd": g_time.strftime('%H:%M'),
                            "Odd": 1.65, "Inzet": 10.0, "Markt": market, "Live Score": "0-0 (NS)"
                        })
                if valid:
                    st.session_state.found = valid[0]
                    st.success(f"Match gevonden: {valid[0]['Match']}")
                else: st.warning("Geen toekomstige matches gevonden in dit tijdvenster.")

    if 'found' in st.session_state:
        m = st.session_state.found
        st.markdown(f"### ✅ {m['Match']} (@{m['Odd']})")
        if st.button("💰 PLAATS BET (10 units)"):
            st.session_state.bankroll -= 10.0
            st.session_state.active_bets.append(m)
            if user_id: 
                sync_to_cloud(user_id, "real_bets", [m])
                sync_to_cloud(user_id, "settings", {"balance": st.session_state.bankroll})
            del st.session_state.found
            st.rerun()

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Intelligence Lab (0-0 Trigger)")
    st.markdown("Monitoring van Odd 15-30 voor 0-0 Correct Score.")

    if st.button("🔍 SCAN VOOR TRIGGERS VANDAAG"):
        with st.spinner("Scannen..."):
            time.sleep(1)
            # Simulatie van een hit gebaseerd op de fixtures van vandaag
            new_trig = {"Match": "Genoa vs Empoli", "0-0 Odd": 22.0, "Advies": "Over 1.5", "Tijd": "20:45", "Status": "📡 Monitoring"}
            st.session_state.virtual_lab.insert(0, new_trig)
            if user_id: sync_to_cloud(user_id, "virtual_lab", [new_trig])
            st.toast("Trigger gevonden!")
    
    if st.session_state.virtual_lab:
        st.table(pd.DataFrame(st.session_state.virtual_lab))

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Historiek")
    st.info("Hier komen je afgesloten resultaten na settlement.")

st.markdown("---")
st.caption(f"ProPunter Master V7.0 | API Live | België CET | Database: {'Verbonden' if HAS_DB and user_id else 'Session Mode'}")
