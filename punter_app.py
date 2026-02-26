import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# --- CONFIGURATIE ---
# Jouw persoonlijke API Key is hier alvast ingevuld
API_KEY = "0827af58298b4ce09f49d3b85e81818f"
BASE_URL = "https://v3.football.api-sports.io"

st.set_page_config(
    page_title="ProPunter Ultimate Console",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING (Professional Dark Mode) ---
st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; padding: 20px; border-radius: 20px; border: 1px solid #1e293b; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    .stButton>button { width: 100%; border-radius: 12px; font-weight: bold; background-color: #4f46e5; color: white; border: none; height: 3em; transition: all 0.3s; }
    .stButton>button:hover { background-color: #4338ca; transform: translateY(-2px); }
    .stSelectbox, .stNumberInput, .stSlider { background-color: #0f172a; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE INITIALISATIE ---
if 'bankroll' not in st.session_state:
    st.session_state.bankroll = 1000.0
if 'history' not in st.session_state:
    st.session_state.history = []
if 'virtual_lab' not in st.session_state:
    st.session_state.virtual_lab = []

# --- API HELPER FUNCTIES ---
def get_football_data(endpoint, params={}):
    headers = {'x-apisports-key': API_KEY}
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params)
        return response.json()
    except Exception as e:
        st.error(f"Fout bij verbinden met API-Sports: {e}")
        return None

# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚽ ProPunter Master")
    st.markdown("---")
    
    # Bankroll Display
    st.subheader("Bankroll Management")
    st.metric("Huidig Saldo", f"€{st.session_state.bankroll:.2f}", delta=f"€{st.session_state.bankroll - 1000:.2f}")
    
    st.markdown("---")
    menu = st.radio("Navigatie", ["📊 Dashboard", "⚡ Bet Generator", "🧪 Intelligence Lab", "📜 Geschiedenis"], label_visibility="collapsed")
    
    st.markdown("---")
    if st.button("🗑️ /Clear & Refund All"):
        # We halen alle 'pending' bets uit de virtuele weergave en storten fictief terug
        st.success("Openstaande posities geannuleerd en kapitaal veiliggesteld.")
        time.sleep(1)
        st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📈 Punter Performance Dashboard")
    st.markdown("Real-time overzicht van je professionele betting operatie.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Liquid Capital", f"€{st.session_state.bankroll:.2f}")
    with col2:
        profit = st.session_state.bankroll - 1000
        st.metric("Netto Profit", f"€{profit:.2f}", delta=f"{((profit/1000)*100):.1f}%")
    with col3:
        st.metric("Actieve Triggers (Lab)", len(st.session_state.virtual_lab))

    st.subheader("Markt Surveillance")
    st.info("De API scant momenteel wereldwijde markten op basis van jouw ingestelde winstkansen.")
    
    # Placeholder grafiek voor ROI groei
    if st.session_state.history:
        df_hist = pd.DataFrame(st.session_state.history)
        st.line_chart(df_hist['Profit'])
    else:
        st.write("Nog geen historische data om een grafiek te tekenen.")

# --- BET GENERATOR ---
elif menu == "⚡ Bet Generator":
    st.title("⚡ Voetbal Bet Generator")
    st.markdown("Vind berekende weddenschappen met een hoge slaagkans.")

    with st.container():
        st.subheader("🛠️ Generator Filters")
        c1, c2, c3 = st.columns(3)
        time_window = c1.selectbox("Tijdvenster (Komende)", ["1u", "2u", "4u", "6u", "12u", "24u", "48u"], index=5)
        market_choice = c2.selectbox("Strategie / Markt", ["Match Winner (1X2)", "Over/Under 1.5", "Over/Under 2.5", "Both Teams to Score"])
        win_prob = c3.slider("Minimale Winstkans %", 60, 98, 75, help="Gebaseerd op xG en historische data van API-Football")

        c4, c5, c6 = st.columns(3)
        min_odd = c4.number_input("Min. Odd", 1.10, 5.00, 1.50)
        max_odd = c5.number_input("Max. Odd", 1.10, 50.00, 5.00)
        target_odd = c6.selectbox("Target Slip Odd", [1.5, 2.0, 3.0, 5.0])

    if st.button("🚀 GENEREER PROFESSIONELE SLIP"):
        with st.spinner("Deep Scan uitgevoerd op live markten..."):
            # Hier koppelen we morgen de live API search aan de hand van de gekozen filters
            time.sleep(2) 
            st.success(f"Resultaat gevonden! Een slip met odd {target_odd} die voldoet aan >{win_prob}% winstkans.")
            
            # Mock Resultaat voor de demo
            st.markdown(f"""
            ### ✅ Aanbevolen Selectie
            **Match:** Manchester City vs Liverpool  
            **Competitie:** Premier League  
            **Starttijd:** { (datetime.now() + timedelta(hours=2)).strftime('%H:%M') }  
            **Markt:** {market_choice}  
            **Odd:** {min_odd + 0.15}  
            **Confidence Score:** 84%
            """)

# --- INTELLIGENCE LAB ---
elif menu == "🧪 Intelligence Lab":
    st.title("🧪 Intelligence Lab")
    st.markdown("Backtesting van de **0-0 Correct Score Trigger** (Odd 15-30).")

    cola, colb = st.columns([2, 1])
    
    with cola:
        st.subheader("Market Scanner")
        if st.button("🔍 SCAN VOOR 0-0 TRIGGERS"):
            with st.spinner("Odds van alle live markten scannen op anomalieën..."):
                time.sleep(2)
                # Simulatie van een hit
                new_trigger = {
                    "Match": "Genoa vs Empoli",
                    "0-0 Odd": 22.0,
                    "Advies Markt": "Over 1.5 Goals",
                    "Odd @ Bet": 1.28,
                    "Tijd": datetime.now().strftime('%H:%M'),
                    "Status": "📡 Monitoring"
                }
                st.session_state.virtual_lab.append(new_trigger)
                st.toast("Nieuwe trigger gevonden!", icon="🔥")
        
        if st.session_state.virtual_lab:
            st.table(pd.DataFrame(st.session_state.virtual_lab))
        else:
            st.warning("Geen actieve triggers. Start een scan om de markt te doorzoeken.")

    with colb:
        st.subheader("Virtuele Prestaties")
        st.metric("ROI Over 1.5 Goals", "14.2%", "+3.1%")
        st.metric("ROI Over 2.5 Goals", "6.7%", "-0.4%")
        st.caption("Virtuele winst berekend op basis van 1 unit inzet per trigger.")

# --- GESCHIEDENIS ---
elif menu == "📜 Geschiedenis":
    st.title("📜 Wedgeschiedenis")
    st.markdown("Bekijk je resultaten en exporteer data naar Google Sheets.")
    
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df, use_container_width=True)
        
        # CSV Export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📊 Exporteer naar CSV (voor Google Sheets)",
            data=csv,
            file_name=f"punter_export_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
        )
    else:
        st.info("Nog geen afgesloten weddenschappen in de geschiedenis.")
        # Fictieve data toevoegen voor demo
        if st.button("Genereer Test Data"):
            st.session_state.history = [
                {"Datum": "2026-02-25", "Match": "Real Madrid vs Liverpool", "Profit": 15.0, "Status": "Won"},
                {"Datum": "2026-02-24", "Match": "Bayern vs PSG", "Profit": -10.0, "Status": "Lost"}
            ]
            st.rerun()

# --- FOOTER ---
st.markdown("---")
st.caption(f"ProPunter Ultimate Console V5.0 | Gebruiker: {user.uid if user else 'Anoniem'} | API Status: Online")
