import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Stock Zapatillas", layout="wide")

PIN = st.secrets["PIN_APP"]

# ---------------- LOGIN ----------------
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pin = st.text_input("Introduce PIN", type="password")
    if st.button("Entrar"):
        if pin == PIN:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("PIN incorrecto")
    st.stop()

# ---------------- GOOGLE SHEETS ----------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)
client = gspread.authorize(creds)
sheet = client.open("STOCK_ZAPATILLAS").sheet1

# ---------------- FUNCIONES ----------------
def texto_a_float(valor):
    if valor is None or valor == "":
        return 0.0
    try:
        v = str(valor).replace("€", "").strip()
        if "." in v and "," in v:
            v = v.replace(".", "")
        v = v.replace(",", ".")
        return float(v)
    except:
        return 0.0

def float_a_texto(v):
    return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_ganancia(estado, compra, venta):
    if estado == "EN STOCK":
        return -compra
    else:
        return venta - compra

# ---------------- CARGA DATOS ----------------
data = sheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    df["Precio Compra (€)"] = df["Precio Compra (€)"].apply(texto_a_float)
    df["Precio Venta (€)"] = df["Precio Venta (€)"].apply(texto_a_float)

# ---------------- MENU ----------------
menu = st.sidebar.radio(
    "Menú",
    ["Añadir", "Stock", "Vender", "Historial"]
)

# ---------------- AÑADIR ----------------
if menu == "Añadir":
    st.title("➕ Añadir zapatilla")

    modelo = st.text_input("Modelo")
    talla = st.text_input("Talla")
    pc = st.number_input("Precio compra (€)", min_value=0.0, step=1.0)
    web = st.text_input("Web / URL")

    if st.button("Guardar"):
        nueva = [
            modelo,
            talla,
            float_a_texto(pc),
            "",
            float_a_texto(-pc),
            "EN STOCK",
            web,
            datetime.now().strftime("%d/%m/%Y")
        ]
        sheet.append_row(nueva)
        st.success("Zapatilla añadida")

# ---------------- STOCK ----------------
elif menu == "Stock":
    st.title("📦 En stock")
    st.dataframe(df[df["Estado"] == "EN STOCK"])

# ---------------- VENDER ----------------
elif menu == "Vender":
    st.title("💰 Vender zapatilla")

    stock = df[df["Estado"] == "EN STOCK"].copy()

    stock["selector"] = (
        stock["Modelo"] + " | Talla " + stock["Talla"].astype(str) +
        " | Compra " + stock["Precio Compra (€)"].apply(lambda x: float_a_texto(x))
    )

    opcion = st.selectbox("Selecciona zapatilla", stock["selector"])

    fila = stock[stock["selector"] == opcion].iloc[0]
    idx = stock[stock["selector"] == opcion].index[0]

    pv = st.number_input("Precio venta (€)", min_value=0.0, step=1.0)

    if st.button("Confirmar venta"):
        gan = calcular_ganancia("VENDIDO", fila["Precio Compra (€)"], pv)

        df.at[idx, "Precio Venta (€)"] = float_a_texto(pv)
        df.at[idx, "Ganancia Neta"] = float_a_texto(gan)
        df.at[idx, "Estado"] = "VENDIDO"

        sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
        st.success("Venta registrada")

# ---------------- HISTORIAL ----------------
elif menu == "Historial":
    st.title("📜 Historial")

    def icono_web(url):
        if url:
            return f'<a href="{url}" target="_blank">🔗</a>'
        return ""

    df_hist = df.copy()
    df_hist["Web"] = df_hist["Web"].apply(icono_web)

    st.write(
        df_hist.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )
