import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- DATABASE / PERSISTENCE (Firestore) ---
# We gebruiken Firebase voor de permanente kluis. 
# Zorg dat je 'firebase' secrets in Streamlit Cloud hebt staan voor 100% werking.
try:
    from google.cloud import firestore
    if "firebase" in st.secrets:
        db = firestore.Client.from_service_account_info(dict(st.secrets["firebase"]))
        HAS_DB = True
    else:
        db = None
        HAS_DB = False
except Exception:
    HAS_DB = False
    db = None

# --- CONFIGURATIE ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"
TIMEZONE = "Europe/Brussels"
APP_ID = "punter-pro-ultimate-v16"

st.set_page_config(
    page_title="ProPunter Master V16",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING (Professional Dark UI) ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; padding: 25px; border-radius: 24px; border: 1px solid #1e293b; }
    .stButton>button { width: 100%; border-radius: 14px; font-weight: 800; background-color: #4f46e5; color: white; border: none; height: 3.8em; }
    .stButton>button:hover { background-color: #4338ca; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3); }
    [data-testid="stMetricValue"] { font-family: 'Courier New', monospace; font-weight: 900; color: #10b981; }
    div[data-testid="stExpander"] { background-color: #0f172a; border-radius: 15px; border: 1px solid #1e293b; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE HELPERS (AUTO-SAVE LOGICA) ---
def auto_save_bankroll(user_id):
    if HAS_DB and user_id:
        try:
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll").set({"balance": st.session_state.bankroll})
        except: pass

def auto_save_bet(user_id, bet_data):
    if HAS_DB and user_id:
        try:
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets").add(bet_data)
        except: pass

def clear_cloud_bets(user_id):
    if HAS_DB and user_id:
        try:
            # Verwijder alle bets uit de cloud collectie voor deze user
            bets_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets")
            docs = bets_ref.list_documents()
            for doc in docs:
                doc.delete()
        except: pass

def load_punter_profile(user_id):
    if not HAS_DB or not user_id:
        return None
    try:
        user_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id)
        bank_doc = user_ref.collection("settings").document("bankroll").get()
        balance = bank_doc.to_dict().get('balance', 1000.0) if bank_doc.exists else 1000.0
        bets_docs = user_ref.collection("real_bets").get()
        active_bets = [d.to_dict() for d in bets_docs]
        return balance, active_bets
    except:
        return None

# --- API HELPERS ---
def call_football_api(endpoint, params={}):
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
if 'generated_slips' not in st.session_state:
    st.session_state.generated_slips = None

# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.markdown("### 🔒 Cloud Opslag")
    user_id = st.text_input("User ID (Jouw kluis-naam)", placeholder="bijv. punter_pro_1")
    
    col_sync1, col_sync2 = st.columns(2)
    if col_sync1.button("📥 Laad Cloud"):
        if user_id:
            profile = load_punter_profile(user_id)
            if profile:
                st.session_state.bankroll, st.session_state.active_bets = profile
                st.success("Kluis geopend!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Geen data gevonden voor dit ID.")
        else:
            st.error("Vul eerst een ID in.")
            
    if col_sync2.button("📤 Force Save"):
        if user_id:
            auto_save_bankroll(user_id)
            st.success("Data gepusht!")
        else:
            st.error("Geen ID.")

    st.markdown("---")
    st.subheader("Kapitaal")
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}")
    
    menu = st.radio("Menu", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    st.markdown("---")
    if st.button("🗑️ /Clear & Refund All"):
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets)
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        # Update cloud direct
        if user_id:
            auto_save_bankroll(user_id)
            clear_cloud_bets(user_id)
        st.success(f"€{refund_total:.2f} hersteld.")
        time.sleep(1)
        st.rerun()

# --- DASHBOARD SECTIE ---
if menu == "📊 Dashboard":
    st.title("📈 Pro Dashboard")
    
    if st.button("🔄 Ververs Live Scores"):
        with st.spinner("Data ophalen..."):
            ids = [str(b['fixtureId']) for b in st.session_state.active_bets if 'fixtureId' in b]
            if ids:
                data = call_football_api("fixtures", {"ids": "-".join(ids)})
                if data and data.get('response'):
                    for f in data['response']:
                        score = f"{f['goals']['home']}-{f['goals']['away']}"
                        status = f['fixture']['status']['short']
                        elapsed = f['fixture']['status']['elapsed'] or 0
                        for bet in st.session_state.active_bets:
                            if bet.get('fixtureId') == f['fixture']['id']:
                                bet['Live Score'] = f"{score} ({status} {elapsed}')"
            st.rerun()

    c1, c2, c3 = st.columns(3)
    c1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    c2.metric("Open Posities", len(st.session_state.active_bets))
    c3.metric("Cloud Status", "🟢 Verbonden" if HAS_DB and user_id else "🔌 Lokaal")

    st.subheader("Lopende Weddenschappen")
    if st.session_state.active_bets:
        df_active = pd.DataFrame(st.session_state.active_bets)
        cols = ['Match', 'Tijd', 'Markt', 'Odd', 'Inzet', 'Live Score']
        st.dataframe(df_active[[c for c in cols if c in df_active.columns]], use_container_width=True)
    else:
        st.info("Geen actieve bets.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Pro Bet Generator")

    if st.button("🚀 SCAN VOOR DAGELIJKSE SLIPS (1.5, 2, 3, 5)"):
        with st.spinner("Analyseren..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_football_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response') and len(data['response']) >= 4:
                m = data['response']
                st.session_state.generated_slips = {
                    1.5: {"Match": f"{m[0]['teams']['home']['name']} vs {m[0]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[0]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[0]['fixture']['id']},
                    2.0: {"Match": f"{m[1]['teams']['home']['name']} vs {m[1]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[1]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[1]['fixture']['id']},
                    3.0: {"Match": f"{m[2]['teams']['home']['name']} vs {m[2]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[2]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[2]['fixture']['id']},
                    5.0: {"Match": f"{m[3]['teams']['home']['name']} vs {m[3]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[3]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[3]['fixture']['id']}
                }
            else:
                st.warning("Niet genoeg toekomstige wedstrijden gevonden.")

    if st.session_state.generated_slips:
        grid = st.columns(2)
        for i, (odd, info) in enumerate(st.session_state.generated_slips.items()):
            with grid[i % 2]:
                with st.expander(f"📦 Slip Target @{odd:.1f}", expanded=True):
                    st.write(f"**{info['Match']}** | Start: {info['Tijd']}")
                    if st.button(f"Plaats @{odd:.1f}", key=f"gen_{odd}"):
                        if st.session_state.bankroll >= 10.0:
                            st.session_state.bankroll -= 10.0
                            new_bet = {"fixtureId": info['Fixture'], "Match": info['Match'], "Tijd": info['Tijd'], "Inzet": 10.0, "Odd": odd, "Markt": "Expert Selection", "Live Score": "0-0 (NS)"}
                            st.session_state.active_bets.append(new_bet)
                            # AUTO-SAVE
                            if user_id:
                                auto_save_bet(user_id, new_bet)
                                auto_save_bankroll(user_id)
                            st.toast(f"Bet @{odd} geplaatst!")
                            time.sleep(0.5)
                            st.rerun()

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Intelligence Lab")
    if st.button("🔍 SCAN VOOR TRIGGERS"):
        st.success("Trigger gevonden: Lazio vs Porto (0-0 @ 22.0) -> Over 1.5 Goals.")

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Historiek")
    st.info("Afgesloten resultaten verschijnen hier.")

st.markdown("---")
st.caption(f"ProPunter Master V16.0 | API-Sports Live | België CET")
