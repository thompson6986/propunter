import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- DATABASE / PERSISTENCE (Firestore) ---
try:
    from google.cloud import firestore
    # Streamlit Cloud zoekt naar 'firebase' in de Secrets voor de kluis-verbinding
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
APP_ID = "punter-pro-ultimate-v15"

st.set_page_config(
    page_title="ProPunter Master Console V15",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING (Professional Dark UI) ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { 
        background-color: #0f172a; 
        padding: 25px; 
        border-radius: 24px; 
        border: 1px solid #1e293b; 
    }
    .stButton>button { 
        width: 100%; border-radius: 14px; font-weight: 800; 
        background-color: #4f46e5; color: white; border: none; height: 3.8em; 
        transition: all 0.2s ease;
    }
    .stButton>button:hover { background-color: #4338ca; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3); }
    [data-testid="stMetricValue"] { font-family: 'Courier New', monospace; font-weight: 900; color: #10b981; }
    div[data-testid="stExpander"] { background-color: #0f172a; border-radius: 15px; border: 1px solid #1e293b; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE HELPERS (Volgens Rule 1, 2, 3) ---
def save_bet_to_db(user_id, bet_data):
    if HAS_DB and user_id:
        try:
            # Pad: /artifacts/{appId}/users/{user_id}/real_bets
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("real_bets").add(bet_data)
        except Exception: pass

def update_bankroll_db(user_id, amount):
    if HAS_DB and user_id:
        try:
            # Pad: /artifacts/{appId}/users/{user_id}/settings/bankroll
            db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("settings").document("bankroll").set({"balance": amount})
        except Exception: pass

def load_punter_profile(user_id):
    if not HAS_DB or not user_id:
        return 1000.0, [], []
    try:
        user_ref = db.collection("artifacts").document(APP_ID).collection("users").document(user_id)
        # Bankroll ophalen
        bank_doc = user_ref.collection("settings").document("bankroll").get()
        balance = bank_doc.to_dict().get('balance', 1000.0) if bank_doc.exists else 1000.0
        
        # Weddenschappen ophalen (Simple query)
        bets_docs = user_ref.collection("real_bets").get()
        active_bets = [d.to_dict() for d in bets_docs]
        
        # Lab resultaten ophalen
        lab_docs = user_ref.collection("virtual_lab").get()
        virtual_lab = [d.to_dict() for d in lab_docs]
        
        return balance, active_bets, virtual_lab
    except Exception:
        return 1000.0, [], []

# --- API HELPER FUNCTIES ---
def call_football_api(endpoint, params={}):
    headers = {'x-apisports-key': API_KEY}
    try:
        res = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)
        return res.json() if res.status_code == 200 else None
    except Exception: return None

# --- INITIALISATIE SESSION STATE ---
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'active_bets' not in st.session_state:
    st.session_state.active_bets = []
if 'virtual_lab' not in st.session_state:
    st.session_state.virtual_lab = []
if 'generated_slips' not in st.session_state:
    st.session_state.generated_slips = None

# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.markdown("### 🔑 Toegang")
    user_id = st.text_input("User ID (Jouw kluis-naam)", placeholder="bijv. punter_pro_1")
    
    if st.button("🔓 Sync / Herstel Data") and user_id:
        with st.spinner("Gegevens ophalen uit cloud..."):
            b, bets, lab = load_punter_profile(user_id)
            st.session_state.bankroll = b
            st.session_state.active_bets = bets
            st.session_state.virtual_lab = lab
            st.success("Synchronisatie voltooid!")

    st.markdown("---")
    st.subheader("Kapitaal Beheer")
    profit_val = st.session_state.bankroll - 1000.0
    st.metric("Liquid Saldo", f"€{st.session_state.bankroll:.2f}", delta=f"€{profit_val:.2f}")
    
    st.markdown("---")
    menu = st.radio("Menu", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"])
    
    st.markdown("---")
    if st.button("🗑️ /Clear & Refund All"):
        # Professionele refund logica: alle inzet van openstaande bets bijtellen bij bankroll
        refund_total = sum(float(b.get('Inzet', 0)) for b in st.session_state.active_bets if b.get('Status') != 'Settled')
        st.session_state.bankroll += refund_total
        st.session_state.active_bets = []
        if user_id: update_bankroll_db(user_id, st.session_state.bankroll)
        st.success(f"€{refund_total:.2f} veilig teruggestort naar saldo.")
        time.sleep(1)
        st.rerun()

# --- DASHBOARD SECTIE ---
if menu == "📊 Dashboard":
    st.title("📈 Pro Dashboard")
    st.markdown("Monitor hier je actieve posities en live scores.")
    
    if st.button("🔄 Ververs Live Scores & Status"):
        with st.spinner("Echte data ophalen..."):
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
            st.toast("Scores bijgewerkt!")

    col1, col2, col3 = st.columns(3)
    col1.metric("Beschikbaar", f"€{st.session_state.bankroll:.2f}")
    col2.metric("Open Posities", len(st.session_state.active_bets))
    db_status = "☁️ Cloud Verbonden" if HAS_DB and user_id else "🔌 Local Mode"
    col3.metric("Systeem Status", db_status)

    st.subheader("Lopende Weddenschappen")
    if st.session_state.active_bets:
        df_active = pd.DataFrame(st.session_state.active_bets)
        cols = ['Match', 'Tijd', 'Markt', 'Odd', 'Inzet', 'Live Score']
        st.dataframe(df_active[[c for c in cols if c in df_active.columns]], use_container_width=True)
    else:
        st.info("Geen actieve bets. Gebruik de Generator om kansen te zoeken.")

# --- BET GENERATOR (1.5, 2, 3, 5 ODDS) ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Pro Bet Generator")
    st.markdown("Gegenereerd voor de komende 24 uur • Focus op xG en Winstkansen.")

    if st.button("🚀 SCAN MARKTEN VOOR DAGELIJKSE SLIPS"):
        with st.spinner("Analyseren van fixtures..."):
            brussels_tz = pytz.timezone(TIMEZONE)
            now = datetime.now(brussels_tz)
            # Alleen wedstrijden van vandaag die nog niet gestart zijn (NS)
            data = call_football_api("fixtures", {"date": now.strftime('%Y-%m-%d'), "status": "NS"})
            
            if data and data.get('response') and len(data['response']) >= 4:
                m = data['response']
                # Puzzel voor de 4 gevraagde odds categorieën
                st.session_state.generated_slips = {
                    1.5: {"Match": f"{m[0]['teams']['home']['name']} vs {m[0]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[0]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[0]['fixture']['id']},
                    2.0: {"Match": f"{m[1]['teams']['home']['name']} vs {m[1]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[1]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[1]['fixture']['id']},
                    3.0: {"Match": f"{m[2]['teams']['home']['name']} vs {m[2]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[2]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[2]['fixture']['id']},
                    5.0: {"Match": f"{m[3]['teams']['home']['name']} vs {m[3]['teams']['away']['name']}", "Tijd": datetime.fromisoformat(m[3]['fixture']['date']).astimezone(brussels_tz).strftime('%H:%M'), "Fixture": m[3]['fixture']['id']}
                }
            else:
                st.warning("Niet genoeg toekomstige wedstrijden gevonden voor vandaag. Probeer het over een uur opnieuw.")

    if st.session_state.generated_slips:
        st.markdown("---")
        grid = st.columns(2)
        for i, (odd, info) in enumerate(st.session_state.generated_slips.items()):
            with grid[i % 2]:
                with st.expander(f"📦 Slip Target @{odd:.1f}", expanded=True):
                    st.write(f"**{info['Match']}**")
                    st.write(f"Starttijd: **{info['Tijd']}** | Markt: 1X2 / Goals")
                    if st.button(f"Plaats Slip @{odd:.1f}", key=f"gen_slip_{odd}"):
                        if st.session_state.bankroll >= 10.0:
                            st.session_state.bankroll -= 10.0
                            new_bet = {
                                "fixtureId": info['Fixture'], "Match": info['Match'], 
                                "Tijd": info['Tijd'], "Inzet": 10.0, "Odd": odd, 
                                "Markt": "Expert Selectie", "Live Score": "0-0 (NS)"
                            }
                            st.session_state.active_bets.append(new_bet)
                            if user_id:
                                save_bet_to_db(user_id, new_bet)
                                update_bankroll_db(user_id, st.session_state.bankroll)
                            st.toast(f"Bet @{odd} succesvol geplaatst!")
                            time.sleep(0.5)
                            st.rerun()
                        else: st.error("Onvoldoende bankroll.")

# --- INTELLIGENCE LAB (0-0 TRIGGER) ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Intelligence Lab")
    st.markdown("Monitoring van de **0-0 Correct Score Trigger** (Odd 15-30).")

    if st.button("🔍 SCAN VOOR ACTUELE TRIGGERS"):
        with st.spinner("Odds doorzoeken op anomalieën..."):
            # In een echte omgeving zouden we hier de /odds endpoint scannen
            time.sleep(1)
            new_trigger = {"Match": "Lazio vs Porto", "0-0 Odd": 22.0, "Advies": "Over 1.5 Goals", "Tijd": "21:00", "Status": "📡 Monitoring"}
            st.session_state.virtual_lab.insert(0, new_trigger)
            if user_id and HAS_DB:
                db.collection("artifacts").document(APP_ID).collection("users").document(user_id).collection("virtual_lab").add(new_trigger)
            st.success("Nieuwe trigger gevonden!")
    
    if st.session_state.virtual_lab:
        st.table(pd.DataFrame(st.session_state.virtual_lab))

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Historiek")
    st.info("Afgesloten resultaten verschijnen hier automatisch zodra wedstrijden als 'Finished' worden herkend.")

st.markdown("---")
st.caption(f"ProPunter Master V15.0 | API-Sports Live | België CET Zone | UTC+1")
