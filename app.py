
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V30", layout="wide", page_icon="👟")

# --- 🌑 MODO OSCURO & BOTONES ROJOS (DISEÑO) ---
st.markdown("""
<style>
    /* Fondo principal negro */
    .stApp {background-color: #0E1117; color: #FFFFFF;}
    
    /* Barra lateral negra */
    section[data-testid="stSidebar"] {background-color: #000000;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    
    /* Inputs (Cajas de texto) gris oscuro y letra blanca */
    .stTextInput input, .stNumberInput input {
        color: white !important; 
        background-color: #333333 !important;
        border: 1px solid #555;
    }
    
    /* Selectbox (Desplegables) */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #333333 !important; 
        color: white !important;
    }
    div[data-baseweb="menu"] {background-color: #333333 !important;}
    
    /* --- BOTONES ROJOS --- */
    .stButton button {
        width: 100%; 
        font-weight: bold;
        background-color: #FF4B4B !important; /* Rojo */
        color: white !important; /* Letras blancas */
        border: none;
    }
    .stButton button:hover {
        background-color: #FF0000 !important; /* Rojo más fuerte al pasar ratón */
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.write("") # Espacio
    with st.form("login_form"):
        pin = st.text_input("PIN DE ACCESO:", type="password")
        # Este botón ahora será ROJO con letras BLANCAS gracias al CSS de arriba
        submit = st.form_submit_button("ENTRAR")
        
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

# --- LIMPIADOR INTELIGENTE (COMA O PUNTO) ---
def limpiar_precio(texto):
    if not texto: return 0.0
    try:
        # 1. Quitamos símbolo € y espacios
        limpio = str(texto).replace("€", "").strip()
        # 2. Reemplazamos coma por punto (para que Python entienda el número)
        limpio = limpio.replace(",", ".")
        # 3. Devolvemos número decimal
        return float(limpio)
    except:
        return 0.0

# --- CARGAR DATOS ---
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
                
                # --- LIMPIEZA DE LECTURA ---
                # Convertimos precios a números para poder sumar en finanzas
                # Esto maneja si en el Excel hay "45,50" o "45.50"
                df['Precio Compra'] = pd.to_numeric(df['Precio Compra'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Precio Venta'] = pd.to_numeric(df['Precio Venta'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Ganancia Neta'] = pd.to_numeric(df['Ganancia Neta'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                
                # TALLA: Forzamos a texto para que no ponga .0
                df['Talla'] = df['Talla'].astype(str).replace('nan', '')
                
                if 'Marca' in df.columns: df['Marca'] = df['Marca'].astype(str).str.strip().str.title()
                if 'Tienda Origen' in df.columns: df['Tienda Origen'] = df['Tienda Origen'].astype(str).str.strip().str.title()
                
                return df[cols]
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        # Fechas bonitas
        dfs['Fecha Compra'] = dfs['Fecha Compra'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs['Fecha Venta'] = dfs['Fecha Venta'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        st.cache_data.clear()

# --- LISTAS INTELIGENTES ---
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

# --- 1. NUEVO PRODUCTO ---
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        with c1:
            ms = st.selectbox("Marca", ["- Seleccionar -"] + list_m)
            mt = st.text_input("¿Nueva?", placeholder="Escribe aquí")
            mf = str(mt if mt else ms).strip().title()
            if mf == "- Seleccionar -": mf = ""

        mod = c2.text_input("Modelo")

        c3, c4, c5 = st.columns(3)
        with c3:
            ts = st.selectbox("Tienda", ["- Seleccionar -"] + list_t)
            tt = st.text_input("¿Nueva?", placeholder="Escribe aquí")
            tf = str(tt if tt else ts).strip().title()
            if tf == "- Seleccionar -": tf = ""

        ta = c4.text_input("Talla")
        
        # PRECIO: Texto libre para que aceptes comas
        pr_txt = c5.text_input("Precio Compra (€)", placeholder="Ej: 45,50")
        
        if st.form_submit_button("GUARDAR"):
            if not mod or not mf: st.error("Falta Marca o Modelo")
            else:
                # Limpiamos el precio (coma o punto -> float)
                p = limpiar_precio(pr_txt)
                nid = 1 if df.empty else df['ID'].max()+1
                
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, 
                       "Marca":mf, "Modelo":mod, "Talla":ta, "Tienda Origen":tf, 
                       "Plataforma Venta":"", "Cuenta Venta":"", 
                       "Precio Compra":p, "Precio Venta":0.0, 
                       "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df)
                st.session_state['ok']=True; st.rerun()

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
            if st.form_submit_button("CONFIRMAR"):
                pv = limpiar_precio(pv_txt)
                idx = df.index[df['ID']==ids][0]
                g = pv - row['Precio Compra']
                coste = row['Precio Compra']
                roi = (g/coste*100) if coste > 0 else 0
                
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv
                df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=roi
                
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
    st.dataframe(df, hide_index=True, use_container_width=True)

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        s=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        ben = s['Ganancia Neta'].sum()
        gst = df[df['Estado']=='En Stock']['Precio Compra'].sum()
        
        # Formato visual europeo (con coma para decimales en la tarjeta)
        ben_str = f"{ben:,.2f} €".replace(",", "@").replace(".", ",").replace("@", ".")
        gst_str = f"{gst:,.2f} €".replace(",", "@").replace(".", ",").replace("@", ".")
        
        k1.metric("Beneficio Neto Total", ben_str)
        k2.metric("Gasto Total en Stock", gst_str)
        
        st.divider()
        st.subheader("Gasto por Tienda")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        
        st.subheader("Beneficio por Plataforma")
        st.bar_chart(s.groupby('Plataforma Venta')['Ganancia Neta'].sum())
