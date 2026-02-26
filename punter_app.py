import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Deep Analyzer", page_icon="🧪", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- BESCHIKBARE COMPETITIES ---
AVAILABLE_LEAGUES = {
    "Europa League 🇪🇺": 3,
    "Conference League 🇪🇺": 848,
    "Jupiler Pro League 🇧🇪": 144,
    "Eredivisie 🇳🇱": 88,
    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿": 39,
    "La Liga 🇪🇸": 140,
    "Serie A 🇮🇹": 135,
    "Bundesliga 🇩🇪": 78
}

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .analysis-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 6px solid #f1e05a; }
    .safe-pick { background: #23863622; color: #3fb950; padding: 15px; border-radius: 8px; border: 1px solid #238636; font-weight: bold; font-size: 1.1rem; }
    .logic-box { font-size: 0.85rem; color: #8b949e; background: #0d1117; padding: 10px; border-radius: 6px; margin-top: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- DB INIT ---
if not firebase_admin._apps and "firebase" in st.secrets:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)
db = firestore.client() if firebase_admin._apps else None

# --- APP ---
t1, t2, t3 = st.tabs(["🚀 DASHBOARD", "📊 DEEP ANALYSIS", "🏟️ STADIUM"])

with t2:
    st.header("📊 Deep Match Analyzer")
    
    with st.expander("🛠️ Filter Instellingen", expanded=True):
        c1, c2 = st.columns(2)
        selected_league_names = c1.multiselect("Kies Competities:", list(AVAILABLE_LEAGUES.keys()), default=["Europa League 🇪🇺", "Conference League 🇪🇺"])
        selected_ids = [AVAILABLE_LEAGUES[name] for name in selected_league_names]
        
        selected_bm = c2.selectbox("Bookmaker voor Odds:", ["Bet365", "Bwin", "Unibet", "Pinnacle"])
        bm_id = {"Bet365": 2, "Bwin": 6, "Unibet": 8, "Pinnacle": 4}[selected_bm]

    if st.button("🔍 START DIEPE ANALYSE", use_container_width=True):
        with st.spinner("Statistieken en Odds aan het berekenen..."):
            res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'date': '2026-02-26'})
            all_fix = res.json().get('response', [])
            
            # Filter op geselecteerde competities
            target_fix = [f for f in all_fix if f['league']['id'] in selected_ids]
            
            st.session_state.deep_cache = []
            for f in target_fix[:15]:
                f_id = f['fixture']['id']
                
                # 1. Haal Odds
                o_res = requests.get(f"{BASE_URL}/odds", headers=headers, params={'fixture': f_id, 'bookmaker': bm_id})
                o_data = o_res.json().get('response', [])
                
                # 2. Haal H2H & Vorm
                h2h_res = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=headers, params={'h2h': f"{f['teams']['home']['id']}-{f['teams']['away']['id']}"})
                h2h = h2h_res.json().get('response', [])[:3]

                # 3. DEEP LOGIC ENGINE
                # Analyseer gemiddelde goals en resultaten
                total_goals = sum([(m['goals']['home'] + m['goals']['away']) for m in h2h if m['goals']['home'] is not None])
                avg_goals = total_goals / len(h2h) if h2h else 0
                
                # Bepaal veiligste bet
                suggestion = "Draw No Bet: Home"
                suggested_odd = 0.0
                logic_reason = "Op basis van algemene vorm."
                
                if o_data:
                    bets = o_data[0]['bookmakers'][0]['bets']
                    # Zoek naar Win Odds
                    win_odd = next((v['odd'] for b in bets if b['name'] == "Match Winner" for v in b['values'] if v['value'] == 'Home'), 1.50)
                    
                    if avg_goals > 2.5:
                        suggestion = "Over 1.5 Goals"
                        logic_reason = f"H2H historiek toont gemiddeld {avg_goals:.1f} goals per match."
                        suggested_odd = next((v['odd'] for b in bets if b['name'] == "Goals Over/Under" for v in b['values'] if v['value'] == 'Over 1.5'), 1.25)
                    elif win_odd < 1.80:
                        suggestion = f"Win of Gelijk: {f['teams']['home']['name']}"
                        logic_reason = f"{f['teams']['home']['name']} is statistisch favoriet met een odd van {win_odd}."
                        suggested_odd = next((v['odd'] for b in bets if b['name'] == "Double Chance" for v in b['values'] if v['value'] == 'Home/Draw'), 1.30)
                
                st.session_state.deep_cache.append({
                    'f': f, 'h2h': h2h, 'suggestion': suggestion, 'odd': suggested_odd, 'reason': logic_reason
                })

    # --- WEERGAVE ---
    if 'deep_cache' in st.session_state:
        for item in st.session_state.deep_cache:
            f = item['f']
            st.markdown(f'<div class="analysis-card">', unsafe_allow_html=True)
            st.markdown(f"### 🏟️ {f['league']['name']}: {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            
            c1, c2 = st.columns([2, 1])
            with c1:
                if item['h2h']:
                    st.write("**H2H Historie:**")
                    for h in item['h2h']:
                        st.write(f"◽ {h['teams']['home']['name']} {h['goals']['home']}-{h['goals']['away']} {h['teams']['away']['name']}")
                
                st.markdown(f'<div class="safe-pick">🛡️ SAFE BET: {item["suggestion"]} (@{item["odd"]})</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="logic-box"><b>Logica:</b> {item["reason"]}</div>', unsafe_allow_html=True)
            
            with c2:
                st.write(f"🕒 Aftrap: {datetime.fromtimestamp(f['fixture']['timestamp'], TIMEZONE).strftime('%H:%M')}")
                if st.button(f"Bevestig @{item['odd']}", key=f"deep_btn_{f['fixture']['id']}", use_container_width=True):
                    if db:
                        db.collection("saved_slips").add({
                            "user_id": "punter_01", "timestamp": datetime.now(TIMEZONE),
                            "total_odd": item['odd'], "matches": [{"match": f"{f['teams']['home']['name']} vs {f['teams']['away']['name']}", "market": item['suggestion'], "odd": item['odd']}],
                            "stake": 10.0
                        })
                        st.toast("Bet toegevoegd aan tracker!")
            st.markdown('</div>', unsafe_allow_html=True)

with t3:
    components.html(f'<div id="wg-api-football-livescore" data-host="v3.football.api-sports.io" data-key="{API_KEY}" data-refresh="60" data-theme="dark" class="api_football_loader"></div><script type="module" src="https://widgets.api-sports.io/football/1.1.8/widget.js"></script>', height=1000)
