import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# ==========================================
# 🔗 CONFIGURACIÓN
# ==========================================
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2589/2589903.png"

st.set_page_config(
    page_title="Vinchy Zapas",
    layout="wide",
    page_icon="👟"
)

# ==========================================
# 🎨 ESTILO VISUAL PROFESIONAL
# ==========================================
st.markdown("""
<style>
.stApp {background-color: #FFFFFF;}
section[data-testid="stSidebar"] {
    background-color: #0F172A;
}
section[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
div.stButton > button {
    background-color: #2563EB;
    color: white;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px;
    border: none;
}
div.stButton > button:hover {
    background-color: #1E40AF;
}
div[data-testid="stMetricValue"] {
    font-size: 26px;
    color: #15803D;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 LOGIN
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'seccion' not in st.session_state:
    st.session_state.seccion = "Inicio"

if not st.session_state.autenticado:
    st.title("🔒 Acceso Vinchy Zapas")
    st.image(LOGO_URL, width=90)
    with st.form("login"):
        pin = st.text_input("PIN", type="password")
        if st.form_submit_button("ENTRAR"):
            if pin == st.secrets["PIN_APP"]:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("PIN incorrecto")
    st.stop()

# ==========================================
# 🧠 FUNCIONES
# ==========================================
def texto_a_float(v):
    try:
        return float(str(v).replace("€","").replace(".","").replace(",","."))
    except:
        return 0.0

def float_a_texto(n):
    try:
        return f"{float(n):.2f}".replace(".",",")
    except:
        return "0,00"

def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["gcp_service_account"]), scope
    )
    client = gspread.authorize(creds)
    return client.open("inventario_zapatillas").sheet1

@st.cache_data(ttl=0)
def cargar():
    sheet = conectar_sheets()
    df = pd.DataFrame(sheet.get_all_records()).astype(str)
    df["ID"] = pd.to_numeric(df["ID"])
    df["🌐 Web"] = "https://www.google.com/search?q=" + df["Marca"] + "+" + df["Modelo"]
    return df

def guardar(df):
    sheet = conectar_sheets()
    if "🌐 Web" in df.columns:
        df = df.drop(columns=["🌐 Web"])
    sheet.clear()
    sheet.update([df.columns.tolist()] + df.values.tolist())
    st.cache_data.clear()

df = cargar()

# ==========================================
# 📚 SIDEBAR
# ==========================================
st.sidebar.image(LOGO_URL, width=100)
st.sidebar.title("VINCHY ZAPAS")

if st.sidebar.button("🏠 Inicio"): st.session_state.seccion = "Inicio"; st.rerun()
if st.sidebar.button("➕ Nueva compra"): st.session_state.seccion = "Nuevo"; st.rerun()
if st.sidebar.button("💸 Vender"): st.session_state.seccion = "Vender"; st.rerun()
if st.sidebar.button("📋 Historial"): st.session_state.seccion = "Historial"; st.rerun()
if st.sidebar.button("📊 Finanzas"): st.session_state.seccion = "Finanzas"; st.rerun()
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar sesión"):
    st.session_state.autenticado = False
    st.rerun()

# ==========================================
# 🏠 INICIO
# ==========================================
if st.session_state.seccion == "Inicio":
    st.title("👟 Panel de Control")
    st.markdown("Gestión profesional de stock y beneficios")

# ==========================================
# ➕ NUEVA COMPRA
# ==========================================
elif st.session_state.seccion == "Nuevo":
    st.title("➕ Nueva compra")
    with st.form("new"):
        marca = st.text_input("Marca")
        modelo = st.text_input("Modelo")
        talla = st.text_input("Talla")
        tienda = st.text_input("Tienda origen")
        precio = st.text_input("Precio compra (€)")
        if st.form_submit_button("Guardar"):
            nid = int(df["ID"].max()) + 1 if not df.empty else 1
            new = {
                "ID": nid,
                "Marca": marca,
                "Modelo": modelo,
                "Talla": talla,
                "Tienda Origen": tienda,
                "Precio Compra": precio,
                "Precio Venta": "0,00",
                "Ganancia Neta": "0,00",
                "ROI %": "0,00",
                "Estado": "En Stock",
                "Fecha Compra": datetime.now().strftime("%d/%m/%Y"),
                "Fecha Venta": "",
                "Plataforma Venta": "",
                "Cuenta Venta": "",
                "Tracking": ""
            }
            guardar(pd.concat([df, pd.DataFrame([new])], ignore_index=True))
            st.success("Compra añadida")
            time.sleep(1)
            st.rerun()

# ==========================================
# 💸 VENDER
# ==========================================
elif st.session_state.seccion == "Vender":
    st.title("💸 Vender zapatilla")
    stock = df[df["Estado"]=="En Stock"]
    sel = st.selectbox(
        "Selecciona",
        ["-"] + stock.apply(lambda x: f"{x.ID} | {x.Marca} {x.Modelo}", axis=1).tolist()
    )
    if sel != "-":
        sid = int(sel.split("|")[0])
        idx = df.index[df["ID"]==sid][0]
        pv = st.text_input("Precio venta (€)")
        if st.button("Confirmar venta"):
            pc = texto_a_float(df.at[idx,"Precio Compra"])
            pvf = texto_a_float(pv)
            gan = pvf - pc
            roi = (gan / pc * 100) if pc > 0 else 0
            df.at[idx,"Precio Venta"] = float_a_texto(pvf)
            df.at[idx,"Ganancia Neta"] = float_a_texto(gan)
            df.at[idx,"ROI %"] = float_a_texto(roi)
            df.at[idx,"Estado"] = "Vendido"
            df.at[idx,"Fecha Venta"] = datetime.now().strftime("%d/%m/%Y")
            guardar(df)
            st.success(f"Vendido +{gan:.2f}€")
            st.balloons()
            time.sleep(1)
            st.rerun()

# ==========================================
# 📋 HISTORIAL
# ==========================================
elif st.session_state.seccion == "Historial":
    st.title("📋 Historial")
    filtro = st.radio("Mostrar:", ["Todos","En Stock","Vendidos"], horizontal=True)
    dfh = df.copy()
    if filtro == "En Stock": dfh = dfh[dfh["Estado"]=="En Stock"]
    if filtro == "Vendidos": dfh = dfh[dfh["Estado"]=="Vendido"]
    edit = st.data_editor(dfh, hide_index=True, use_container_width=True)
    if st.button("💾 Guardar cambios"):
        for _, r in edit.iterrows():
            idx = df.index[df["ID"]==r["ID"]][0]
            pc = texto_a_float(r["Precio Compra"])
            pv = texto_a_float(r["Precio Venta"])
            df.loc[idx] = r
            df.at[idx,"Ganancia Neta"] = float_a_texto(pv-pc)
            df.at[idx,"ROI %"] = float_a_texto((pv-pc)/pc*100 if pc>0 else 0)
        guardar(df)
        st.success("Cambios guardados")
        time.sleep(1)
        st.rerun()

# ==========================================
# 📊 FINANZAS
# ==========================================
elif st.session_state.seccion == "Finanzas":
    st.title("📊 Finanzas")
    dff = df.copy()
    for c in ["Precio Compra","Precio Venta","Ganancia Neta","ROI %"]:
        dff[c] = dff[c].apply(texto_a_float)
    vendidos = dff[dff["Estado"]=="Vendido"]
    stock = dff[dff["Estado"]=="En Stock"]
    c1,c2,c3 = st.columns(3)
    c1.metric("Beneficio total", float_a_texto(vendidos["Ganancia Neta"].sum())+" €")
    c2.metric("Dinero en stock", float_a_texto(stock["Precio Compra"].sum())+" €")
    c3.metric("ROI medio", float_a_texto(vendidos["ROI %"].mean())+" %")
    if not vendidos.empty:
        fig = px.pie(vendidos, names="Marca", values="Ganancia Neta", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
