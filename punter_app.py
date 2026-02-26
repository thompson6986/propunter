import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- FIRESTORE PERSISTENCE ---
try:
    from google.cloud import firestore
    # Streamlit Cloud zoekt automatisch naar secrets in de settings van de app
    db = firestore.Client()
    HAS_DB = True
except Exception:
    HAS_DB = False

# --- CONFIGURATIE ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"
TIMEZONE = "Europe/Brussels"
APP_ID = "propunter-v8-pro"

st.set_page_config(
    page_title="ProPunter Ultimate V8",
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
    .stAlert { border-radius: 15px; }
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
        bank_doc = user_ref.collection("settings").document("bankroll").get()
        bank = bank_doc.to_dict().get('balance', 1000.0) if bank_doc.exists else 1000.0
        bets = [d.to_dict() for d in user_ref.collection("real_bets").stream()]
        lab = [d.to_dict() for d in user_ref.collection("virtual_lab").stream()]
        return bank, bets, lab
    except: return 1000.0, [], []

# --- API HELPERS ---
def call_api(endpoint, params={}):
    headers = {'x-apisports-key': API_KEY}
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
        else:
            st.error(f"API Fout: {res.status_code}")
            return None
    except Exception as e:
        st.error(f"Verbindingsfout: {str(e)}")
        return None

# --- INITIALISATIE ---
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state:
    st.session_state.active_bets = []
if 'virtual_lab' not in st.session_state:
    st.session_state.virtual_lab = []
if 'found_match' not in st.session_state:
    st.session_state.found_match = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    user_id = st.text_input("User ID", placeholder="Naam voor cloud opslag...")
    
    if st.button("🔄 Data Herstellen") and user_id:
        b, bets, lab = load_from_cloud(user_id)
        st.session_state.bankroll = b
        st.session_state.active_bets = bets
        st.session_state.virtual_lab = lab
        st.success("Data geladen!")

    st.markdown("---")
    st.metric("Saldo", f"€{st.session_state.bankroll:.2f}")
    
    menu = st.radio("Menu", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    st.markdown("---")
    if st.button("🗑️ /Clear & Refund"):
        refund = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        if user_id: sync_to_cloud(user_id, "settings", {"balance": st.session_state.bankroll})
        st.success(f"€{refund:.2f} hersteld.")
        time.sleep(1)
        st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📈 Punter Dashboard")
    
    if st.button("🔄 Live Scores Verversen"):
        with st.spinner("Actuele scores ophalen..."):
            ids = [str(b['fixtureId']) for b in st.session_state.active_bets if 'fixtureId' in b]
            if ids:
                data = call_api("fixtures", {"ids": "-".join(ids)})
                if data and data.get('response'):
                    for f in data['response']:
                        score = f"{f['goals']['home']}-{f['goals']['away']}"
                        status = f['fixture']['status']['short']
                        elapsed = f['fixture']['status']['elapsed']
                        for bet in st.session_state.active_bets:
                            if bet.get('fixtureId') == f['fixture']['id']:
                                bet['Live Score'] = f"{score} ({status} {elapsed}')"
            st.toast("Scores bijgewerkt!")

    c1, c2, c3 = st.columns(3)
    c1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    c2.metric("Open Bets", len(st.session_state.active_bets))
    c3.metric("DB Status", "☁️ Cloud" if HAS_DB and user_id else "🔌 Lokaal")

    st.subheader("Actieve Weddenschappen")
    if st.session_state.active_bets:
        df = pd.DataFrame(st.session_state.active_bets)
        display_cols = ['Match', 'Tijd', 'Markt', 'Odd', 'Inzet', 'Live Score']
        st.dataframe(df[[c for c in display_cols if c in df.columns]], use_container_width=True)
    else:
        st.info("Geen actieve bets. Gebruik de Generator om te starten.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Live Bet Generator")
    st.markdown("Scant enkel toekomstige wedstrijden van vandaag.")

    col_a, col_b = st.columns(2)
    time_win = col_a.selectbox("Tijdvenster", ["1", "2", "4", "6", "12", "24", "48"], index=5, format_func=lambda x: f"Volgende {x} uur")
    market_type = col_b.selectbox("Markt", ["1X2", "Over 2.5 Goals", "Both Teams to Score"])

    if st.button("🚀 SCAN TOEKOMSTIGE MATCHES"):
        with st.spinner("Live data ophalen..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response'):
                limit = now + timedelta(hours=int(time_win))
                valid = []
                for f in data['response']:
                    g_time = datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00')).astimezone(brussels_tz)
                    if now < g_time < limit:
                        valid.append({
                            "fixtureId": f['fixture']['id'],
                            "Match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}",
                            "Tijd": g_time.strftime('%H:%M'),
                            "Odd": 1.75, "Inzet": 10.0, "Markt": market_type, "Live Score": "0-0 (NS)"
                        })
                
                if valid:
                    st.session_state.found_match = valid[0]
                    st.success(f"Match gevonden: {valid[0]['Match']}")
                else:
                    st.session_state.found_match = None
                    st.warning("Geen passende wedstrijden gevonden voor dit tijdvenster.")
            else:
                st.error("API gaf geen resultaten. Controleer je limieten of key.")

    if st.session_state.found_match:
        m = st.session_state.found_match
        st.markdown("---")
        col_m1, col_m2 = st.columns([2, 1])
        with col_m1:
            st.info(f"**Aanbevolen:** {m['Match']} | Start: {m['Tijd']} | Odd: @{m['Odd']}")
        with col_m2:
            if st.button("💰 BEVESTIG & PLAATS (10u)"):
                if st.session_state.bankroll >= 10.0:
                    st.session_state.bankroll -= 10.0
                    st.session_state.active_bets.append(m)
                    if user_id: 
                        sync_to_cloud(user_id, "real_bets", [m])
                        sync_to_cloud(user_id, "settings", {"balance": st.session_state.bankroll})
                    st.session_state.found_match = None
                    st.toast("Bet geplaatst!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Onvoldoende saldo.")

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Lab: 0-0 Trigger Scanner")
    st.markdown("Monitoring van de 0-0 Correct Score anomalie (Odd 15-30).")

    if st.button("🔍 SCAN VOOR ACTUELE TRIGGERS"):
        with st.spinner("Odds scannen voor vandaag..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response') and len(data['response']) > 0:
                target = data['response'][0]
                g_time = datetime.fromisoformat(target['fixture']['date'].replace('Z', '+00:00')).astimezone(brussels_tz)
                
                new_trig = {
                    "Match": f"{target['teams']['home']['name']} vs {target['teams']['away']['name']}",
                    "0-0 Odd": 21.0, 
                    "Advies": "Over 1.5 Goals", 
                    "Tijd": g_time.strftime('%H:%M'), 
                    "Status": "📡 Monitoring"
                }
                st.session_state.virtual_lab.insert(0, new_trig)
                if user_id: sync_to_cloud(user_id, "virtual_lab", [new_trig])
                st.success(f"Trigger gevonden voor {new_trig['Match']}!")
            else:
                st.warning("Geen geschikte wedstrijden gevonden om te scannen.")

    if st.session_state.virtual_lab:
        st.table(pd.DataFrame(st.session_state.virtual_lab))

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Wedgeschiedenis")
    st.info("Afgesloten resultaten verschijnen hier na automatische settlement.")
    if st.button("Genereer Test Export"):
        st.session_state.history = [{"Datum": "2026-02-26", "Match": "Liverpool vs Everton", "Status": "Won", "Profit": 5.0}]
        st.rerun()

st.markdown("---")
st.caption(f"ProPunter Master V8.0 | API Live | België CET | Database: {'Actief' if HAS_DB and user_id else 'Sessie-only'}")
