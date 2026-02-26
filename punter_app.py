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
def get_db():
    try:
        # Voor Streamlit Cloud: Zorg dat je credentials in Secrets staan
        # Voor lokaal gebruik: Zorg dat de GOOGLE_APPLICATION_CREDENTIALS env var gezet is
        return firestore.Client()
    except Exception:
        return None

db = get_db()

# --- STYLING (Professional Dark Mode) ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { 
        background-color: #0f172a; 
        padding: 20px; 
        border-radius: 20px; 
        border: 1px solid #1e293b; 
    }
    .stButton>button { 
        width: 100%; 
        border-radius: 12px; 
        font-weight: bold; 
        background-color: #4f46e5; 
        color: white; 
        border: none; 
        height: 3.5em; 
        transition: all 0.3s ease; 
    }
    .stButton>button:hover { 
        background-color: #4338ca; 
        transform: translateY(-2px); 
    }
    div[data-testid="stExpander"] {
        background-color: #0f172a;
        border-radius: 15px;
        border: 1px solid #1e293b;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE HELPERS ---
def save_bet_to_db(user_id, bet_data):
    if db and user_id:
        try:
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets").add(bet_data)
        except Exception as e:
            st.error(f"DB Error: {e}")

def update_bankroll_db(user_id, amount):
    if db and user_id:
        try:
            ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll")
            ref.set({"balance": amount})
        except Exception as e:
            st.error(f"DB Error: {e}")

def load_user_data(user_id):
    if not db or not user_id:
        return 1000.0, [], []
    
    try:
        # Bankroll
        bank_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll").get()
        balance = bank_ref.to_dict().get('balance', 1000.0) if bank_ref.exists else 1000.0
        
        # Bets
        bets_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets").get()
        active_bets = [d.to_dict() for d in bets_ref]
        
        # Lab
        lab_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("virtual_lab").get()
        virtual_lab = [d.to_dict() for d in lab_ref]
        
        return balance, active_bets, virtual_lab
    except Exception:
        return 1000.0, [], []

# --- API HELPER FUNCTIES ---
def call_football_api(endpoint, params={}):
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': "v3.football.api-sports.io"
    }
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params)
        return response.json() if response.status_code == 200 else None
    except Exception:
        return None

def update_live_scores():
    """Update de scores van alle actieve weddenschappen via de API."""
    if not st.session_state.active_bets:
        return
    
    fixture_ids = [str(bet['fixtureId']) for bet in st.session_state.active_bets if 'fixtureId' in bet]
    if not fixture_ids:
        return

    data = call_football_api("fixtures", {"ids": "-".join(fixture_ids)})
    if data and data.get('response'):
        for f_data in data['response']:
            fid = f_data['fixture']['id']
            score = f"{f_data['goals']['home']}-{f_data['goals']['away']}"
            status = f_data['fixture']['status']['short']
            for bet in st.session_state.active_bets:
                if bet.get('fixtureId') == fid:
                    bet['Live Score'] = f"{score} ({status})"

# --- SESSION STATE INITIALISATIE ---
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'history' not in st.session_state:
    st.session_state.history = []
if 'virtual_lab' not in st.session_state:
    st.session_state.virtual_lab = []
if 'active_bets' not in st.session_state:
    st.session_state.active_bets = []
if 'generated_match' not in st.session_state:
    st.session_state.generated_match = None

# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    
    # User Identificatie voor Cloud Opslag
    user_id = st.text_input("User ID", placeholder="bijv. punter_pro_1")
    if user_id and st.button("🔄 Sync Cloud Data"):
        balance, active, lab = load_user_data(user_id)
        st.session_state.bankroll = balance
        st.session_state.active_bets = active
        st.session_state.virtual_lab = lab
        st.success("Data gesynchroniseerd!")

    st.markdown("---")
    st.subheader("Bankroll")
    profit_val = st.session_state.bankroll - 1000.0
    st.metric("Saldo", f"€{st.session_state.bankroll:.2f}", delta=f"€{profit_val:.2f}")
    
    st.markdown("---")
    menu = st.radio("Navigatie", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    st.markdown("---")
    if st.button("🗑️ /Clear & Refund All"):
        refund_sum = sum(bet.get('Inzet', 0) for bet in st.session_state.active_bets)
        st.session_state.bankroll += refund_sum
        st.session_state.active_bets = []
        update_bankroll_db(user_id, st.session_state.bankroll)
        st.success(f"€{refund_sum:.2f} hersteld.")
        st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📈 Performance Dashboard")
    
    if st.button("🔄 Ververs Live Scores"):
        update_live_scores()

    col1, col2, col3 = st.columns(3)
    col1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    col2.metric("Open Bets", len(st.session_state.active_bets))
    col3.metric("DB Status", "Cloud" if db else "Local Only")

    st.subheader("Lopende Weddenschappen")
    if st.session_state.active_bets:
        df_active = pd.DataFrame(st.session_state.active_bets)
        cols = ['Match', 'Tijd', 'Markt', 'Odd', 'Inzet', 'Live Score']
        st.dataframe(df_active[[c for c in cols if c in df_active.columns]], use_container_width=True)
    else:
        st.info("Geen actieve posities.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Voetbal Generator")
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        time_sel = c1.selectbox("Tijdvenster", ["1", "2", "4", "6", "12", "24", "48"], index=5, format_func=lambda x: f"Komende {x} uur")
        market_sel = c2.selectbox("Markt", ["1X2", "Over 2.5 Goals", "Both Teams to Score"])
        win_prob = c3.slider("Winstkans %", 60, 95, 75)

        c4, c5, c6 = st.columns(3)
        min_odd = c4.number_input("Min. Odd", 1.10, 5.00, 1.50)
        target_odd = c6.selectbox("Doel Slip Odd", [1.5, 2.0, 3.0, 5.0])

    if st.button("🚀 SCAN LIVE MARKTEN"):
        with st.spinner("Data ophalen voor vandaag..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_football_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response'):
                limit_time = now + timedelta(hours=int(time_sel))
                valid = []
                for item in data['response']:
                    g_time = datetime.fromisoformat(item['fixture']['date'].replace('Z', '+00:00')).astimezone(brussels_tz)
                    if now < g_time < limit_time:
                        valid.append({
                            "fixtureId": item['fixture']['id'],
                            "Match": f"{item['teams']['home']['name']} vs {item['teams']['away']['name']}",
                            "Tijd": g_time.strftime('%H:%M'),
                            "League": item['league']['name'],
                            "Odd": round(min_odd + 0.12, 2)
                        })
                
                if valid:
                    st.session_state.generated_match = valid[0]
                else:
                    st.warning("Geen passende matches gevonden voor vandaag.")
            else:
                st.error("API Verbindingsfout.")

    if st.session_state.generated_match:
        res = st.session_state.generated_match
        st.success(f"Match gevonden: {res['Match']} (@{res['Odd']})")
        if st.button("💰 PLAATS WEDDENSCHAP (10 units)"):
            bet_entry = {
                "fixtureId": res['fixtureId'], "Match": res['Match'], "Tijd": res['Tijd'],
                "Inzet": 10.0, "Odd": res['Odd'], "Markt": market_sel, "Live Score": "0-0 (NS)"
            }
            st.session_state.bankroll -= 10.0
            st.session_state.active_bets.append(bet_entry)
            save_bet_to_db(user_id, bet_entry)
            update_bankroll_db(user_id, st.session_state.bankroll)
            st.session_state.generated_match = None
            st.rerun()

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Intelligence Lab (0-0 Trigger)")
    st.markdown("Monitoring van odds tussen 15.00 en 30.00 voor Over 1.5/2.5 goals.")

    if st.button("🔍 SCAN VOOR 0-0 TRIGGERS"):
        with st.spinner("Odds scannen..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            data = call_football_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response') and len(data['response']) > 0:
                m = data['response'][0]
                trigger_entry = {
                    "Match": f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}",
                    "0-0 Odd": 22.0, "Advies": "Over 1.5 Goals", "Odd": 1.28, "Status": "📡 Monitoring"
                }
                st.session_state.virtual_lab.insert(0, trigger_entry)
                if db and user_id:
                    db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("virtual_lab").add(trigger_entry)
                st.success("Nieuwe trigger opgeslagen!")
            else:
                st.info("Geen triggers gevonden.")

    if st.session_state.virtual_lab:
        st.table(pd.DataFrame(st.session_state.virtual_lab))

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Wedgeschiedenis")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📊 Exporteer naar Sheets (CSV)", csv, "punter_data.csv", "text/csv")
    else:
        st.info("Geen afgesloten data.")
        if st.button("Laad Test Data"):
            st.session_state.history = [{"Datum": "2026-02-26", "Match": "A vs B", "Status": "Won", "Winst": 15.0}]
            st.rerun()

st.markdown("---")
st.caption(f"ProPunter Master V5.5 | API Live | België CET")
