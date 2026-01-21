import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V42", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL ---
st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #000000;}
    section[data-testid="stSidebar"] {background-color: #111111;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        color: #000000 !important; background-color: #F0F2F6 !important; border-radius: 5px;
    }
    
    /* BOTÓN ROJO */
    div.stButton > button {
        background-color: #D32F2F; color: white; font-weight: bold; border: none; width: 100%;
        padding: 12px; font-size: 16px;
    }
    
    /* Métricas */
    div[data-testid="stMetricValue"] {font-size: 22px !important; color: #2E7D32 !important;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if 'seccion_actual' not in st.session_state: st.session_state['seccion_actual'] = "Inicio"

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.markdown("### Versión 42")
    with st.form("login_v42"):
        pin = st.text_input("PIN:", type="password")
        if st.form_submit_button("ENTRAR"):
            if pin == "1234": st.session_state['autenticado'] = True; st.rerun()
            else: st.error("Incorrecto")
    st.stop()

# --- CONEXIÓN ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except: return None

# --- HELPERS ---
def forzar_numero(valor):
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    try:
        v = float(str(valor).replace("€", "").replace(",", ".").strip())
        if v > 1000: v = v/100
        elif v > 150: v = v/10
        return float(v)
    except: return 0.0

def arreglar_talla(valor):
    v = str(valor).replace(".0", "").replace(",", ".").strip()
    if len(v) == 3 and v.endswith("5") and "." not in v: return f"{v[:2]}.{v[2]}"
    if v == "nan": return ""
    return v

# --- CARGAR DATOS ---
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
                
                df['Precio Compra'] = df['Precio Compra'].apply(forzar_numero)
                df['Precio Venta'] = df['Precio Venta'].apply(forzar_numero)
                df['Ganancia Neta'] = df['Precio Venta'] - df['Precio Compra']
                df.loc[df['Estado'] == 'En Stock', 'Ganancia Neta'] = 0.0
                
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                for c in ['Marca', 'Modelo', 'Tienda Origen']:
                    df[c] = df[c].astype(str).str.strip().str.title()
                
                df['Talla'] = df['Talla'].apply(arreglar_talla)
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                
                return df[cols]
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        for col in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
            dfs[col] = dfs[col].apply(lambda x: f"{float(x):.2f}".replace(".", ",") if isinstance(x, (int, float)) else "0,00")
        dfs['Fecha Compra'] = pd.to_datetime(dfs['Fecha Compra']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs['Fecha Venta'] = pd.to_datetime(dfs['Fecha Venta']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        st.cache_data.clear()

def obtener_listas(df):
    m = sorted(list(set(BASES_MARCAS + (df['Marca'].unique().tolist() if not df.empty else []))))
    t = sorted(list(set(BASES_TIENDAS + (df['Tienda Origen'].unique().tolist() if not df.empty else []))))
    return [x for x in m if str(x).strip() not in ["","nan"]], [x for x in t if str(x).strip() not in ["","nan"]]

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
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

# --- INICIO ---
if st.session_state['seccion_actual'] == "Inicio":
    st.title("👟 Vinchy Zapas")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ NUEVA", use_container_width=True): st.session_state['seccion_actual'] = "Nuevo"; st.rerun()
        st.write("")
        if st.button("📋 HISTORIAL", use_container_width=True): st.session_state['seccion_actual'] = "Historial"; st.rerun()
    with c2:
        if st.button("💸 VENDER", use_container_width=True): st.session_state['seccion_actual'] = "Vender"; st.rerun()
        st.write("")
        if st.button("📊 FINANZAS", use_container_width=True): st.session_state['seccion_actual'] = "Finanzas"; st.rerun()

# --- NUEVO ---
elif st.session_state['seccion_actual'] == "Nuevo":
    st.title("➕ Nueva")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False
    with st.form("f_new"):
        c1, c2 = st.columns([1, 2])
        ms = c1.selectbox("Marca", ["-"] + list_m); mt = c1.text_input("¿Nueva?", key="kmt")
        mf = str(mt if mt else ms).strip().title()
        if mf == "-": mf = ""
        mod = c2.text_input("Modelo")
        c3, c4, c5 = st.columns(3)
        ts = c3.selectbox("Tienda", ["-"] + list_t); tt = c3.text_input("¿Nueva?", key="ktt")
        tf = str(tt if tt else ts).strip().title()
        if tf == "-": tf = ""
        ta = c4.text_input("Talla"); pr = c5.text_input("Precio Compra (€)", placeholder="45,50")
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca/Modelo")
            else:
                p = forzar_numero(pr); nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":arreglar_talla(ta), "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df); st.session_state['ok']=True; st.rerun()

# --- VENDER ---
elif st.session_state['seccion_actual'] == "Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    opcs = ["-"] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist()
    sel = st.selectbox("Buscar zapatilla:", opcs)
    if sel != "-":
        ids = int(sel.split(" |")[0].replace("ID:",""))
        row = df[df['ID']==ids].iloc[0]
        st.info(f"VENDIENDO: {row['Marca']} {row['Modelo']}")
        with st.form("f_ven"):
            pv = st.text_input("Precio Venta (€)", placeholder="100,50")
            c3,c4=st.columns(2); pl=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cu=c4.text_input("Cuenta")
            if st.form_submit_button("CONFIRMAR VENTA"):
                prio = forzar_numero(pv); idx = df.index[df['ID']==ids][0]
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=prio; df.at[idx,'Plataforma Venta']=pl; df.at[idx,'Cuenta Venta']=cu; df.at[idx,'Ganancia Neta']=prio-row['Precio Compra']
                guardar_datos(df); st.balloons(); st.success("Vendido"); st.rerun()

# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial Global")
    
    # 1. BUSCADOR
    busqueda = st.text_input("🔍 Filtrar (Marca, Modelo, ID...):", placeholder="Escribe para filtrar...")
    
    # 2. ORDENACIÓN MANUAL (SOLUCIÓN INFALIBLE)
    col_sort1, col_sort2 = st.columns(2)
    criterio_orden = col_sort1.selectbox("🔃 Ordenar por:", ["Fecha Compra (Más reciente)", "Fecha Compra (Más antigua)", "Marca (A-Z)", "Precio Compra (Menor a Mayor)", "Precio Compra (Mayor a Menor)", "Estado"])
    
    df_ver = df.copy()
    
    # APLICAR ORDEN
    if criterio_orden == "Fecha Compra (Más reciente)":
        df_ver = df_ver.sort_values(by="Fecha Compra", ascending=False)
    elif criterio_orden == "Fecha Compra (Más antigua)":
        df_ver = df_ver.sort_values(by="Fecha Compra", ascending=True)
    elif criterio_orden == "Marca (A-Z)":
        df_ver = df_ver.sort_values(by="Marca", ascending=True)
    elif criterio_orden == "Precio Compra (Menor a Mayor)":
        df_ver = df_ver.sort_values(by="Precio Compra", ascending=True)
    elif criterio_orden == "Precio Compra (Mayor a Menor)":
        df_ver = df_ver.sort_values(by="Precio Compra", ascending=False)
    elif criterio_orden == "Estado":
        df_ver = df_ver.sort_values(by="Estado", ascending=True)

    # APLICAR FILTRO
    if busqueda:
        mask = df_ver.astype(str).apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1)
        df_ver = df_ver[mask]

    col_config = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "Marca": st.column_config.TextColumn(width="medium"),
        "Modelo": st.column_config.TextColumn(width="large"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }
    
    df_editado = st.data_editor(df_ver, column_config=col_config, hide_index=True, use_container_width=True, num_rows="dynamic", key="ed_v42")
    if not df.equals(df_editado):
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
        df_editado['Talla'] = df_editado['Talla'].apply(arreglar_talla)
        df.update(df_editado); guardar_datos(df); st.toast("✅ Cambios guardados")

# --- FINANZAS PRO ---
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Panel Financiero")
    
    c_ex1, c_ex2 = st.columns(2)
    c_ex1.download_button("📥 Descargar STOCK CSV", df[df['Estado']=='En Stock'].to_csv(index=False).encode('utf-8-sig'), "stock.csv", "text/csv")
    c_ex2.download_button("💰 Descargar VENTAS CSV", df[df['Estado']=='Vendido'].to_csv(index=False).encode('utf-8-sig'), "ventas.csv", "text/csv")
    st.divider()

    if not df.empty:
        hoy = datetime.now()
        df_sold = df[df['Estado'] == 'Vendido']
        df_stock = df[df['Estado'] == 'En Stock']
        
        # Filtros
        mask_compras_mes = (df['Fecha Compra'].dt.month == hoy.month) & (df['Fecha Compra'].dt.year == hoy.year)
        mask_ventas_mes = (df_sold['Fecha Venta'].dt.month == hoy.month) & (df_sold['Fecha Venta'].dt.year == hoy.year)
        
        # Cálculos
        total_beneficio = df_sold['Ganancia Neta'].sum()
        total_gasto_stock = df_stock['Precio Compra'].sum()
        cantidad_stock = len(df_stock) # NUEVO: CUENTA LOS PARES
        
        total_ventas_num = len(df_sold)
        total_compras_num = len(df)
        
        mes_beneficio = df_sold[mask_ventas_mes]['Ganancia Neta'].sum()
        mes_gasto_compras = df[mask_compras_mes]['Precio Compra'].sum()
        mes_ventas_num = len(df_sold[mask_ventas_mes])
        mes_compras_num = len(df[mask_compras_mes])

        # Visuales
        st.subheader(f"📅 Resumen {hoy.strftime('%B %Y')}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Beneficio Mes", f"{mes_beneficio:,.2f} €")
        m2.metric("Gasto Mes", f"{mes_gasto_compras:,.2f} €")
        m3.metric("Ventas (Uds.)", mes_ventas_num)
        m4.metric("Compras (Uds.)", mes_compras_num)
        
        st.divider()
        st.subheader("🌍 Resumen Global")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Beneficio TOTAL", f"{total_beneficio:,.2f} €")
        # MÉTRICAS DE STOCK SEPARADAS
        g2.metric("Dinero en Stock", f"{total_gasto_stock:,.2f} €")
        g3.metric("Pares en Stock", f"{cantidad_stock} pares") 
        g4.metric("Total Vendidos", total_ventas_num)
