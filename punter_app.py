import streamlit as st

# Probeer de imports één voor één om te zien waar het stopt
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_LIB = True
except ImportError:
    HAS_LIB = False

# Sidebar status
st.sidebar.title("🛠️ Systeem Check")
if not HAS_LIB:
    st.sidebar.error("❌ Bibliotheken nog niet geladen. Wacht op installatie...")
    st.stop() # Stop de rest van de app tot de installatie klaar is

# --- DATABASE CONNECTIE ---
if "firebase" in st.secrets:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.sidebar.success("🚀 Cloud Verbonden!")
    except Exception as e:
        st.sidebar.error(f"⚠️ Connectie fout: {e}")
else:
    st.sidebar.warning("⚠️ Geen [firebase] secrets gevonden.")

# De rest van je ProPunter code hieronder...
st.title("⚽ ProPunter Master V18")
