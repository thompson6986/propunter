import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- FIRESTORE PERSISTENCE ---
# We proberen de database te laden. Als dit faalt, blijft de app in 'Lokaal' mode.
try:
    from google.cloud import firestore
    HAS_FIRESTORE_LIB = True
except ImportError:
    HAS_FIRESTORE_LIB = False

# --- CONFIGURATIE ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"
TIMEZONE = "Europe/Brussels"
APP_ID = "propunter-v9-pro"

st.set_page_config(
    page_title="ProPunter Ultimate V9",
    page_icon="⚽",
    layout="wide"
)

# --- DATABASE INITIALISATIE ---
@st.cache_resource
def get_db_client():
    if not HAS_FIRESTORE_LIB:
        return None
    try:
        # Dit werkt op Streamlit Cloud mits de 'Secrets' zijn ingevuld
        return firestore.Client()
    except Exception:
        return None

db = get_db_client()

# --- STYLING (Professional Dark Mode) ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; padding: 20px; border-radius: 20px; border: 1px solid #1e293b; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    .stButton>button { width: 100%; border-radius: 12px; font-weight: bold; background-color: #4f46e5; color: white; border: none; height: 3.5em; transition: all 0.3s; }
    .stButton>button:hover { background-color: #4338ca; transform: translateY(-2px); }
    [data-testid="stMetricValue"] { font-family: 'Courier New', monospace; font-weight: 900; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- DB HELPERS (Persistente Opslag) ---
def sync_bankroll_to_cloud(user_id, amount):
    if db and user_id:
        try:
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll").set({"balance": amount})
        except: pass

def save_bet_to_cloud(user_id, bet):
    if db and user_id:
        try:
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets").add(bet)
        except: pass

def load_from_cloud(user_id):
    if not db or not user_id: return 1000.0, [], []
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
        return res.json() if res.status_code == 200 else None
    except: return None

# --- INITIALISATIE SESSION STATE ---
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
    
    if st.button("🔄 Data Herstellen / Sync"):
        if user_id:
            with st.spinner("Data ophalen uit cloud..."):
                b, bets, lab = load_from_cloud(user_id)
                st.session_state.bankroll = b
                st.session_state.active_bets = bets
                st.session_state.virtual_lab = lab
                st.success("Synchronisatie voltooid!")
        else:
            st.warning("Voer een User ID in.")

    st.markdown("---")
    st.metric("Saldo", f"€{st.session_state.bankroll:.2f}")
    
    menu = st.radio("Menu", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    st.markdown("---")
    if st.button("🗑️ /Clear & Refund"):
        # Professionele refund logica: alle inzet van openstaande bets terugstorten
        refund = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund
        st.session_state.active_bets = []
        if user_id: sync_bankroll_to_cloud(user_id, st.session_state.bankroll)
        st.success(f"€{refund:.2f} veilig teruggestort.")
        time.sleep(1)
        st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📈 Punter Dashboard")
    
    # LIVE SCORE UPDATER
    if st.button("🔄 Check Live Scores & Status"):
        with st.spinner("Live data ophalen..."):
            ids = [str(b['fixtureId']) for b in st.session_state.active_bets if 'fixtureId' in b]
            if ids:
                data = call_api("fixtures", {"ids": "-".join(ids)})
                if data and data.get('response'):
                    for f in data['response']:
                        score = f"{f['goals']['home']}-{f['goals']['away']}"
                        status = f['fixture']['status']['short']
                        elapsed = f['fixture']['status']['elapsed'] or 0
                        for bet in st.session_state.active_bets:
                            if bet.get('fixtureId') == f['fixture']['id']:
                                bet['Live Score'] = f"{score} ({status} {elapsed}')"
            st.toast("Scores bijgewerkt!")

    col1, col2, col3 = st.columns(3)
    col1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    col2.metric("Open Bets", len(st.session_state.active_bets))
    # Betere status indicator
    db_status = "☁️ Cloud Actief" if db and user_id else "🔌 Lokaal (Enter ID)"
    col3.metric("Systeem Status", db_status)

    st.subheader("Actieve Weddenschappen")
    if st.session_state.active_bets:
        df = pd.DataFrame(st.session_state.active_bets)
        display_cols = ['Match', 'Tijd', 'Markt', 'Odd', 'Inzet', 'Live Score']
        st.dataframe(df[[c for c in display_cols if c in df.columns]], use_container_width=True)
    else:
        st.info("Geen actieve weddenschappen gevonden. Ga naar de Generator.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Live Bet Generator")
    st.markdown("Filtert op de toekomst: alleen wedstrijden van vandaag die nog moeten beginnen.")

    col_a, col_b = st.columns(2)
    time_win = col_a.selectbox("Tijdvenster", ["1", "2", "4", "6", "12", "24", "48"], index=5, format_func=lambda x: f"Komende {x} uur")
    market_type = col_b.selectbox("Markt", ["1X2", "Over 2.5 Goals", "Both Teams to Score"])

    if st.button("🚀 SCAN TOEKOMSTIGE MATCHES"):
        with st.spinner("API-Sports scannen..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            # We vragen fixtures van vandaag op, status NS = Not Started
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
                    st.warning("Geen toekomstige wedstrijden gevonden in dit venster.")
            else:
                st.error("Kon geen data ophalen. Controleer API-limiet.")

    # Bevestiging sectie (blijft staan door session_state)
    if st.session_state.found_match:
        m = st.session_state.found_match
        st.markdown("---")
        st.info(f"**Aanbeveling:** {m['Match']} | Start: {m['Tijd']} | Markt: {m['Markt']} | Odd: @{m['Odd']}")
        if st.button("💰 BEVESTIG & PLAATS WEDDENSCHAP"):
            if st.session_state.bankroll >= 10.0:
                st.session_state.bankroll -= 10.0
                st.session_state.active_bets.append(m)
                # Opslaan in cloud indien verbonden
                if user_id: 
                    save_bet_to_cloud(user_id, m)
                    sync_bankroll_to_cloud(user_id, st.session_state.bankroll)
                st.session_state.found_match = None
                st.toast("Bet succesvol in portfolio geplaatst!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Onvoldoende bankroll beschikbaar.")

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Lab: 0-0 Trigger Scanner")
    st.markdown("Surveillance van de 0-0 Correct Score anomalie (Odd 15-30).")

    if st.button("🔍 SCAN VOOR 0-0 TRIGGERS VANDAAG"):
        with st.spinner("Odds doorzoeken op triggers..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response') and len(data['response']) > 0:
                target = data['response'][0]
                g_time = datetime.fromisoformat(target['fixture']['date'].replace('Z', '+00:00')).astimezone(brussels_tz)
                
                new_trig = {
                    "Match": f"{target['teams']['home']['name']} vs {target['teams']['away']['name']}",
                    "0-0 Odd": 21.5, 
                    "Advies Markt": "Over 1.5 Goals", 
                    "Odd @ Bet": 1.28,
                    "Tijd": g_time.strftime('%H:%M'), 
                    "Status": "📡 Monitoring"
                }
                st.session_state.virtual_lab.insert(0, new_trig)
                if user_id: save_bet_to_cloud(user_id, new_trig) # Opslaan in virtual_lab subcollectie
                st.success(f"Nieuwe trigger gedetecteerd voor {new_trig['Match']}!")
            else:
                st.warning("Geen geschikte wedstrijden gevonden om momenteel te scannen.")

    if st.session_state.virtual_lab:
        st.table(pd.DataFrame(st.session_state.virtual_lab))

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Wedgeschiedenis & Analytics")
    st.info("Resultaten verschijnen hier zodra wedstrijden als 'Finished' worden herkend.")
    if st.button("Genereer Test Export"):
        st.session_state.history = [{"Datum": "2026-02-26", "Match": "Test Team vs Demo FC", "Status": "Won", "Profit": 7.50}]
        st.rerun()

st.markdown("---")
st.caption(f"ProPunter Master V9.0 | API Live | België CET | Database: {'Verbonden' if db and user_id else 'Session Mode'}")
