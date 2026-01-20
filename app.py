
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V27", layout="wide", page_icon="👟")

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
    .stButton button {width: 100%; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    with st.form("login"):
        pin = st.text_input("PIN:", type="password")
        if st.form_submit_button("ENTRAR"):
            if pin == "1234": st.session_state['autenticado'] = True; st.rerun()
            else: st.error("Mal")
    st.stop()

# --- CONEXIÓN ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except: return None

# --- HERRAMIENTA DE REPARACIÓN INTELIGENTE ---
def reparar_valor_precio(valor):
    try:
        # 1. Convertir a número float puro
        v_str = str(valor).replace("€", "").replace(",", ".").strip()
        if not v_str: return 0.0
        v = float(v_str)
        
        # 2. Aplicar lógica de Vinchy (Nada vale más de 100€)
        if v > 1000: 
            return v / 100  # Ej: 4544 -> 45.44
        elif v > 100: 
            return v / 10   # Ej: 234 -> 23.4
        else:
            return v        # Ej: 50 -> 50
    except:
        return 0.0

def reparar_talla(valor):
    try:
        v = str(valor).strip()
        if v.endswith(".0"): 
            return v.replace(".0", "") # Quita el decimal feo a las tallas
        return v
    except: return str(valor)

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
                
                # Conversiones básicas
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                
                # Asegurar que Talla sea texto (para que no salga 42.0)
                df['Talla'] = df['Talla'].astype(str).replace('nan', '')
                
                return df[cols]
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        dfs['Fecha Compra'] = dfs['Fecha Compra'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs['Fecha Venta'] = dfs['Fecha Venta'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
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
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial", "🔧 REPARAR DATOS", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos_cacheado()
list_m, list_t = obtener_listas(df)

# --- 1. NUEVO PRODUCTO ---
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        ms = c1.selectbox("Marca", ["-"] + list_m); mt = c1.text_input("¿Nueva?", placeholder="Escribe aquí")
        mf = str(mt if mt else ms).strip().title()
        mod = c2.text_input("Modelo")
        
        c3, c4, c5 = st.columns(3)
        ts = c3.selectbox("Tienda", ["-"] + list_t); tt = c3.text_input("¿Nueva?", placeholder="Escribe aquí")
        tf = str(tt if tt else ts).strip().title()
        
        ta = c4.text_input("Talla")
        pr_txt = c5.text_input("Precio (€)", placeholder="Ej: 45,50")
        
        if st.form_submit_button("GUARDAR"):
            if not mod: st.error("Falta Modelo")
            else:
                p = reparar_valor_precio(pr_txt) # Usamos la función de limpieza al guardar
                nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":ta, "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df); st.success("Guardado"); st.rerun()

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
            pv_txt = st.text_input("Precio Venta (€)")
            c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX"]); cta=c4.text_input("Cuenta")
            if st.form_submit_button("CONFIRMAR"):
                pv = reparar_valor_precio(pv_txt)
                idx = df.index[df['ID']==ids][0]
                g = pv - row['Precio Compra']
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g
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
    
    # Tabla visual
    st.dataframe(df, hide_index=True, use_container_width=True)

# --- 🔧 HERRAMIENTA DE REPARACIÓN (NUEVO) ---
elif op == "🔧 REPARAR DATOS":
    st.title("🔧 Reparación Automática")
    st.warning("Usa esto SOLO si ves los precios mal (ej: 4544 en vez de 45.44).")
    
    st.write("Esta herramienta hará lo siguiente:")
    st.write("- Si el precio es > 1000 (ej: 4544), lo divide entre 100 (-> 45.44)")
    st.write("- Si el precio es > 100 (ej: 234), lo divide entre 10 (-> 23.4)")
    st.write("- Arregla las tallas (ej: quita el .0)")
    
    if st.button("🚨 ARREGLAR TODOS LOS PRECIOS Y TALLAS AHORA", type="primary"):
        # Aplicamos la lógica a toda la tabla
        df['Precio Compra'] = df['Precio Compra'].apply(reparar_valor_precio)
        df['Precio Venta'] = df['Precio Venta'].apply(reparar_valor_precio)
        df['Talla'] = df['Talla'].apply(reparar_talla)
        
        # Recalcular ganancias
        df['Ganancia Neta'] = df['Precio Venta'] - df['Precio Compra']
        # Corregir negativos en stock (si no se ha vendido, ganancia es 0)
        df.loc[df['Estado']=='En Stock', 'Ganancia Neta'] = 0.0
        
        guardar_datos(df)
        st.success("¡Datos reparados! Ve al historial a comprobarlo.")
        st.cache_data.clear() # Limpiar caché para ver cambios

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        s=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        # Formato visual correcto
        ben = s['Ganancia Neta'].sum()
        gst = df[df['Estado']=='En Stock']['Precio Compra'].sum()
        k1.metric("Beneficio Neto", f"{ben:,.2f} €".replace(",", "@").replace(".", ",").replace("@", "."))
        k2.metric("Stock Activo", f"{gst:,.2f} €".replace(",", "@").replace(".", ",").replace("@", "."))
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
