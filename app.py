import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V49", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL ---
st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #000000;}
    section[data-testid="stSidebar"] {background-color: #111111;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        color: #000000 !important; background-color: #F0F2F6 !important; border: 1px solid #ccc;
    }
    /* BOTÓN ROJO */
    div.stButton > button {
        background-color: #D32F2F; color: white; font-weight: bold; border: none; width: 100%;
        padding: 12px; font-size: 16px;
    }
    /* ENLACES BOTONES */
    a.st-emotion-cache-button {text-decoration: none; color: white !important;}
    
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
    st.markdown("### Versión 49")
    with st.form("login_v49"):
        pin = st.text_input("PIN:", type="password")
        if st.form_submit_button("ENTRAR AL SISTEMA"):
            if pin == "1234": st.session_state['autenticado'] = True; st.rerun()
            else: st.error("🚫 PIN Incorrecto")
    st.stop()

# --- CONEXIÓN AL LIBRO COMPLETO ---
def obtener_libro_google():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas")
    except: return None

# --- GESTIÓN DE ZAPATILLAS (Hoja 1) ---
def cargar_datos_zapas():
    libro = obtener_libro_google()
    if not libro: return pd.DataFrame()
    try:
        sheet = libro.sheet1 # Primera pestaña
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Limpieza y formatos
        cols = ["ID", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", 
                "Estado", "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Fecha Compra", "Fecha Venta", "ROI %"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
            
        # Números
        for c in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace("€","").str.replace(",",".").str.strip(), errors='coerce').fillna(0.0)
            # Regla corrección precios locos
            df[c] = df[c].apply(lambda x: x/100 if x > 1000 else (x/10 if x > 150 else x))

        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
        df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
        
        return df[cols]
    except: return pd.DataFrame()

def guardar_datos_zapas(df):
    libro = obtener_libro_google()
    if libro:
        sheet = libro.sheet1
        dfs = df.copy()
        for col in ['Precio Compra', 'Precio Venta', 'Ganancia Neta']:
            dfs[col] = dfs[col].apply(lambda x: f"{float(x):.2f}".replace(".", ",") if isinstance(x, (int, float)) else "0,00")
        dfs['Fecha Compra'] = pd.to_datetime(dfs['Fecha Compra']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs['Fecha Venta'] = pd.to_datetime(dfs['Fecha Venta']).dt.strftime('%d/%m/%Y').replace("NaT", "")
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())

# --- GESTIÓN DE TRACKINGS (Hoja 2) ---
def cargar_trackings():
    libro = obtener_libro_google()
    if not libro: return pd.DataFrame(columns=["Alias", "Tracking", "Fecha"])
    
    # Intentamos abrir la pestaña "trackings", si no existe, la creamos
    try:
        sheet = libro.worksheet("trackings")
    except:
        sheet = libro.add_worksheet(title="trackings", rows=100, cols=3)
        sheet.append_row(["Alias", "Tracking", "Fecha"])
        
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def guardar_tracking_nuevo(alias, codigo):
    libro = obtener_libro_google()
    if libro:
        try: sheet = libro.worksheet("trackings")
        except: sheet = libro.add_worksheet(title="trackings", rows=100, cols=3)
        
        fecha = datetime.now().strftime("%d/%m/%Y")
        sheet.append_row([alias, codigo, fecha])

def borrar_tracking(codigo):
    libro = obtener_libro_google()
    if libro:
        sheet = libro.worksheet("trackings")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Filtramos para quitar el borrado
        df_nuevo = df[df['Tracking'].astype(str) != str(codigo)]
        
        sheet.clear()
        sheet.update([df_nuevo.columns.values.tolist()] + df_nuevo.values.tolist())

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
if st.sidebar.button("🔒 Cerrar Sesión"): 
    st.session_state['autenticado']=False
    st.rerun()

# Carga de datos principales
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
        # NUEVO BOTÓN
        if st.button("🚚 PAQUETES EN CAMINO", use_container_width=True): st.session_state['seccion_actual'] = "Trackings"; st.rerun()
    with c2:
        if st.button("💸 VENDER", use_container_width=True): st.session_state['seccion_actual'] = "Vender"; st.rerun()
        st.write("")
        if st.button("📊 FINANZAS", use_container_width=True): st.session_state['seccion_actual'] = "Finanzas"; st.rerun()

