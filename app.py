import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# ==========================================
# 🔗 CONFIGURACIÓN
# ==========================================
LINK_APP = "https://vinchy-zapas.streamlit.app"
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2589/2589903.png"

st.set_page_config(page_title="Vinchy Zapas V76", layout="wide", page_icon="👟")

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
        background-color: #D32F2F; color: white; font-weight: bold; border: none; width: 100%; padding: 12px; font-size: 16px;
    }
    a {color: #0000EE !important; font-weight: bold;}
    div[data-testid="stMetricValue"] {font-size: 22px !important; color: #2E7D32 !important;}
    img {border-radius: 10px; margin-top: 5px;}
    .version-text {font-size: 24px; font-weight: bold; color: #D32F2F; text-align: center; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if 'seccion_actual' not in st.session_state: st.session_state['seccion_actual'] = "Inicio"

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.markdown('<p class="version-text">VERSIÓN 76 (EL CIRUJANO)</p>', unsafe_allow_html=True)
    st.image(LOGO_URL, width=80)
    with st.form("login_v76"):
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

# --- LÓGICA DE TEXTO A NÚMERO ---
def texto_a_float(valor):
    """Convierte '30,50' (texto) a 30.5 (número) para calcular"""
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    try:
        # Quitamos € y puntos de miles
        limpio = str(valor).replace("€", "").replace(".", "").strip()
        # Coma a punto
        limpio = limpio.replace(",", ".")
        return float(limpio)
    except: return 0.0

def float_a_texto(numero):
    """Convierte 30.5 (número) a '30,50' (texto) para guardar"""
    try:
        return f"{float(numero):.2f}".replace(".", ",")
    except: return "0,00"

def arreglar_talla(valor):
    v = str(valor).replace(".0", "").replace(",", ".").strip()
    if len(v) == 3 and v.endswith("5") and "." not in v: return f"{v[:2]}.{v[2]}"
    if v == "nan": return ""
    return v

# --- FUNCIÓN CIRUJANO (CORRIGE PRECIOS LOCOS) ---
def corregir_precio_loco(valor):
    """Si el precio es > 200, lo divide entre 100. Si no, lo deja igual."""
    num = texto_a_float(valor)
    if num > 200: # Asumimos que 2000 es 20.00
        num = num / 100
    return float_a_texto(num)

# --- CARGAR DATOS ---
@st.cache_data(ttl=0, show_spinner=False)
def cargar_datos_texto():
    sheet = obtener_libro_google()
    if not sheet: return pd.DataFrame()
    try:
        data = sheet.sheet1.get_all_records()
        df = pd.DataFrame(data)
        cols = ["ID", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", 
                "Estado", "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Fecha Compra", "Fecha Venta", "ROI %", "Tracking"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
            
        # Todo a String para control total
        df = df.astype(str).replace("nan", "")
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        
        # Enlace Web
        df['🌐 Web'] = "https://www.google.com/search?q=" + df['Marca'] + "+" + df['Modelo'] + "+precio"
        return df
    except: return pd.DataFrame()

def guardar_datos_texto(df):
    sheet = obtener_libro_google()
    if sheet:
        dfs = df.copy()
        if '🌐 Web' in dfs.columns: dfs = dfs.drop(columns=['🌐 Web'])
        dfs = dfs.astype(str).replace("nan", "")
        sheet.sheet1.clear()
        sheet.sheet1.update([dfs.columns.values.tolist()] + dfs.values.tolist())
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
st.sidebar.image(LOGO_URL, width=100)
st.sidebar.markdown("<h3 style='color: white; text-align: center;'>VINCHY ZAPAS</h3>", unsafe_allow_html=True)

st.sidebar.title("Navegación")
if st.sidebar.button("🏠 MENÚ PRINCIPAL", type="primary"):
    st.session_state['seccion_actual'] = "Inicio"
    st.rerun()
st.sidebar.divider()

with st.sidebar.expander("📲 COMPARTIR APP"):
    st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP}")

st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

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
        ta = c4.text_input("Talla"); pr = c5.text_input("Precio Compra (€)", placeholder="45,50")
        cant = st.number_input("📦 Cantidad", 1, 10, 1)
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca/Modelo")
            else:
                p_float = texto_a_float(pr)
                p_str = float_a_texto(p_float)
                nid = 1 if df.empty else df['ID'].max()+1
                nuevas = []
                for i in range(cant):
                    nuevas.append({"ID":nid+i, "Fecha Compra":datetime.now().strftime("%d/%m/%Y"), "Fecha Venta":"", "Marca":mf, "Modelo":mod, "Talla":arreglar_talla(ta), "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p_str, "Precio Venta":"0,00", "Estado":"En Stock", "Ganancia Neta":"0,00", "ROI %":"0,00", "Tracking":""})
                df = pd.concat([df, pd.DataFrame(nuevas)], ignore_index=True)
                guardar_datos_texto(df); st.session_state['ok']=True; st.rerun()

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
            tr = st.text_input("🚚 Nº Seguimiento Venta (Opcional)")
            if st.form_submit_button("CONFIRMAR"):
                idx=df.index[df['ID']==ids][0]
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now().strftime("%d/%m/%Y"); df.at[idx,'Precio Venta']=float_a_texto(pv_float); df.at[idx,'Plataforma Venta']=pl; df.at[idx,'Cuenta Venta']=cu; df.at[idx,'Ganancia Neta']=float_a_texto(gan); df.at[idx,'Tracking']=tr
                guardar_datos_texto(df); st.balloons(); st.success(f"¡Vendido! +{gan:.2f}€"); st.rerun()

# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial (TEXTO)")
    
    # === BOTÓN DE CIRUJANO (Arreglar precios locos) ===
    with st.expander("🔧 HERRAMIENTAS DE REPARACIÓN (Usar si los precios están mal)"):
        st.warning("Pulsa este botón SOLO si ves precios tipo '3000' en lugar de '30'. Dividirá todo lo mayor de 200 entre 100.")
        if st.button("🚑 ARREGLAR PRECIOS AHORA", type="primary"):
            count = 0
            for i, row in df.iterrows():
                # Corregir Compra
                pc = texto_a_float(row['Precio Compra'])
                if pc > 200: 
                    df.at[i, 'Precio Compra'] = float_a_texto(pc / 100)
                    count += 1
                
                # Corregir Venta
                pv = texto_a_float(row['Precio Venta'])
                if pv > 200:
                    df.at[i, 'Precio Venta'] = float_a_texto(pv / 100)
                    count += 1
                
                # Recalcular Ganancia
                nc = texto_a_float(df.at[i, 'Precio Compra'])
                nv = texto_a_float(df.at[i, 'Precio Venta'])
                
                if row['Estado'] == 'Vendido':
                    df.at[i, 'Ganancia Neta'] = float_a_texto(nv - nc)
                else:
                    df.at[i, 'Ganancia Neta'] = "0,00"
            
            guardar_datos_texto(df)
            st.success(f"✅ ¡Reparado! Se han corregido {count} valores.")
            time.sleep(2)
            st.rerun()
    # ==================================================
    
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
    df_ed = st.data_editor(df_v[[c for c in cols_ord if c in df_v.columns]], column_config=col_cfg, hide_index=True, use_container_width=True, key="ev76")

    if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary"):
        for i, row in df_ed.iterrows():
            real_idx = df.index[df['ID'] == row['ID']].tolist()
            if real_idx:
                idx = real_idx[0]
                pc = texto_a_float(row['Precio Compra'])
                pv = texto_a_float(row['Precio Venta'])
                
                for col in df.columns:
                    if col in row: df.at[idx, col] = row[col]
                
                # RECALCULAR GANANCIA AL GUARDAR
                if row['Estado'] == 'Vendido':
                    df.at[idx, 'Ganancia Neta'] = float_a_texto(pv - pc)
                else:
                    df.at[idx, 'Ganancia Neta'] = "0,00"

        guardar_datos_texto(df)
        st.success("✅ Datos actualizados"); time.sleep(1); st.rerun()

# --- FINANZAS ---
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Finanzas")
    st.caption("Cálculos en tiempo real sobre texto.")
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
        
        # NUEVAS MÉTRICAS SOLICITADAS
        g1, g2 = st.columns(2)
        # Suma de lo GASTADO en total (Todo lo que has comprado en la historia)
        gasto_total_hist = df_calc['Precio Compra'].sum()
        # Suma de lo INGRESADO total (Todo lo que has vendido)
        ingreso_total_hist = ds['Precio Venta'].sum()
        
        g1.metric("Total Gastado (Compras)", float_a_texto(gasto_total_hist) + " €")
        g2.metric("Total Ingresado (Ventas)", float_a_texto(ingreso_total_hist) + " €")
        
        st.divider()
        if not ds.empty:
            c1, c2 = st.columns(2)
            with c1: 
                fig = px.pie(ds, names='Marca', values='Ganancia Neta', title='Rentabilidad por Marca', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = px.bar(ds.groupby('Plataforma Venta')['Ganancia Neta'].sum().reset_index(), x='Plataforma Venta', y='Ganancia Neta', title='Por Plataforma', color='Plataforma Venta')
                st.plotly_chart(fig2, use_container_width=True)
