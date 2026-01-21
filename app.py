import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V40", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL: MENÚ BLANCO / BARRA NEGRA ---
st.markdown("""
<style>
    /* 1. Fondo Principal BLANCO */
    .stApp {
        background-color: #FFFFFF;
        color: #000000;
    }
    
    /* 2. Barra Lateral NEGRA */
    section[data-testid="stSidebar"] {
        background-color: #111111;
    }
    /* Texto de la barra lateral BLANCO */
    section[data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    
    /* 3. Botones del Menú Principal (Grandes) */
    .big-button {
        width: 100%;
        padding: 40px;
        font-size: 24px;
        font-weight: bold;
        border-radius: 15px;
        border: 2px solid #ccc;
        background-color: #f8f9fa;
        color: black;
        text-align: center;
        cursor: pointer;
        margin-bottom: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .big-button:hover {
        background-color: #e2e6ea;
        border-color: #adb5bd;
    }

    /* 4. Ajustes de Inputs (Cajas de texto oscuras sobre blanco) */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        color: #000000 !important;
        background-color: #F0F2F6 !important;
        border-radius: 5px;
    }
    
    /* 5. Botón ROJO de acción */
    div.stButton > button {
        background-color: #D32F2F;
        color: white;
        font-weight: bold;
        border: none;
        width: 100%;
        padding: 10px;
    }
    div.stButton > button:hover {
        background-color: #B71C1C;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- GESTIÓN DE SESIÓN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if 'seccion_actual' not in st.session_state: st.session_state['seccion_actual'] = "Inicio" # Para el menú pantalla completa

# --- LOGIN ---
if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    with st.form("login_v40"):
        pin = st.text_input("INTRODUCE PIN:", type="password")
        if st.form_submit_button("ENTRAR"):
            if pin == "1234": 
                st.session_state['autenticado'] = True
                st.rerun()
            else: 
                st.error("🚫 Incorrecto")
    st.stop()

# --- CONEXIÓN ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except: return None

# --- LÓGICA DE DATOS ---
def forzar_numero_real(valor):
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    try:
        str_val = str(valor).replace("€", "").replace(",", ".").strip()
        v = float(str_val)
        if v > 1000: v = v / 100
        elif v > 150: v = v / 10
        return float(v)
    except: return 0.0

def arreglar_talla(valor):
    v = str(valor).replace(".0", "").replace(",", ".").strip()
    if len(v) == 3 and v.endswith("5") and "." not in v: return f"{v[:2]}.{v[2]}"
    if v == "nan": return ""
    return v

# --- CARGAR DATOS (SIN CONVERTIR A TEXTO PARA QUE ORDENE BIEN) ---
@st.cache_data(ttl=5, show_spinner=False)
def cargar_datos_cacheado():
    cols = ["ID", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", 
            "Estado", "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Fecha Compra", "Fecha Venta", "ROI %"]
    sheet = conectar_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                for c in cols: 
                    if c not in df.columns: df[c] = ""
                
                # NÚMEROS REALES (Floats) -> Esto permite ordenar de menor a mayor
                df['Precio Compra'] = df['Precio Compra'].apply(forzar_numero_real)
                df['Precio Venta'] = df['Precio Venta'].apply(forzar_numero_real)
                df['Ganancia Neta'] = df['Precio Venta'] - df['Precio Compra']
                df.loc[df['Estado'] == 'En Stock', 'Ganancia Neta'] = 0.0
                
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Talla'] = df['Talla'].apply(arreglar_talla)
                
                # FECHAS REALES (Datetime) -> Esto permite ordenar por calendario
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
        # Guardamos en formato "14,50" para que el Excel quede bonito
        for col in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
            dfs[col] = dfs[col].apply(lambda x: f"{float(x):.2f}".replace(".", ",") if isinstance(x, (int, float)) else "0,00")
            
        dfs['Fecha Compra'] = pd.to_datetime(dfs['Fecha Compra']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs['Fecha Venta'] = pd.to_datetime(dfs['Fecha Venta']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        st.cache_data.clear()

# --- LISTAS ---
def obtener_listas(df):
    m = sorted(list(set(BASES_MARCAS + (df['Marca'].unique().tolist() if not df.empty else []))))
    t = sorted(list(set(BASES_TIENDAS + (df['Tienda Origen'].unique().tolist() if not df.empty else []))))
    return [x for x in m if str(x).strip() not in ["","nan"]], [x for x in t if str(x).strip() not in ["","nan"]]

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================

# 1. BARRA LATERAL (SIEMPRE VISIBLE PARA VOLVER AL MENÚ)
st.sidebar.title("Navegación")
if st.sidebar.button("🏠 MENÚ PRINCIPAL", type="primary"):
    st.session_state['seccion_actual'] = "Inicio"
    st.rerun()

st.sidebar.divider()
st.sidebar.write(f"Estás en: **{st.session_state['seccion_actual']}**")
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): 
    st.session_state['autenticado']=False
    st.rerun()

df = cargar_datos_cacheado()
list_m, list_t = obtener_listas(df)

# ==========================================
# 2. PANTALLA DE INICIO (MENÚ GIGANTE)
# ==========================================
if st.session_state['seccion_actual'] == "Inicio":
    st.title("👟 Vinchy Zapas")
    st.write("Selecciona una opción:")
    st.write("") # Espacio
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Usamos botones normales de Streamlit pero ocupan ancho completo
        if st.button("➕ NUEVA COMPRA", use_container_width=True):
            st.session_state['seccion_actual'] = "Nuevo"
            st.rerun()
            
        st.write("") # Espacio
        
        if st.button("📋 HISTORIAL", use_container_width=True):
            st.session_state['seccion_actual'] = "Historial"
            st.rerun()

    with col2:
        if st.button("💸 VENDER", use_container_width=True):
            st.session_state['seccion_actual'] = "Vender"
            st.rerun()
            
        st.write("") # Espacio
        
        if st.button("📊 FINANZAS", use_container_width=True):
            st.session_state['seccion_actual'] = "Finanzas"
            st.rerun()

# ==========================================
# SECCIÓN: NUEVO
# ==========================================
elif st.session_state['seccion_actual'] == "Nuevo":
    st.title("➕ Nueva Compra")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    with st.form("form_nuevo_v40"):
        c1, c2 = st.columns([1, 2])
        ms = c1.selectbox("Marca", ["-"] + list_m, key="m_v40"); mt = c1.text_input("¿Nueva?", placeholder="Escribe aquí", key="mt_v40")
        mf = str(mt if mt else ms).strip().title()
        if mf == "-": mf = ""
        mod = c2.text_input("Modelo", key="mod_v40")
        
        c3, c4, c5 = st.columns(3)
        ts = c3.selectbox("Tienda", ["-"] + list_t, key="t_v40"); tt = c3.text_input("¿Nueva?", placeholder="Escribe aquí", key="tt_v40")
        tf = str(tt if tt else ts).strip().title()
        if tf == "-": tf = ""
        ta = c4.text_input("Talla", key="ta_v40")
        pr_txt = c5.text_input("Precio Compra (€)", placeholder="Ej: 45,50", key="pr_v40")
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca o Modelo")
            else:
                try: p = float(str(pr_txt).replace(",", "."))
                except: p = 0.0
                p = forzar_numero_real(p)
                nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":arreglar_talla(ta), "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df); st.session_state['ok']=True; st.rerun()

# ==========================================
# SECCIÓN: VENDER
# ==========================================
elif st.session_state['seccion_actual'] == "Vender":
    st.title("💸 Registrar Venta")
    dfs = df[df['Estado']=='En Stock'].copy()
    opcs = ["-"] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist()
    sel = st.selectbox("Buscar zapatilla:", opcs, key="sel_ven_v40")
    
    if sel != "-":
        ids = int(sel.split(" |")[0].replace("ID:",""))
        row = df[df['ID']==ids].iloc[0]
        st.info(f"VENDIENDO: {row['Marca']} {row['Modelo']}")
        with st.form("form_vender_v40"):
            pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50", key="pv_v40")
            c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"], key="pl_v40"); cta=c4.text_input("Cuenta Venta", key="cta_v40")
            if st.form_submit_button("CONFIRMAR VENTA"):
                try: pv = float(str(pv_txt).replace(",", "."))
                except: pv = 0.0
                idx = df.index[df['ID']==ids][0]
                g = pv - row['Precio Compra']
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g
                guardar_datos(df); st.balloons(); st.success("Vendido"); st.rerun()

# ==========================================
# SECCIÓN: HISTORIAL
# ==========================================
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial Global")
    
    # Buscador
    busqueda = st.text_input("🔍 Filtrar:", placeholder="Escribe marca, modelo...", key="search_v40")
    df_ver = df.copy()
    if busqueda:
        mask = df_ver.astype(str).apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1)
        df_ver = df_ver[mask]

    # CONFIGURACIÓN DE ORDENACIÓN Y FORMATO
    col_config = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "Marca": st.column_config.TextColumn(width="medium"),
        "Modelo": st.column_config.TextColumn(width="large"),
        # Los precios se ordenan bien porque internamente son números, aunque se muestren con €
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"), 
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }
    
    st.caption("👆 Pulsa en los títulos (Marca, Precio, Fecha...) para ORDENAR.")
    
    df_editado = st.data_editor(
        df_ver, 
        column_config=col_config, 
        hide_index=True, 
        use_container_width=True,
        num_rows="dynamic",
        key="editor_v40"
    )

    if not df.equals(df_editado):
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
        df_editado['Talla'] = df_editado['Talla'].apply(arreglar_talla)
        df.update(df_editado)
        guardar_datos(df)
        st.toast("✅ Cambios guardados")

# ==========================================
# SECCIÓN: FINANZAS
# ==========================================
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Panel Financiero")
    
    # BOTONES DE EXPORTACIÓN
    col_ex1, col_ex2 = st.columns(2)
    csv_stock = df[df['Estado']=='En Stock'].to_csv(index=False).encode('utf-8-sig')
    col_ex1.download_button("📥 Descargar STOCK", csv_stock, "stock.csv", "text/csv")
    
    csv_ventas = df[df['Estado']=='Vendido'].to_csv(index=False).encode('utf-8-sig')
    col_ex2.download_button("💰 Descargar VENTAS", csv_ventas, "ventas.csv", "text/csv")
    
    st.divider()
    
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        ben = sold['Ganancia Neta'].sum()
        gst = df[df['Estado']=='En Stock']['Precio Compra'].sum()
        
        k1.metric("Beneficio Neto Total", f"{ben:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        k2.metric("Dinero en Stock", f"{gst:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
