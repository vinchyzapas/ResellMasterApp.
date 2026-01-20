import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V33", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL (CSS AGRESIVO) ---
st.markdown("""
<style>
    /* Fondo negro */
    .stApp {background-color: #0E1117; color: white;}
    section[data-testid="stSidebar"] {background-color: #000000;}
    section[data-testid="stSidebar"] * {color: white !important;}
    
    /* Cajas de texto */
    .stTextInput input, .stNumberInput input {
        background-color: #333333 !important;
        color: white !important;
        border: 1px solid #555;
    }
    
    /* Desplegables */
    div[data-baseweb="select"] > div {background-color: #333333 !important; color: white !important;}
    
    /* 🔴 BOTÓN ROJO FORZADO */
    div.stButton > button:first-child {
        background-color: #FF0000 !important;
        color: white !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border: 2px solid #990000 !important;
        border-radius: 8px !important;
        width: 100% !important;
    }
    div.stButton > button:hover {
        background-color: #CC0000 !important;
        color: #EEEEEE !important;
    }
    
    label {color: white !important;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.markdown("### 🟢 Versión 33") # AQUÍ ESTÁ EL INDICADOR DE VERSIÓN
    st.write("---")
    
    with st.form("login_form"):
        st.markdown("### Introduce tu clave:")
        pin = st.text_input("PIN", type="password", label_visibility="collapsed")
        st.write("") 
        submit = st.form_submit_button("ENTRAR AL SISTEMA")
        
        if submit:
            if pin == "1234": 
                st.session_state['autenticado'] = True
                st.rerun()
            else: 
                st.error("🚫 PIN Incorrecto")
    st.stop()

# --- CONEXIÓN ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except: return None

# --- CONVERSORES DE PRECIO ---
def texto_a_numero(texto):
    if not texto: return 0.0
    try:
        if isinstance(texto, (int, float)): return float(texto)
        limpio = str(texto).replace("€", "").strip().replace(",", ".")
        return float(limpio)
    except: return 0.0

def numero_a_texto_bonito(valor):
    try:
        if valor == 0: return "0,00 €"
        return f"{float(valor):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00 €"

# --- CARGAR DATOS ---
@st.cache_data(ttl=5, show_spinner=False)
def cargar_datos_cacheado():
    cols = ["ID", "Fecha Compra", "Fecha Venta", "Marca", "Modelo", "Talla", "Tienda Origen", 
            "Plataforma Venta", "Cuenta Venta", "Precio Compra", "Precio Venta", 
            "Estado", "Ganancia Neta", "ROI %"]
    sheet = conectar_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                for c in cols: 
                    if c not in df.columns: df[c] = ""
                
                df['Precio Compra'] = df['Precio Compra'].apply(texto_a_numero)
                df['Precio Venta'] = df['Precio Venta'].apply(texto_a_numero)
                df['Ganancia Neta'] = df['Precio Venta'] - df['Precio Compra']
                
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Talla'] = df['Talla'].astype(str).replace('nan', '')
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                
                if 'Marca' in df.columns: df['Marca'] = df['Marca'].astype(str).str.strip().str.title()
                
                return df[cols]
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        dfs['Precio Compra'] = dfs['Precio Compra'].apply(lambda x: str(x).replace(".", ","))
        dfs['Precio Venta'] = dfs['Precio Venta'].apply(lambda x: str(x).replace(".", ","))
        dfs['Ganancia Neta'] = dfs['Ganancia Neta'].apply(lambda x: str(x).replace(".", ","))
        
        dfs['Fecha Compra'] = dfs['Fecha Compra'].astype(str).replace('NaT', '')
        dfs['Fecha Venta'] = dfs['Fecha Venta'].astype(str).replace('NaT', '')
        
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        st.cache_data.clear()

# --- LISTAS ---
def obtener_listas(df):
    m = sorted(list(set(BASES_MARCAS + (df['Marca'].unique().tolist() if not df.empty else []))))
    t = sorted(list(set(BASES_TIENDAS + (df['Tienda Origen'].unique().tolist() if not df.empty else []))))
    return [x for x in m if str(x).strip() not in ["","nan"]], [x for x in t if str(x).strip() not in ["","nan"]]

# --- INTERFAZ ---
st.sidebar.title("Menú")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos_cacheado()
list_m, list_t = obtener_listas(df)

# --- 1. NUEVO ---
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        ms = c1.selectbox("Marca", ["-"] + list_m); mt = c1.text_input("¿Nueva?", placeholder="Escribe aquí")
        mf = str(mt if mt else ms).strip().title()
        if mf == "-": mf = ""
        mod = c2.text_input("Modelo")
        
        c3, c4, c5 = st.columns(3)
        ts = c3.selectbox("Tienda", ["-"] + list_t); tt = c3.text_input("¿Nueva?", placeholder="Escribe aquí")
        tf = str(tt if tt else ts).strip().title()
        if tf == "-": tf = ""
        
        ta = c4.text_input("Talla")
        pr_txt = c5.text_input("Precio Compra (€)", placeholder="Ej: 45,50")
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca o Modelo")
            else:
                p = texto_a_numero(pr_txt)
                nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":ta, "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df); st.session_state['ok']=True; st.rerun()

# --- 2. VENDER ---
elif op == "💸 Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    opcs = ["-"] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist()
    sel = st.selectbox("Buscar:", opcs)
    
    if sel != "-":
        ids = int(sel.split(" |")[0].replace("ID:",""))
        row = df[df['ID']==ids].iloc[0]
        st.info(f"VENDIENDO: {row['Marca']} {row['Modelo']}")
        with st.form("fv"):
            pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50")
            c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta Venta")
            if st.form_submit_button("CONFIRMAR VENTA"):
                pv = texto_a_numero(pv_txt)
                idx = df.index[df['ID']==ids][0]
                g = pv - row['Precio Compra']
                coste = row['Precio Compra']
                roi = (g/coste*100) if coste > 0 else 0
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=roi
                guardar_datos(df); st.balloons(); st.success("Vendido"); st.rerun()

# --- 3. HISTORIAL ---
elif op == "📦 Historial":
    st.title("📦 Historial")
    with st.expander("🗑️ ELIMINAR"):
        lb = ["-"] + df.apply(lambda x: f"ID:{x['ID']} | {x['Modelo']}", axis=1).tolist()
        sb = st.selectbox("Elegir:", lb)
        if sb != "-":
            idb = int(sb.split(" |")[0].replace("ID:",""))
            if st.button("BORRAR", type="primary"):
                guardar_datos(df[df['ID']!=idb]); st.success("Borrado"); st.rerun()
    
    df_visual = df.copy()
    df_visual['Precio Compra'] = df_visual['Precio Compra'].apply(numero_a_texto_bonito)
    df_visual['Precio Venta'] = df_visual['Precio Venta'].apply(numero_a_texto_bonito)
    df_visual['Ganancia Neta'] = df_visual['Ganancia Neta'].apply(numero_a_texto_bonito)
    df_visual['Fecha Compra'] = pd.to_datetime(df_visual['Fecha Compra']).dt.strftime('%d/%m/%Y').replace("NaT", "")
    df_visual['Fecha Venta'] = pd.to_datetime(df_visual['Fecha Venta']).dt.strftime('%d/%m/%Y').replace("NaT", "")
    st.dataframe(df_visual, hide_index=True, use_container_width=True)

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        s=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        ben = s['Ganancia Neta'].sum()
        gst = df[df['Estado']=='En Stock']['Precio Compra'].sum()
        k1.metric("Beneficio Neto", numero_a_texto_bonito(ben))
        k2.metric("Gasto Total en Stock", numero_a_texto_bonito(gst))
        st.divider()
        st.subheader("Gasto por Tienda")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        st.subheader("Beneficio por Plataforma")
        st.bar_chart(s.groupby('Plataforma Venta')['Ganancia Neta'].sum())
