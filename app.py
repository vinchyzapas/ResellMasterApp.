import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# CONFIG
# ==========================================
st.set_page_config(page_title="Vinchy Zapas", layout="wide", page_icon="👟")

# ==========================================
# FUNCIONES CLAVE
# ==========================================
def leer_numero_literal(valor):
    if valor is None:
        return 0.0
    txt = str(valor).strip()
    if txt == "" or txt.lower() == "nan":
        return 0.0

    txt = txt.replace("€", "").replace(" ", "")
    txt = txt.replace(",", ".")

    try:
        return float(txt)
    except:
        return 0.0

def numero_a_texto(valor):
    try:
        return f"{float(valor):.2f}".replace(".", ",")
    except:
        return ""

def obtener_libro_google():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["gcp_service_account"]), scope
    )
    client = gspread.authorize(creds)
    return client.open("inventario_zapatillas")

# ==========================================
# CARGAR DATOS
# ==========================================
@st.cache_data(ttl=5)
def cargar_datos():
    libro = obtener_libro_google()
    sheet = libro.sheet1
    df = pd.DataFrame(sheet.get_all_records())

    if df.empty:
        return pd.DataFrame()

    for c in ["Precio Compra", "Precio Venta", "Ganancia Neta"]:
        df[c] = df[c].apply(leer_numero_literal)

    df["Fecha Compra"] = pd.to_datetime(df["Fecha Compra"], dayfirst=True, errors="coerce")
    df["Fecha Venta"] = pd.to_datetime(df["Fecha Venta"], dayfirst=True, errors="coerce")

    return df

# ==========================================
# GUARDAR DATOS (ANTI GOOGLE)
# ==========================================
def guardar_datos(df):
    libro = obtener_libro_google()
    sheet = libro.sheet1

    out = df.copy()

    # 🔒 PRECIOS COMO TEXTO
    out["Precio Compra"] = out["Precio Compra"].apply(numero_a_texto)
    out["Precio Venta"] = out["Precio Venta"].apply(numero_a_texto)
    out["Ganancia Neta"] = out["Ganancia Neta"].apply(numero_a_texto)

    out["Fecha Compra"] = out["Fecha Compra"].dt.strftime("%d/%m/%Y").replace("NaT", "")
    out["Fecha Venta"] = out["Fecha Venta"].dt.strftime("%d/%m/%Y").replace("NaT", "")

    out = out.fillna("")

    sheet.clear()
    sheet.update([out.columns.tolist()] + out.values.tolist())
    st.cache_data.clear()

# ==========================================
# APP
# ==========================================
st.title("👟 Vinchy Zapas")

df = cargar_datos()

if df.empty:
    st.info("No hay datos todavía")
    st.stop()

st.subheader("📋 Historial")

df_edit = st.data_editor(
    df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Precio Compra": st.column_config.TextColumn(),
        "Precio Venta": st.column_config.TextColumn(),
        "Ganancia Neta": st.column_config.TextColumn(disabled=True),
        "Fecha Compra": st.column_config.DateColumn("DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn("DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(
            options=["En Stock", "Vendido"]
        )
    }
)

if not df.equals(df_edit):
    df_edit["Precio Compra"] = df_edit["Precio Compra"].apply(leer_numero_literal)
    df_edit["Precio Venta"] = df_edit["Precio Venta"].apply(leer_numero_literal)
    df_edit["Ganancia Neta"] = df_edit["Precio Venta"] - df_edit["Precio Compra"]

    guardar_datos(df_edit)
    st.success("✅ Guardado sin errores")
