import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🔗 TU ENLACE CONFIGURADO
# ==========================================
LINK_APP = "https://vinchy-zapas.streamlit.app"
# ==========================================

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL ---
st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #000000;}
    section[data-testid="stSidebar"] {background-color: #111111;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        color: #000000 !important; background-color: #F0F2F6 !important; border: 1px solid #ccc;
    }
    div.stButton > button {
        background-color: #D32F2F; color: white; font-weight: bold; border: none; width: 100%;
        padding: 12px; font-size: 16px;
    }
    a {color: #0000EE !important; font-weight: bold;}
    code {color: #000000 !important; background-color: #f0f0f0 !important; font-weight: bold; font-size: 14px;}
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
    with st.form("login_final"):
        pin = st.text_input("PIN:", type="password")
        if st.form_submit_button("ENTRAR AL SISTEMA"):
            if pin == "1234": st.session_state['autenticado'] = True; st.rerun()
            else: st.error("🚫 PIN Incorrecto")
    st.stop()

# --- CONEXIÓN ---
def obtener_libro_google():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas")
    except: return None

# --- GESTIÓN DATOS ---
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

@st.cache_data(ttl=5, show_spinner=False)
def cargar_datos_zapas():
    libro = obtener_libro_google()
    if not libro: return pd.DataFrame()
    try:
        sheet = libro.sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        cols = ["ID", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", 
                "Estado", "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Fecha Compra", "Fecha Venta", "ROI %", "Tracking"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
            
        for c in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
            df[c] = df[c].apply(forzar_numero)

        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        df['Talla'] = df['Talla'].apply(arreglar_talla)
        df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
        df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
        
        # Enlace Web visible
        df['🌐 Web'] = "https://www.google.com/search?q=" + df['Marca'].astype(str) + "+" + df['Modelo'].astype(str) + "+precio"
        
        return df
    except: return pd.DataFrame()

def guardar_datos_zapas(df):
    libro = obtener_libro_google()
    if libro:
        sheet = libro.sheet1
        dfs = df.copy()
        if '🌐 Web' in dfs.columns: dfs = dfs.drop(columns=['🌐 Web'])
        if 'T_Num' in dfs.columns: dfs = dfs.drop(columns=['T_Num'])
        
        for col in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
            dfs[col] = dfs[col].apply(lambda x: f"{float(x):.2f}".replace(".", ",") if isinstance(x, (int, float)) else "0,00")
        dfs['Fecha Compra'] = pd.to_datetime(dfs['Fecha Compra']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs['Fecha Venta'] = pd.to_datetime(dfs['Fecha Venta']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())
        st.cache_data.clear()

def cargar_trackings():
    libro = obtener_libro_google()
    if not libro: return pd.DataFrame(columns=["Alias", "Tracking", "Fecha"])
    try: sheet = libro.worksheet("trackings")
    except: 
        sheet = libro.add_worksheet(title="trackings", rows=100, cols=3)
        sheet.append_row(["Alias", "Tracking", "Fecha"])
    return pd.DataFrame(sheet.get_all_records())

def guardar_tracking_nuevo(alias, codigo):
    libro = obtener_libro_google()
    if libro:
        try: sheet = libro.worksheet("trackings")
        except: sheet = libro.add_worksheet("trackings", 100, 3)
        sheet.append_row([alias, codigo, datetime.now().strftime("%d/%m/%Y")])

def borrar_tracking(codigo):
    libro = obtener_libro_google()
    if libro:
        sheet = libro.worksheet("trackings")
        df = pd.DataFrame(sheet.get_all_records())
        df_new = df[df['Tracking'].astype(str) != str(codigo)]
        sheet.clear()
        sheet.update([df_new.columns.values.tolist()] + df_new.values.tolist())

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

# --- COMPARTIR ---
with st.sidebar.expander("📲 COMPARTIR APP"):
    st.write("**Tu enlace:**")
    st.code(LINK_APP)
    st.write("**Escanea:**")
    # Genera QR con TU enlace
    st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP}")

st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos_zapas()
list_m, list_t = obtener_listas(df)

# --- INICIO ---
if st.session_state['seccion_actual'] == "Inicio":
    st.title("👟 Vinchy Zapas")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ NUEVA COMPRA", use_container_width=True): st.session_state['seccion_actual'] = "Nuevo"; st.rerun()
        st.write("")
        if st.button("📋 HISTORIAL", use_container_width=True): st.session_state['seccion_actual'] = "Historial"; st.rerun()
        st.write("")
        if st.button("🚚 ENVÍOS", use_container_width=True): st.session_state['seccion_actual'] = "Trackings"; st.rerun()
    with c2:
        if st.button("💸 VENDER", use_container_width=True): st.session_state['seccion_actual'] = "Vender"; st.rerun()
        st.write("")
        if st.button("📊 FINANZAS", use_container_width=True): st.session_state['seccion_actual'] = "Finanzas"; st.rerun()

# --- TRACKINGS ---
elif st.session_state['seccion_actual'] == "Trackings":
    st.title("🚚 Paquetes en Camino")
    if "t_alias" not in st.session_state: st.session_state.t_alias = ""
    if "t_code" not in st.session_state: st.session_state.t_code = ""
    with st.form("form_track"):
        c1, c2 = st.columns(2)
        alias = c1.text_input("Alias / Tienda", key="t_alias", placeholder="Ej: Pedido Nike")
        track_num = c2.text_input("Nº Seguimiento", key="t_code")
        if st.form_submit_button("AÑADIR SEGUIMIENTO"):
            if alias and track_num:
                guardar_tracking_nuevo(alias, track_num)
                st.session_state.t_alias = ""; st.session_state.t_code = ""; st.toast("✅ Guardado"); st.rerun()
            else: st.error("Faltan datos")
    st.divider()
    df_t = cargar_trackings()
    if not df_t.empty:
        for i, r in df_t.iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**{r['Alias']}**"); c1.caption(f"{r['Tracking']}")
                c2.link_button("🔎 RASTREAR", f"https://t.17track.net/es#nums={r['Tracking']}")
                if c3.button("🗑️", key=f"d_{i}"): borrar_tracking(r['Tracking']); st.rerun()
                st.divider()
    else: st.info("No hay paquetes pendientes.")

# --- NUEVO ---
elif st.session_state['seccion_actual'] == "Nuevo":
    st.title("➕ Nueva Compra")
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
        ta = c4.text_input("Talla"); pr = c5.text_input("Precio (€)", placeholder="45,50")
        cant = st.number_input("📦 Cantidad", 1, 10, 1)
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca/Modelo")
            else:
                p = forzar_numero(pr); nid = 1 if df.empty else df['ID'].max()+1
                nuevas = []
                for i in range(cant):
                    nuevas.append({"ID":nid+i, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":arreglar_talla(ta), "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0, "Tracking":""})
                df = pd.concat([df, pd.DataFrame(nuevas)], ignore_index=True)
                guardar_datos_zapas(df); st.session_state['ok']=True; st.rerun()

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
        c1.metric("Talla", row['Talla']); c2.metric("Tienda", row['Tienda Origen']); c3.metric("Coste", f"{row['Precio Compra']:.2f}€".replace(".", ","))
        st.divider()
        pv_txt = st.text_input("Precio Venta (€)", placeholder="100,50")
        pv = forzar_numero(pv_txt); gan = pv - row['Precio Compra']
        if pv > 0: st.markdown(f"#### 💰 Ganancia: <span style='color:{'green' if gan>0 else 'red'}'>{gan:.2f} €</span>", unsafe_allow_html=True)
        with st.form("fv"):
            c3,c4 = st.columns(2); pl = c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","En Persona","Otro"]); cu = c4.text_input("Cuenta")
            tr = st.text_input("🚚 Nº Seguimiento Venta (Opcional)")
            if st.form_submit_button("CONFIRMAR"):
                idx=df.index[df['ID']==ids][0]
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=pl; df.at[idx,'Cuenta Venta']=cu; df.at[idx,'Ganancia Neta']=gan; df.at[idx,'Tracking']=tr
                guardar_datos_zapas(df); st.balloons(); st.success(f"¡Vendido! +{gan:.2f}€"); st.rerun()

# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial")
    bus = st.text_input("🔍 Filtrar:", placeholder="Escribe...")
    cri = st.selectbox("🔃 Ordenar:", ["Fecha Compra (Reciente)", "Marca (A-Z)", "Precio (Bajo-Alto)", "Talla (Menor-Mayor)", "Talla (Mayor-Menor)"])
    df_v = df.copy()
    if bus: mask = df_v.astype(str).apply(lambda row: row.str.contains(bus, case=False).any(), axis=1); df_v = df_v[mask]
    
    if "Reciente" in cri: df_v = df_v.sort_values(by="Fecha Compra", ascending=False)
    elif "Marca" in cri: df_v = df_v.sort_values(by="Marca", ascending=True)
    elif "Precio" in cri: df_v = df_v.sort_values(by="Precio Compra", ascending=True)
    elif "Talla" in cri: 
        df_v['T_Num'] = pd.to_numeric(df_v['Talla'], errors='coerce')
        if "Menor-Mayor" in cri: df_v = df_v.sort_values(by="T_Num", ascending=True)
        else: df_v = df_v.sort_values(by="T_Num", ascending=False)

    cols_ord = ["ID", "🌐 Web", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", "Estado", "Tracking", "Fecha Compra", "Fecha Venta"]
    col_cfg = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "🌐 Web": st.column_config.LinkColumn(display_text="🔎 Buscar"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }
    df_ed = st.data_editor(df_v[[c for c in cols_ord if c in df_v.columns]], column_config=col_cfg, hide_index=True, use_container_width=True, num_rows="dynamic", key="ev54")
    if not df.equals(df_ed):
        df_ag = df_ed.drop(columns=['🌐 Web', 'T_Num'], errors='ignore')
        df_ag['Ganancia Neta'] = df_ag['Precio Venta'] - df_ag['Precio Compra']
        df_ag['Talla'] = df_ag['Talla'].apply(arreglar_talla)
        df.update(df_ag); guardar_datos_zapas(df); st.toast("✅ Guardado")

# --- FINANZAS ---
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Panel Financiero")
    c1, c2 = st.columns(2)
    df_x = df.drop(columns=['🌐 Web'], errors='ignore')
    c1.download_button("📥 Stock CSV", df_x[df_x['Estado']=='En Stock'].to_csv(index=False).encode('utf-8-sig'), "stock.csv", "text/csv")
    c2.download_button("💰 Ventas CSV", df_x[df_x['Estado']=='Vendido'].to_csv(index=False).encode('utf-8-sig'), "ventas.csv", "text/csv")
    st.divider()
    if not df.empty:
        hoy = datetime.now()
        ds = df[df['Estado']=='Vendido']; dk = df[df['Estado']=='En Stock']
        mm_v = (ds['Fecha Venta'].dt.month == hoy.month) & (ds['Fecha Venta'].dt.year == hoy.year)
        mm_c = (df['Fecha Compra'].dt.month == hoy.month) & (df['Fecha Compra'].dt.year == hoy.year)
        vm = ds[mm_v].copy()
        best = f"🏆 {vm.loc[vm['Ganancia Neta'].idxmax()]['Modelo']} (+{vm['Ganancia Neta'].max():.2f}€)" if not vm.empty else "-"
        st.subheader(f"📅 {hoy.strftime('%B %Y')}"); st.info(best)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Beneficio", f"{ds[mm_v]['Ganancia Neta'].sum():.2f} €".replace(".", ","))
        m2.metric("Gasto", f"{df[mm_c]['Precio Compra'].sum():.2f} €".replace(".", ","))
        m3.metric("Ventas", len(ds[mm_v])); m4.metric("Compras", len(df[mm_c]))
        st.divider(); st.subheader("🌍 Global")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Total", f"{ds['Ganancia Neta'].sum():.2f} €".replace(".", ","))
        g2.metric("Stock", f"{dk['Precio Compra'].sum():.2f} €".replace(".", ","))
        g3.metric("Pares", len(dk)); g4.metric("Vendidos", len(ds))