# --- NUEVO TRACKING ---
elif st.session_state['seccion_actual'] == "Trackings":
    st.title("🚚 Paquetes en Camino")
    st.info("Añade aquí los envíos que estás esperando recibir.")
    
    # 1. FORMULARIO AÑADIR
    with st.form("form_track"):
        c1, c2 = st.columns(2)
        alias = c1.text_input("Alias / Tienda", placeholder="Ej: Pedido Nike")
        track_num = c2.text_input("Nº Seguimiento")
        if st.form_submit_button("AÑADIR SEGUIMIENTO"):
            if alias and track_num:
                guardar_tracking_nuevo(alias, track_num)
                st.success("Añadido"); st.rerun()
            else:
                st.error("Faltan datos")
    
    st.divider()
    
    # 2. LISTA DE PAQUETES
    df_t = cargar_trackings()
    
    if df_t.empty:
        st.caption("No tienes paquetes pendientes.")
    else:
        for index, row in df_t.iterrows():
            with st.container():
                col_info, col_btn, col_del = st.columns([2, 1, 1])
                
                # Info
                col_info.markdown(f"**{row['Alias']}**")
                col_info.caption(f"Ref: {row['Tracking']} ({row['Fecha']})")
                
                # Botón Rastrear (17Track)
                link = f"https://t.17track.net/es#nums={row['Tracking']}"
                col_btn.link_button("🔎 RASTREAR", link)
                
                # Botón Borrar (Ya llegó)
                if col_del.button("🗑️ YA LLEGÓ", key=f"del_{index}"):
                    borrar_tracking(row['Tracking'])
                    st.toast("Paquete eliminado de la lista")
                    st.rerun()
                
                st.divider()

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
        
        cant = st.number_input("📦 Cantidad", min_value=1, value=1)
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca/Modelo")
            else:
                try: p = float(str(pr).replace(",", "."))
                except: p = 0.0
                if p > 150: p = p/10 # Auto-corrección
                
                nid = 1 if df.empty else df['ID'].max()+1
                nuevas = []
                for i in range(cant):
                    new = {"ID":nid+i, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":ta, "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                    nuevas.append(new)
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
        
        st.markdown(f"### 👟 {row['Marca']} {row['Modelo']}")
        c_i1, c_i2, c_i3 = st.columns(3)
        c_i1.metric("Talla", row['Talla']); c_i2.metric("Tienda", row['Tienda Origen'])
        c_i3.metric("Coste", f"{row['Precio Compra']:.2f} €".replace(".", ","))
        
        st.divider()
        pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50")
        
        try: pv = float(str(pv_txt).replace(",", "."))
        except: pv = 0.0
        gan = pv - row['Precio Compra']
        
        if pv > 0:
            col = "green" if gan > 0 else "red"
            st.markdown(f"#### 💰 Ganancia: <span style='color:{col}'>{gan:.2f} €</span>", unsafe_allow_html=True)
        
        with st.form("f_ven"):
            c3,c4=st.columns(2)
            pl = c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","En Persona","Otro"])
            cu = c4.text_input("Cuenta Venta")
            
            if st.form_submit_button("CONFIRMAR VENTA"):
                idx=df.index[df['ID']==ids][0]
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=pl; df.at[idx,'Cuenta Venta']=cu; df.at[idx,'Ganancia Neta']=gan
                guardar_datos_zapas(df); st.balloons(); st.success(f"¡Vendido!"); st.rerun()

# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial")
    busqueda = st.text_input("🔍 Filtrar:", placeholder="Escribe...")
    c_s1, c_s2 = st.columns(2)
    cri = c_s1.selectbox("🔃 Ordenar:", ["Fecha Compra (Reciente)", "Marca (A-Z)", "Precio (Bajo-Alto)"])
    
    df_ver = df.copy()
    if busqueda: mask = df_ver.astype(str).apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1); df_ver = df_ver[mask]
    if "Reciente" in cri: df_ver = df_ver.sort_values(by="Fecha Compra", ascending=False)
    elif "Marca" in cri: df_ver = df_ver.sort_values(by="Marca", ascending=True)
    elif "Precio" in cri: df_ver = df_ver.sort_values(by="Precio Compra", ascending=True)

    col_cfg = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "Marca": st.column_config.TextColumn(width="medium"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }
    df_ed = st.data_editor(df_ver, column_config=col_cfg, hide_index=True, use_container_width=True, num_rows="dynamic", key="v49_ed")
    if not df.equals(df_ed):
        df_ed['Ganancia Neta'] = df_ed['Precio Venta'] - df_ed['Precio Compra']
        df.update(df_ed); guardar_datos_zapas(df); st.toast("✅ Guardado")

# --- FINANZAS ---
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Finanzas")
    c_ex1, c_ex2 = st.columns(2)
    c_ex1.download_button("📥 Stock CSV", df[df['Estado']=='En Stock'].to_csv(index=False).encode('utf-8-sig'), "stock.csv", "text/csv")
    c_ex2.download_button("💰 Ventas CSV", df[df['Estado']=='Vendido'].to_csv(index=False).encode('utf-8-sig'), "ventas.csv", "text/csv")
    st.divider()

    if not df.empty:
        hoy = datetime.now()
        df_sold = df[df['Estado'] == 'Vendido']; df_stock = df[df['Estado'] == 'En Stock']
        m_c_m = (df['Fecha Compra'].dt.month == hoy.month) & (df['Fecha Compra'].dt.year == hoy.year)
        m_v_m = (df_sold['Fecha Venta'].dt.month == hoy.month) & (df_sold['Fecha Venta'].dt.year == hoy.year)
        
        # Mejor venta
        v_mes = df_sold[m_v_m].copy()
        txt_mejor = "-"
        if not v_mes.empty:
            v_mes['ROI_Calc'] = v_mes.apply(lambda x: (x['Ganancia Neta'] / x['Precio Compra'] * 100) if x['Precio Compra'] > 0 else 0, axis=1)
            mejor = v_mes.loc[v_mes['ROI_Calc'].idxmax()]
            txt_mejor = f"🏆 {mejor['Marca']} {mejor['Modelo']} (+{mejor['Ganancia Neta']:.2f}€)"

        st.subheader(f"📅 {hoy.strftime('%B %Y')}")
        st.info(txt_mejor)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Beneficio", f"{df_sold[m_v_m]['Ganancia Neta'].sum():.2f} €".replace(".", ","))
        m2.metric("Gasto", f"{df[m_c_m]['Precio Compra'].sum():.2f} €".replace(".", ","))
        m3.metric("Ventas", len(df_sold[m_v_m])); m4.metric("Compras", len(df[m_c_m]))
        
        st.divider()
        st.subheader("🌍 Global")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Total Ganado", f"{df_sold['Ganancia Neta'].sum():.2f} €".replace(".", ","))
        g2.metric("Stock (€)", f"{df_stock['Precio Compra'].sum():.2f} €".replace(".", ","))
        g3.metric("Pares Stock", len(df_stock)); g4.metric("Total Ventas", len(df_sold))
