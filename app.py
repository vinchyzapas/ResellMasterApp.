import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# ==========================================
# 🔗 CONFIGURACIÓN
# ==========================================
LINK_APP = "https://vinchy-zapas.streamlit.app"
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2589/2589903.png"

st.set_page_config(page_title="Vinchy Zapas V65", layout="wide", page_icon="👟")

# ==========================================
# 🎨 ESTILO
# ==========================================
st.markdown("""
<style>
.stApp {background-color: #FFFFFF;}
section[data-testid="stSidebar"] {background-color: #111111;}
section[data-testid="stSidebar"] * {color: white !important;}
.stTextInput input, .stNumberInput input {background-color: #F0F2F6;}
div.stButton > button {
    background-color: #D32F2F; color: white; font-weight: bold;
    width: 100%; padding: 12px; font-size: 16px;
}
.version-text {font-size: 24px; font-weight: bold; color: #D32F2F; text-align: center;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# LISTAS BASE
# ==========================================
BASES_MARCAS = ["Adidas","Nike","Hoka","Salomon","Asics","New Balance","Merrell"]
BASES_TIENDAS = ["Asos","Amazon","Zalando","Footlocker","Vinted","Privalia"]

# ==========================================
# LOGIN
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'seccion_actual' not in st.session_state:
    st.session_state.seccion_actual = "Inicio"

if not st.session_state.autenticado:
    st.title("🔒 Acceso Vinchy Zapas")
    st.markdown('<p class="version-text">VERSIÓN 65</p>', unsafe_allow_html=True)
    st.image(LOGO_URL, width=80)
    pin = st.text_input("PIN", type="password")
    if st.button("ENTRAR"):
        if pin == "1234":
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("PIN incorrecto")
    st.stop()

# ==========================================
# GOOGLE SHEETS
# ==========================================
def obtener_libro_google():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["gcp_service_account"]), scope
    )
    client = gspread.authorize(creds)
    return client.open("inventario_zapatillas")

# ==========================================
# UTILIDADES
# ==========================================
def leer_numero_literal(valor):
    if pd.isna(valor) or str(valor).strip() == "":
        return 0.0
    try:
        txt = str(valor).replace("€","").replace(",",".").strip()
        return float(txt)
    except:
        return 0.0

def arreglar_talla(valor):
    v = str(valor).replace(",",".").replace(".0","").strip()
    if len(v)==3 and v.endswith("5") and "." not in v:
        return f"{v[:2]}.{v[2]}"
    return v if v!="nan" else ""

# ==========================================
# CARGA / GUARDADO
# ==========================================
@st.cache_data(ttl=5)
def cargar_datos():
    libro = obtener_libro_google()
    sheet = libro.sheet1
    df = pd.DataFrame(sheet.get_all_records())

    for c in ["Precio Compra","Precio Venta","Ganancia Neta"]:
        df[c] = df[c].apply(leer_numero_literal)

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
    df["Talla"] = df["Talla"].apply(arreglar_talla)
    df["Fecha Compra"] = pd.to_datetime(df["Fecha Compra"], dayfirst=True, errors="coerce")
    df["Fecha Venta"] = pd.to_datetime(df["Fecha Venta"], dayfirst=True, errors="coerce")

    df["🌐 Web"] = "https://www.google.com/search?q=" + df["Marca"] + "+" + df["Modelo"]
    return df

def guardar_datos(df):
    libro = obtener_libro_google()
    sheet = libro.sheet1
    out = df.drop(columns=["🌐 Web"], errors="ignore").copy()

    for c in ["Precio Compra","Precio Venta","Ganancia Neta"]:
        out[c] = out[c].astype(float)

    out["Fecha Compra"] = out["Fecha Compra"].dt.strftime("%d/%m/%Y")
    out["Fecha Venta"] = out["Fecha Venta"].dt.strftime("%d/%m/%Y")

    out = out.fillna("")
    sheet.clear()
    sheet.update([out.columns.tolist()] + out.values.tolist())
    st.cache_data.clear()

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.image(LOGO_URL, width=100)
if st.sidebar.button("🏠 Inicio"):
    st.session_state.seccion_actual="Inicio"; st.rerun()
if st.sidebar.button("📋 Historial"):
    st.session_state.seccion_actual="Historial"; st.rerun()
if st.sidebar.button("🔒 Salir"):
    st.session_state.autenticado=False; st.rerun()

df = cargar_datos()

# ==========================================
# INICIO
# ==========================================
if st.session_state.seccion_actual=="Inicio":
    st.title("👟 Panel de Control")
    st.metric("Stock", len(df[df["Estado"]=="En Stock"]))
    st.metric("Ganancia Total", f"{df[df['Estado']=='Vendido']['Ganancia Neta'].sum():.2f} €")

# ==========================================
# HISTORIAL (FIX DEFINITIVO)
# ==========================================
elif st.session_state.seccion_actual=="Historial":
    st.title("📋 Historial")
    st.info("✍️ Escribe precios con coma o punto (65,5 o 65.5)")

    col_cfg = {
        "ID": st.column_config.NumberColumn(disabled=True),
        "🌐 Web": st.column_config.LinkColumn("Buscar"),
        "Precio Compra": st.column_config.TextColumn(),
        "Precio Venta": st.column_config.TextColumn(),
        "Ganancia Neta": st.column_config.NumberColumn(disabled=True),
        "Fecha Compra": st.column_config.DateColumn("DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn("DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock","Vendido"])
    }

    df_ed = st.data_editor(
        df,
        column_config=col_cfg,
        hide_index=True,
        use_container_width=True
    )

    if not df.equals(df_ed):
        df_ed["Precio Compra"] = df_ed["Precio Compra"].apply(leer_numero_literal)
        df_ed["Precio Venta"] = df_ed["Precio Venta"].apply(leer_numero_literal)
        df_ed["Ganancia Neta"] = df_ed["Precio Venta"] - df_ed["Precio Compra"]
        df_ed["Talla"] = df_ed["Talla"].apply(arreglar_talla)

        guardar_datos(df_ed)
        st.success("✅ Cambios guardados")
