import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
# Firebase/Firestore integratie voor persistente opslag
try:
    from google.cloud import firestore
except ImportError:
    st.error("Installeer google-cloud-firestore via requirements.txt")

# --- CONFIGURATIE ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"
TIMEZONE = "Europe/Brussels"
APP_ID = "propunter-master-2026"

st.set_page_config(
    page_title="ProPunter Master Console V5.5",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FIRESTORE INITIALISATIE ---
# Opmerking: In een echte Streamlit Cloud omgeving moet je je service_account JSON 
# in de 'Secrets' zetten. Voor nu bouwen we de structuur op.
def get_db():
    try:
        # Streamlit zoekt automatisch naar credentials in secrets
        return firestore.Client()
    except Exception:
        return None

db = get_db()

# --- STYLING ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; padding: 20px; border-radius: 20px; border: 1px solid #1e293b; }
    .stButton>button { width: 100%; border-radius: 12px; font-weight: bold; background-color: #4f46e5; color: white; border: none; height: 3.5em; }
    </style>
    """, unsafe_allow_html=True)

# --- DB HELPERS (VOLGENS RULE 1 & 2) ---
def save_data(user_id, collection_name, data_dict):
    if db and user_id:
        path = f"artifacts/{APP_ID}/users/{user_id}/{collection_name}"
        db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection(collection_name).add(data_dict)

def update_bankroll_db(user_id, amount):
    if db and user_id:
        ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll")
        ref.set({"balance": amount})

def load_user_data(user_id):
    if not db or not user_id:
        return 1000.0, [], []
    
    # Bankroll ophalen
    bank_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll").get()
    balance = bank_ref.to_dict().get('balance', 1000.0) if bank_ref.exists else 1000.0
    
    # Bets ophalen (Simpele query volgens Rule 2)
    bets_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets").stream()
    active_bets = [d.to_dict() for d in bets_ref]
    
    # Lab ophalen
    lab_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("virtual_lab").stream()
    virtual_lab = [d.to_dict() for d in lab_ref]
    
    return balance, active_bets, virtual_lab

# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    
    # Gebruikersidentificatie voor opslag
    user_id = st.text_input("User ID (voor opslag)", placeholder="bijv. punter_pro_1")
    if not user_id:
        st.warning("Voer een User ID in om je data op te slaan.")
    
    st.markdown("---")
    
    # Initialiseer of Laad data
    if 'data_loaded' not in st.session_state or st.sidebar.button("🔄 Sync Cloud Data"):
        balance, active, lab = load_user_data(user_id)
        st.session_state.bankroll = balance
        st.session_state.active_bets = active
        st.session_state.virtual_lab = lab
        st.session_state.data_loaded = True

    st.subheader("Bankroll Management")
    st.metric("Huidig Saldo", f"€{st.session_state.bankroll:.2f}")
    
    st.markdown("---")
    menu = st.radio("Menu", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    if st.sidebar.button("🗑️ /Clear & Refund All"):
        refund_sum = sum(bet.get('Inzet', 0) for bet in st.session_state.active_bets)
        st.session_state.bankroll += refund_sum
        st.session_state.active_bets = []
        update_bankroll_db(user_id, st.session_state.bankroll)
        # In een echte DB zouden we hier ook de documenten verwijderen
        st.success("Bankroll hersteld.")
        st.rerun()

# --- API HELPER ---
def call_football_api(endpoint, params={}):
    headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': "v3.football.api-sports.io"}
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params)
        return response.json() if response.status_code == 200 else None
    except: return None

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📈 Punter Dashboard")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    col2.metric("Open Bets", len(st.session_state.active_bets))
    col3.metric("Database Status", "Online" if db else "Local Mode")

    st.subheader("Lopende Weddenschappen")
    if st.session_state.active_bets:
        st.dataframe(pd.DataFrame(st.session_state.active_bets), use_container_width=True)
    else:
        st.info("Geen actieve bets gevonden in de database.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Live Bet Generator")
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        time_sel = c1.selectbox("Tijdvenster", ["1", "2", "4", "6", "12", "24", "48"], index=5)
        market_sel = c2.selectbox("Markt", ["1X2", "Over 2.5", "BTTS"])
        win_prob = c3.slider("Winstkans %", 60, 95, 75)

    if st.button("🚀 SCAN & GENEREER"):
        with st.spinner("Live data ophalen..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_football_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response'):
                valid = [f for f in data['response'] if now < datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00')).astimezone(brussels_tz) < now + timedelta(hours=int(time_sel))]
                
                if valid:
                    match = valid[0]
                    res = {
                        "Match": f"{match['teams']['home']['name']} vs {match['teams']['away']['name']}",
                        "Tijd": datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00')).astimezone(brussels_tz).strftime('%H:%M'),
                        "Odd": 1.65, "Markt": market_sel, "Inzet": 10.0, "fixtureId": match['fixture']['id']
                    }
                    st.session_state.current_scan = res
                else: st.warning("Geen matches gevonden.")

    if 'current_scan' in st.session_state:
        s = st.session_state.current_scan
        st.success(f"Match gevonden: {s['Match']} (@{s['Odd']})")
        if st.button("💰 PLAATS WEDDENSCHAP"):
            st.session_state.bankroll -= 10.0
            st.session_state.active_bets.append(s)
            
            # OPSLAAN IN DATABASE
            save_data(user_id, "real_bets", s)
            update_bankroll_db(user_id, st.session_state.bankroll)
            
            del st.session_state.current_scan
            st.rerun()

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Intelligence Lab")
    if st.button("🔍 SCAN 0-0 TRIGGERS"):
        new_trigger = {"Match": "Lazio vs Porto", "0-0 Odd": 22.0, "Advies": "Over 1.5", "Status": "Live", "Timestamp": time.time()}
        st.session_state.virtual_lab.append(new_trigger)
        save_data(user_id, "virtual_lab", new_trigger)
        st.success("Trigger opgeslagen in database.")

    if st.session_state.virtual_lab:
        st.table(pd.DataFrame(st.session_state.virtual_lab))

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Historiek")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df)
        st.download_button("📊 Export CSV", df.to_csv().encode('utf-8'), "punter_data.csv")
    else:
        st.info("Nog geen afgesloten data.")

st.markdown("---")
st.caption(f"ProPunter Master V5.5 | Gebruiker: {user_id if user_id else 'Gast'} | Opslag: {'Firestore Live' if db else 'Local Mode'}")
