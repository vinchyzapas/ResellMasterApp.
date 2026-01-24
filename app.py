import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
APP_TITLE = "Vinchy Zapas"
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2589/2589903.png"
SHEET_NAME = "inventario_zapatillas"
PIN_CORRECTO = "1234"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="👟",
    layout="wide"
)

# =====================================================
# ESTILOS
# =====================================================
st.markdown("""
<style>
.stApp { background-color: #f5f6fa; }
section[data-testid="stSidebar"] { background-color: #111; }
section[data-testid="stSidebar"] * { color: white !important; }
div.stButton > button {
    background-color: #d32f2f;
    color: white;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px;
}
div[data-testid="stMetricValue"] {
    font-size: 24px;
    color: #2e7d32;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# SESIÓN
# =====================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "seccion" not in st.session_state:
    st.session_state.seccion = "Inicio"

# =====================================================
# LOGIN
# =====================================================
if not st.session_state.autenticado:
    st.image(LOGO_URL, width=90)
    st.title("VINCHY ZAPAS")
    st.caption("Gestión de stock y reventa")

    with st.form("login"):
        pin = st.text_input("PIN de acceso", type="password")
        if st.form_submit_button("ENTRAR"):
            if pin == PIN_CORRECTO:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("PIN incorrecto")

    st.stop()

# =====================================================
# FUNCIONES ÚTILES
# =====================================================
def texto_a_float(v):
    if pd.isna(v) or str(v).strip() == "":
        return 0.0
    try:
        return float(str(v).replace("€", "").replace(",", "."))
    except:
        return 0.0

def float_a_texto(n):
    try:
        return f"{float(n):.2f}".replace(".", ",")
    except:
        return "0,00"

# =====================================================
# GOOGLE SHEETS
# =====================================================
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["gcp_service_account"]),
        scope
    )
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

@st.cache_data(ttl=0)
def cargar_datos():
    sheet = conectar_sheets()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "ID","Marca","Modelo","Talla","Precio Compra","Precio Venta",
            "Ganancia Neta","Estado","Fecha Compra","Fecha Venta"
        ])
    df = df.astype(str).replace("nan", "")
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
    df["🔎"] = "https://www.google.com/search?q=" + df["Marca"] + "+" + df["Modelo"]
    return df

def guardar_datos(df):
    sheet = conectar_sheets()
    out = df.drop(columns=["🔎"], errors="ignore").astype(str)
    sheet.clear()
    sheet.update([out.columns.tolist()] + out.values.tolist())
    st.cache_data.clear()

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.image(LOGO_URL, width=100)
st.sidebar.title("VINCHY ZAPAS")

if st.sidebar.button("🏠 Inicio"):
    st.session_state.seccion = "Inicio"
if st.sidebar.button("➕ Nueva compra"):
    st.session_state.seccion = "Nuevo"
if st.sidebar.button("💸 Vender"):
    st.session_state.seccion = "Vender"
if st.sidebar.button("📋 Historial"):
    st.session_state.seccion = "Historial"
if st.sidebar.button("📊 Finanzas"):
    st.session_state.seccion = "Finanzas"

st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar sesión"):
    st.session_state.autenticado = False
    st.rerun()

df = cargar_datos()

# =====================================================
# INICIO
# =====================================================
if st.session_state.seccion == "Inicio":
    st.title("👟 Panel principal")
    st.metric("En stock", len(df[df["Estado"]=="En Stock"]))
    st.metric("Vendidas", len(df[df["Estado"]=="Vendido"]))

# =====================================================
# NUEVA COMPRA
# =====================================================
elif st.session_state.seccion == "Nuevo":
    st.title("➕ Nueva compra")
    with st.form("nueva"):
        marca = st.text_input("Marca")
        modelo = st.text_input("Modelo")
        talla = st.text_input("Talla")
        precio = st.text_input("Precio compra (€)")
        if st.form_submit_button("Guardar"):
            nid = 1 if df.empty else df["ID"].max() + 1
            pc = texto_a_float(precio)
            nuevo = {
                "ID": nid,
                "Marca": marca,
                "Modelo": modelo,
                "Talla": talla,
                "Precio Compra": float_a_texto(pc),
                "Precio Venta": "0,00",
                "Ganancia Neta": float_a_texto(-pc),
                "Estado": "En Stock",
                "Fecha Compra": datetime.now().strftime("%d/%m/%Y"),
                "Fecha Venta": ""
            }
            df = pd.concat([df, pd.DataFrame([nuevo])])
            guardar_datos(df)
            st.success("Compra guardada")
            time.sleep(1)
            st.rerun()

# =====================================================
# VENDER
# =====================================================
elif st.session_state.seccion == "Vender":
    st.title("💸 Vender zapatilla")
    stock = df[df["Estado"]=="En Stock"]
    opciones = stock.apply(
        lambda x: f"ID {x['ID']} | {x['Modelo']} | Talla {x['Talla']}",
        axis=1
    ).tolist()
    sel = st.selectbox("Selecciona", opciones)
    if sel:
        id_sel = int(sel.split("|")[0].replace("ID",""))
        idx = df.index[df["ID"]==id_sel][0]
        pv = st.text_input("Precio venta (€)")
        if st.button("Confirmar venta"):
            pvf = texto_a_float(pv)
            pcf = texto_a_float(df.at[idx,"Precio Compra"])
            gan = pvf - pcf
            df.at[idx,"Precio Venta"] = float_a_texto(pvf)
            df.at[idx,"Ganancia Neta"] = float_a_texto(gan)
            df.at[idx,"Estado"] = "Vendido"
            df.at[idx,"Fecha Venta"] = datetime.now().strftime("%d/%m/%Y")
            guardar_datos(df)
            st.success("Venta registrada")
            st.balloons()
            time.sleep(1)
            st.rerun()

# =====================================================
# HISTORIAL
# =====================================================
elif st.session_state.seccion == "Historial":
    st.title("📋 Historial")
    df_edit = st.data_editor(
        df,
        column_config={
            "🔎": st.column_config.LinkColumn("Web", display_text="🔎"),
            "Estado": st.column_config.SelectboxColumn(
                options=["En Stock","Vendido"]
            )
        },
        hide_index=True,
        use_container_width=True
    )
    if st.button("💾 Guardar cambios"):
        # recalcular ganancias
        for i,row in df_edit.iterrows():
            pc = texto_a_float(row["Precio Compra"])
            pv = texto_a_float(row["Precio Venta"])
            if row["Estado"]=="En Stock":
                df_edit.at[i,"Ganancia Neta"] = float_a_texto(-pc)
            else:
                df_edit.at[i,"Ganancia Neta"] = float_a_texto(pv-pc)
        guardar_datos(df_edit)
        st.success("Cambios guardados")
        time.sleep(1)
        st.rerun()

# =====================================================
# FINANZAS
# =====================================================
elif st.session_state.seccion == "Finanzas":
    st.title("📊 Finanzas")
    calc = df.copy()
    calc["Ganancia Neta"] = calc["Ganancia Neta"].apply(texto_a_float)
    total = calc["Ganancia Neta"].sum()
    st.metric("Resultado total", float_a_texto(total) + " €")
