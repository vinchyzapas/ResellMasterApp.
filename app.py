import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px # GRÁFICOS

# ==========================================
# 🔗 CONFIGURACIÓN
# ==========================================
LINK_APP = "https://vinchy-zapas.streamlit.app"
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2589/2589903.png"

st.set_page_config(page_title="Vinchy Zapas V73", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL ---
st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #000000;}
    section[data-testid="stSidebar"] {background-color: #111111;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    .stTextInput input, .stSelectbox div {
        color: #000000 !important; background-color: #F0F2F6 !important; border: 1px solid #ccc;
    }
    /* BOTONES */
    div.stButton > button {
        background-color: #D32F2F; color: white; font-weight: bold; border: none; width: 100%; padding: 12px;
    }
    /* ENLACES */
    a {color: #0000EE !important; font-weight: bold;}
    /* MÉTRICAS */
    div[data-testid="stMetricValue"] {font-size: 22px !important; color: #2E7D32 !important;}
</style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if 'seccion_actual' not in st.session_state: st.session_state['seccion_actual'] = "Inicio"

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.image(LOGO_URL, width=80)
    with st.form("login_v73"):
        pin = st.text_input("PIN:", type="password")
        if st.form_submit_button("ENTRAR AL SISTEMA"):
            if pin == "1234": st.session_state['autenticado'] = True; st.rerun()
            else: st.error("🚫 PIN Incorrecto")
    st.stop()

# --- 🧠 LÓGICA DE TEXTO PURO ---
def texto_a_float(valor):
    """Convierte '45,50' a 45.50 para calcular"""
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    try:
        limpio = str(valor).replace("€", "").strip()
        if "." in limpio and "," in limpio: limpio = limpio.replace(".", "")
        limpio = limpio.replace(",", ".")
        return float(limpio)
    except: return 0.0

def float_a_texto(numero):
    """Convierte 45.50 a '45,50' para mostrar"""
    try:
        return f"{float(numero):.2f}".replace(".", ",")
    except: return "0,00"

def arreglar_talla(valor):
    v = str(valor).replace(".0", "").replace(",", ".").strip()
    if v == "nan": return ""
    return v

# --- 🧱 ALMACENAMIENTO ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except: return None

@st.cache_data(ttl=0, show_spinner=False)
def cargar_datos_texto():
    sheet = conectar_sheets()
    if not sheet: return pd.DataFrame()
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        cols = ["ID", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", 
                "Estado", "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Fecha Compra", "Fecha Venta", "ROI %", "Tracking"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
        
        # TODO STRING
        df = df.astype(str).replace("nan", "")
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        
        # Enlace Web
        df['🌐 Web'] = "https://www.google.com/search?q=" + df['Marca'] + "+" + df['Modelo'] + "+precio"
        return df
    except: return pd.DataFrame()

def guardar_datos_texto(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        if '🌐 Web' in dfs.columns: dfs = dfs.drop(columns=['🌐 Web'])
        dfs = dfs.astype(str).replace("nan", "")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        st.cache_data.clear()

def obtener_listas(df):
    BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
    BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]
    m = df['Marca'].unique().tolist() if not df.empty else []
    t = df['Tienda Origen'].unique().tolist() if not df.empty else []
    return sorted(list(set(BASES_MARCAS + m))), sorted(list(set(BASES_TIENDAS + t)))

# ==========================================
# 🖥️ INTERFAZ
# ==========================================
st.sidebar.image(LOGO_URL, width=100)
st.sidebar.markdown("<h3 style='color: white; text-align: center;'>VINCHY ZAPAS</h3>", unsafe_allow_html=True)

st.sidebar.title("Navegación")
if st.sidebar.button("🏠 MENÚ PRINCIPAL", type="primary"):
    st.session_state['seccion_actual'] = "Inicio"
    st.rerun()
st.sidebar.divider()

if st.sidebar.button("🔒 Cerrar Sesión"): 
    st.session_state['autenticado']=False
    st.rerun()

df = cargar_datos_texto()
list_m, list_t = obtener_listas(df)

# --- INICIO ---
if st.session_state['seccion_actual'] == "Inicio":
    st.title("👟 Panel de Control")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ NUEVA COMPRA", use_container_width=True): st.session_state['seccion_actual'] = "Nuevo"; st.rerun()
        st.write("")
        if st.button("📋 HISTORIAL", use_container_width=True): st.session_state['seccion_actual'] = "Historial"; st.rerun()
    with c2:
        if st.button("💸 VENDER", use_container_width=True): st.session_state['seccion_actual'] = "Vender"; st.rerun()
        st.write("")
        if st.button("📊 FINANZAS", use_container_width=True): st.session_state['seccion_actual'] = "Finanzas"; st.rerun()

# --- NUEVO ---
elif st.session_state['seccion_actual'] == "Nuevo":
    st.title("➕ Nueva Compra")
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
                p_float = texto_a_float(pr)
                p_str = float_a_texto(p_float)
                nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now().strftime("%d/%m/%Y"), "Fecha Venta":"", "Marca":mf, "Modelo":mod, "Talla":arreglar_talla(ta), "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p_str, "Precio Venta":"0,00", "Estado":"En Stock", "Ganancia Neta":"0,00", "ROI %":"0,00", "Tracking":""}
                new_df = pd.DataFrame([new]).astype(str)
                df_final = pd.concat([df, new_df], ignore_index=True)
                guardar_datos_texto(df_final)
                st.success(f"Guardado: {p_str} €"); time.sleep(1); st.rerun()

# --- VENDER ---
elif st.session_state['seccion_actual'] == "Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    opcs = ["-"] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist()
    sel = st.selectbox("Buscar zapatilla:", opcs)
    
    if sel != "-":
        ids = int(sel.split(" |")[0].replace("ID:",""))
        row = df[df['ID']==ids].iloc[0]
        st.markdown(f"### {row['Marca']} {row['Modelo']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Talla", row['Talla']); c2.metric("Tienda", row['Tienda Origen']); c3.metric("Coste", f"{row['Precio Compra']} €")
        st.divider()
        
        pv_txt = st.text_input("Precio Venta (€)", placeholder="100,50")
        pv_float = texto_a_float(pv_txt)
        pc_float = texto_a_float(row['Precio Compra'])
        gan = pv_float - pc_float
        
        if pv_float > 0: st.markdown(f"#### 💰 Ganancia: <span style='color:{'green' if gan>0 else 'red'}'>{gan:.2f} €</span>", unsafe_allow_html=True)
        
        with st.form("fv"):
            c3,c4 = st.columns(2); pl = c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","En Persona","Otro"]); cu = c4.text_input("Cuenta")
            tr = st.text_input("🚚 Nº Seguimiento (Opcional)")
            if st.form_submit_button("CONFIRMAR"):
                idx = df.index[df['ID']==ids][0]
                df.at[idx,'Estado'] = 'Vendido'
                df.at[idx,'Fecha Venta'] = datetime.now().strftime("%d/%m/%Y")
                df.at[idx,'Precio Venta'] = float_a_texto(pv_float)
                df.at[idx,'Plataforma Venta'] = pl
                df.at[idx,'Cuenta Venta'] = cu
                df.at[idx,'Ganancia Neta'] = float_a_texto(gan)
                df.at[idx,'Tracking'] = tr
                guardar_datos_texto(df)
                st.balloons(); st.success(f"¡Vendido! +{gan:.2f}€"); time.sleep(1); st.rerun()

# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial (TEXTO)")
    st.info("💡 Edita y pulsa 'GUARDAR CAMBIOS'. Lo que escribas se guardará TAL CUAL.")
    bus = st.text_input("🔍 Filtrar:", placeholder="Escribe...")
    df_v = df.copy()
    if bus: mask = df_v.astype(str).apply(lambda row: row.str.contains(bus, case=False).any(), axis=1); df_v = df_v[mask]

    cols_ord = ["ID", "🌐 Web", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", "Estado", "Tracking", "Fecha Compra", "Fecha Venta"]
    col_cfg = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "🌐 Web": st.column_config.LinkColumn(display_text="🔎 Buscar"),
        "Precio Compra": st.column_config.TextColumn(),
        "Precio Venta": st.column_config.TextColumn(),
        "Ganancia Neta": st.column_config.TextColumn(disabled=True),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }
    df_ed = st.data_editor(df_v[[c for c in cols_ord if c in df_v.columns]], column_config=col_cfg, hide_index=True, use_container_width=True, key="ev73")

    if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary"):
        for i, row in df_ed.iterrows():
            real_idx = df.index[df['ID'] == row['ID']].tolist()
            if real_idx:
                idx = real_idx[0]
                pc = texto_a_float(row['Precio Compra'])
                pv = texto_a_float(row['Precio Venta'])
                
                for col in df.columns:
                    if col in row: df.at[idx, col] = row[col]
                
                df.at[idx, 'Ganancia Neta'] = float_a_texto(pv - pc)

        guardar_datos_texto(df)
        st.success("✅ Datos actualizados"); time.sleep(1); st.rerun()

# --- FINANZAS ---
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Finanzas")
    df_calc = df.copy()
    for c in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
        df_calc[c] = df_calc[c].apply(texto_a_float)
    df_calc['Fecha Compra'] = pd.to_datetime(df_calc['Fecha Compra'], dayfirst=True, errors='coerce')
    df_calc['Fecha Venta'] = pd.to_datetime(df_calc['Fecha Venta'], dayfirst=True, errors='coerce')

    if not df_calc.empty:
        hoy = datetime.now()
        ds = df_calc[df_calc['Estado']=='Vendido']; dk = df_calc[df_calc['Estado']=='En Stock']
        mm_v = (ds['Fecha Venta'].dt.month == hoy.month) & (ds['Fecha Venta'].dt.year == hoy.year)
        
        m1, m2 = st.columns(2)
        ben = ds['Ganancia Neta'].sum()
        ben_mes = ds[mm_v]['Ganancia Neta'].sum()
        
        m1.metric("Beneficio TOTAL", float_a_texto(ben) + " €")
        m2.metric("Beneficio MES", float_a_texto(ben_mes) + " €")
        st.divider()
        if not ds.empty:
            c1, c2 = st.columns(2)
            with c1: 
                fig = px.pie(ds, names='Marca', values='Ganancia Neta', title='Rentabilidad por Marca', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = px.bar(ds.groupby('Plataforma Venta')['Ganancia Neta'].sum().reset_index(), x='Plataforma Venta', y='Ganancia Neta', title='Por Plataforma', color='Plataforma Venta')
                st.plotly_chart(fig2, use_container_width=True)
