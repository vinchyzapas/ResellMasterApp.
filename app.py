
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V26", layout="wide", page_icon="👟")

# --- 🌑 MODO OSCURO TOTAL ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117; color: #FFFFFF;}
    section[data-testid="stSidebar"] {background-color: #000000;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    .stRadio label {color: #FFFFFF !important; font-weight: bold;}
    .stTextInput input, .stNumberInput input {color: white !important; background-color: #333333 !important;}
    .stSelectbox div[data-baseweb="select"] > div {background-color: #333333 !important; color: white !important;}
    div[data-baseweb="menu"] {background-color: #333333 !important;}
    /* Botón de entrar grande */
    .stButton button {width: 100%; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN CON BOTÓN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    
    with st.form("login_form"):
        pin_input = st.text_input("Introduce PIN:", type="password")
        submit_button = st.form_submit_button("ENTRAR")
        
        if submit_button:
            if pin_input == "1234":
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("🚫 PIN Incorrecto")
    st.stop()

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except Exception as e:
        return None

# --- LIMPIADOR DE PRECIOS ---
def limpiar_precio(texto):
    if not texto: return 0.0
    try:
        limpio = str(texto).replace("€", "").strip().replace(",", ".")
        return float(limpio)
    except:
        return 0.0

# --- CARGAR DATOS (CON CACHÉ PARA EVITAR ERROR DE CONEXIÓN) ---
# ttl=10 significa que mantiene los datos en memoria 10 segundos antes de volver a llamar a Google
@st.cache_data(ttl=10, show_spinner=False)
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
                    if c not in df.columns: df[c] = 0.0 if "Precio" in c else ""
                
                # Limpiezas
                df['Precio Compra'] = pd.to_numeric(df['Precio Compra'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Precio Venta'] = pd.to_numeric(df['Precio Venta'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Ganancia Neta'] = pd.to_numeric(df['Ganancia Neta'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                
                if 'Marca' in df.columns: df['Marca'] = df['Marca'].astype(str).str.strip().str.title()
                if 'Tienda Origen' in df.columns: df['Tienda Origen'] = df['Tienda Origen'].astype(str).str.strip().str.title()
                
                return df[cols]
            else:
                return pd.DataFrame(columns=cols)
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR DATOS (Limpia la caché para ver cambios al instante) ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        dfs['Fecha Compra'] = dfs['Fecha Compra'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs['Fecha Venta'] = dfs['Fecha Venta'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        # Borramos la caché para que al recargar se vean los datos nuevos
        st.cache_data.clear()

# --- LISTAS INTELIGENTES ---
def obtener_listas_actualizadas(df):
    marcas, tiendas = [], []
    if not df.empty:
        if 'Marca' in df.columns: marcas = df['Marca'].unique().tolist()
        if 'Tienda Origen' in df.columns: tiendas = df['Tienda Origen'].unique().tolist()
    
    todas_marcas = sorted(list(set(BASES_MARCAS + marcas)))
    todas_tiendas = sorted(list(set(BASES_TIENDAS + tiendas)))
    return [m for m in todas_marcas if str(m).strip() not in ["", "nan"]], [t for t in todas_tiendas if str(t).strip() not in ["", "nan"]]

# --- ESTADO ---
keys = ['k_marca_sel', 'k_marca_txt', 'k_modelo', 'k_tienda_sel', 'k_tienda_txt', 'k_talla', 'k_precio']
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys: st.session_state[k] = ""
    st.session_state['limpiar'] = False

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.sidebar.title("Menú")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

# CARGAMOS DATOS USANDO LA CACHÉ (Esto evita el error de conexión)
df = cargar_datos_cacheado()
# Si falla la carga (df vacío por error), intentamos reconectar
if df.empty and not conectar_sheets():
    st.error("Error de conexión. Intenta recargar.")
    st.stop()

mis_marcas, mis_tiendas = obtener_listas_actualizadas(df)

# --- 1. NUEVO PRODUCTO ---
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        with c1:
            ms = st.selectbox("Marca", ["- Seleccionar -"] + mis_marcas, key="k_marca_sel")
            mt = st.text_input("¿Nueva?", key="k_marca_txt")
            mf = mt if mt else ms
            if mf == "- Seleccionar -": mf = ""

        mod = c2.text_input("Modelo", key="k_modelo")

        c3, c4, c5 = st.columns(3)
        with c3:
            ts = st.selectbox("Tienda", ["- Seleccionar -"] + mis_tiendas, key="k_tienda_sel")
            tt = st.text_input("¿Nueva?", key="k_tienda_txt")
            tf = tt if tt else ts
            if tf == "- Seleccionar -": tf = ""

        ta = c4.text_input("Talla", key="k_talla")
        pr_txt = c5.text_input("Precio Compra (€)", key="k_precio", placeholder="Ej: 50,90")
        
        if st.form_submit_button("GUARDAR", use_container_width=True):
            if not mf or not mod: st.error("⚠️ Falta datos")
            else:
                nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":str(mf).strip().title(), "Modelo":mod, "Talla":ta, "Tienda Origen":str(tf).strip().title(), "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":limpiar_precio(pr_txt), "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df); st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

# --- 2. VENDER ---
elif op == "💸 Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    if dfs.empty: st.warning("Sin stock.")
    else:
        sel = st.selectbox("Busca:", ["Seleccionar..."] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist())
        if sel != "Seleccionar...":
            ids = int(float(sel.split(" |")[0].replace("ID:","")))
            row = df[df['ID']==ids].iloc[0]
            st.info(f"VENDIENDO: **{row['Marca']} {row['Modelo']}**")
            with st.form("fv"):
                pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50")
                c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta Venta")
                if st.form_submit_button("CONFIRMAR VENTA", use_container_width=True):
                    pv = limpiar_precio(pv_txt); idx=df.index[df['ID']==ids][0]; g=pv-row['Precio Compra']
                    df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g
                    guardar_datos(df); st.balloons(); st.success("¡Vendido!"); st.rerun()

# --- 3. HISTORIAL (ESTABLE) ---
elif op == "📦 Historial":
    st.title("📦 Historial")
    with st.expander("🗑️ ELIMINAR"):
        sb = st.selectbox("Buscar:", ["- Elegir -"] + df.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1).tolist())
        if sb != "- Elegir -":
            idb = int(sb.split(" |")[0].replace("ID:", ""))
            if st.button(f"🗑️ BORRAR ID {idb}", type="primary"):
                guardar_datos(df[df['ID'] != idb]); st.success("Borrado."); st.rerun()

    # Tabla sin edición directa para MAXIMA ESTABILIDAD en el móvil
    # Si quieres editar, es mejor borrar y crear de nuevo para evitar el "refresh loop"
    st.dataframe(df, hide_index=True, use_container_width=True)

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        ben = sold['Ganancia Neta'].sum() if not sold.empty else 0.0
        gasto = df[df['Estado']=='En Stock']['Precio Compra'].sum() if not df.empty else 0.0
        k1.metric("Beneficio Neto Total", f"{ben:.2f} €")
        k2.metric("Gasto Total en Stock", f"{gasto:.2f} €")
        st.divider()
        st.subheader("Gasto por Tienda"); st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        st.subheader("Beneficio por Plataforma"); st.bar_chart(sold.groupby('Plataforma Venta')['Ganancia Neta'].sum())
