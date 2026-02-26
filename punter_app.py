import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import time
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
st.set_page_config(page_title="Pro Punter Live Tracker", page_icon="⚽", layout="wide")
TIMEZONE = pytz.timezone("Europe/Brussels")

# --- DATABASE VERBINDING ---
if "firebase" in st.secrets and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client() if firebase_admin._apps else None

# --- API CONFIG ---
API_KEY = "0827af58298b4ce09f49d3b85e81818f" 
BASE_URL = "https://v3.football.api-sports.io"
headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- SETTLEMENT ENGINE ---
def check_win(market, value, home_g, away_g):
    """Berekent of een weddenschap gewonnen is op basis van de score."""
    try:
        total_g = home_g + away_g
        # Match Winner logica
        if "Winner" in market:
            if value == "Home" and home_g > away_g: return True
            if value == "Away" and away_g > home_g: return True
            if value == "Draw" and home_g == away_g: return True
        
        # Goals Over/Under logica
        if "Over" in value:
            threshold = float(value.split(" ")[-1])
            if total_g > threshold: return True
        if "Under" in value:
            threshold = float(value.split(" ")[-1])
            if total_g < threshold: return True
            
        # Double Chance logica
        if "Home/Draw" in value and home_g >= away_g: return True
        if "Away/Draw" in value and away_g >= home_g: return True
        if "Home/Away" in value and home_g != away_g: return True
        
        return False
    except: return False

# --- UI TABS ---
t1, t2 = st.tabs(["🚀 Parlay Generator", "📡 Mijn Portfolio & Live Tracker"])

# [Tab 1: Generator blijft ongewijzigd van V38/V39]

with t2:
    st.header("📡 Live Tracker")
    user_id = st.text_input("User ID", value="punter_01")
    
    if db:
        try:
            # Deze query veroorzaakt de index-melding
            saved = db.collection("saved_slips").where("user_id", "==", user_id).order_by("timestamp", direction="DESCENDING").limit(10).get()
            
            if not saved:
                st.info("Nog geen opgeslagen slips gevonden.")
            else:
                # 1. Verzamel alle fixture IDs
                f_ids = []
                docs_data = []
                for doc in saved:
                    d = doc.to_dict()
                    d['id'] = doc.id
                    docs_data.append(d)
                    for m in d['matches']:
                        f_ids.append(m['fixture_id'])
                
                # 2. Haal Live Data op
                live_updates = {}
                if f_ids:
                    res = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={'ids': "-".join(map(str, set(f_ids)))})
                    if res.status_code == 200:
                        for f in res.json().get('response', []):
                            live_updates[f['fixture']['id']] = f

                # 3. Toon de Slips
                for s in docs_data:
                    with st.expander(f"Slip @{s['total_odd']} | {s['timestamp'].strftime('%d/%m %H:%M')}"):
                        slip_won = True
                        for m in s['matches']:
                            f_id = m['fixture_id']
                            f_data = live_updates.get(f_id)
                            
                            col1, col2, col3 = st.columns([3, 2, 1])
                            with col1:
                                st.write(f"**{m['match']}**")
                                st.caption(f"{m['market']} (@{m['odd']})")
                            
                            if f_data:
                                h_g = f_data['goals']['home']
                                a_g = f_data['goals']['away']
                                status = f_data['fixture']['status']['short']
                                
                                with col2:
                                    if status in ['1H', '2H', 'HT']:
                                        st.markdown(f"🔴 **LIVE {f_data['fixture']['status']['elapsed']}'**")
                                        st.subheader(f"{h_g} - {a_g}")
                                    elif status == 'FT':
                                        st.write("🏁 Finished")
                                        st.subheader(f"{h_g} - {a_g}")
                                    else:
                                        st.write(f"🕒 Start: {m['time']}")

                                with col3:
                                    if status == 'FT':
                                        # Split markt en waarde voor de settlement check
                                        m_name = m['market'].split(":")[0]
                                        m_val = m['market'].split(":")[1].strip()
                                        if check_win(m_name, m_val, h_g, a_g):
                                            st.success("WON")
                                        else:
                                            st.error("LOST")
                                            slip_won = False
                                    else:
                                        st.write("⏳ Open")
                            else:
                                col2.write("Geen live data")

                        if st.button("🗑️ Verwijder Slip", key=f"del_{s['id']}"):
                            db.collection("saved_slips").document(s['id']).delete()
                            st.rerun()
        except Exception as e:
            st.warning("De database is bezig met het aanmaken van de index. Kom over 2 minuten terug.")
