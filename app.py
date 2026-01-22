import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V48", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL ---
st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #000000;}
    
    /* Barra Lateral */
    section[data-testid="stSidebar"] {background-color: #111111;}
    section[data-testid="stSidebar"] * {color: #FFFFFF !important;}
    
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        color: #000000 !important; background-color: #F0F2F6 !important; border: 1px solid #ccc;
    }
    
    /* Botón ROJO Acción */
    div.stButton > button {
        background-color: #D32F2F; color: white; font-weight: bold; border: none; width: 100%;
        padding: 12px; font-size: 16px;
    }
    
    /* Botón AZUL Enlace (Rastrear) */
    a.st-emotion-cache-button {
        text-decoration: none; color: white !important;
    }
    
    /* Métricas */
    div[data-testid="stMetricValue"] {font-size: 24px !important; color: #2E7D32 !important;}
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
    st.markdown("### Versión 48")
    with st.form("login_v48"):
        pin = st.text_input("PIN:", type="password")
        if st.form_submit_button("ENTRAR AL SISTEMA"):
            if pin == "1234": st.session_state['autenticado'] = True; st.rerun()
            else: st.error("🚫 PIN Incorrecto")
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
    # AÑADIDA COLUMNA 'Tracking'
    cols = ["ID", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", 
            "Estado", "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Tracking", "Fecha Compra", "Fecha Venta", "ROI %"]
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
                df['Tracking'] = df['Tracking'].astype(str).replace('nan', '') # Asegurar que tracking es texto
                
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                
                # Enlace de Mercado
                df['🔍 Mercado'] = "https://www.google.com/search?q=" + df['Marca'].astype(str) + "+" + df['Modelo'].astype(str) + "+precio"
                
                return df
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        if '🔍 Mercado' in dfs.columns: dfs = dfs.drop(columns=['🔍 Mercado'])
            
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
        st.write("")
        if st.button("🚚 ENVÍOS", use_container_width=True): st.session_state['seccion_actual'] = "Seguimiento"; st.rerun()
    with c2:
        if st.button("💸 VENDER", use_container_width=True): st.session_state['seccion_actual'] = "Vender"; st.rerun()
        st.write("")
        if st.button("📊 FINANZAS", use_container_width=True): st.session_state['seccion_actual'] = "Finanzas"; st.rerun()

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
        
        st.divider()
        cant = st.number_input("📦 Cantidad (Pares iguales)", min_value=1, value=1)
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca/Modelo")
            else:
                p = forzar_numero(pr); nid_base = 1 if df.empty else df['ID'].max()+1
                nuevas = []
                for i in range(cant):
                    new = {"ID":nid_base+i, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":mf, "Modelo":mod, "Talla":arreglar_talla(ta), "Tienda Origen":tf, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":p, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0, "Tracking":""}
                    nuevas.append(new)
                df = pd.concat([df, pd.DataFrame(nuevas)], ignore_index=True)
                guardar_datos(df); st.session_state['ok']=True; st.rerun()

# --- VENDER (CON TRACKING) ---
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
        pv = forzar_numero(pv_txt)
        gan = pv - row['Precio Compra']
        if pv > 0:
            col = "green" if gan > 0 else "red"
            st.markdown(f"#### 💰 Ganancia: <span style='color:{col}'>{gan:.2f} €</span>", unsafe_allow_html=True)
        
        with st.form("f_ven"):
            c3,c4 = st.columns(2)
            pl = c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","En Persona","Otro"])
            cu = c4.text_input("Cuenta Venta")
            # CAMPO NUEVO
            track = st.text_input("🚚 Nº Seguimiento (Opcional):", placeholder="Pega aquí el código del envío")
            
            if st.form_submit_button("CONFIRMAR VENTA"):
                idx=df.index[df['ID']==ids][0]
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=pl; df.at[idx,'Cuenta Venta']=cu; df.at[idx,'Ganancia Neta']=gan
                df.at[idx, 'Tracking'] = track # Guardamos tracking
                guardar_datos(df); st.balloons(); st.success(f"¡Vendido! Ganancia: {gan:.2f}€"); st.rerun()

# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial Global")
    busqueda = st.text_input("🔍 Filtrar:", placeholder="Escribe para filtrar...")
    c_s1, c_s2 = st.columns(2)
    cri = c_s1.selectbox("🔃 Ordenar por:", ["Fecha Compra (Más reciente)", "Fecha Compra (Más antigua)", "Marca (A-Z)", "Precio Compra (Menor a Mayor)", "Estado"])
    
    df_ver = df.copy()
    if busqueda: mask = df_ver.astype(str).apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1); df_ver = df_ver[mask]
    if cri == "Fecha Compra (Más reciente)": df_ver = df_ver.sort_values(by="Fecha Compra", ascending=False)
    elif cri == "Fecha Compra (Más antigua)": df_ver = df_ver.sort_values(by="Fecha Compra", ascending=True)
    elif cri == "Marca (A-Z)": df_ver = df_ver.sort_values(by="Marca", ascending=True)
    elif cri == "Precio Compra (Menor a Mayor)": df_ver = df_ver.sort_values(by="Precio Compra", ascending=True)
    elif cri == "Estado": df_ver = df_ver.sort_values(by="Estado", ascending=True)

    cols_ord = ["ID", "🔍 Mercado", "Marca", "Modelo", "Talla", "Precio Compra", "Precio Venta", "Ganancia Neta", "Estado", "Tracking", "Fecha Compra", "Fecha Venta"]
    df_ver = df_ver[[c for c in cols_ord if c in df_ver.columns]]

    col_cfg = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "🔍 Mercado": st.column_config.LinkColumn(display_text="🔎 Ver"),
        "Marca": st.column_config.TextColumn(width="medium"),
        "Modelo": st.column_config.TextColumn(width="large"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]),
        "Tracking": st.column_config.TextColumn(help="Escribe aquí el número de seguimiento")
    }
    df_ed = st.data_editor(df_ver, column_config=col_cfg, hide_index=True, use_container_width=True, num_rows="dynamic", key="ed_v48")
    if not df.equals(df_ed):
        df_ag = df_ed.drop(columns=['🔍 Mercado'], errors='ignore')
        df_ag['Ganancia Neta'] = df_ag['Precio Venta'] - df_ag['Precio Compra']
        df_ag['Talla'] = df_ag['Talla'].apply(arreglar_talla)
        df.update(df_ag); guardar_datos(df); st.toast("✅ Cambios guardados")

# --- SEGUIMIENTO (NUEVO) ---
elif st.session_state['seccion_actual'] == "Seguimiento":
    st.title("🚚 Seguimiento de Envíos")
    st.info("Aquí ves lo que has vendido y tiene número de seguimiento.")
    
    # Filtramos las que tienen algo escrito en Tracking y están vendidas
    df_track = df[(df['Tracking'] != "") & (df['Estado'] == 'Vendido')].copy()
    
    if df_track.empty:
        st.warning("No hay envíos activos. Añade el número de seguimiento al vender o en el historial.")
    else:
        for index, row in df_track.iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.markdown(f"**{row['Marca']} {row['Modelo']}**")
                c1.caption(f"Talla: {row['Talla']} | {row['Plataforma Venta']}")
                
                c2.text_input("Nº Seguimiento", value=row['Tracking'], disabled=True, key=f"t_{row['ID']}")
                
                # ENLACE MÁGICO A 17TRACK (Rastreador Universal)
                link_rastreo = f"https://t.17track.net/es#nums={row['Tracking']}"
                c3.link_button("🔎 RASTREAR", link_rastreo)
                
                st.divider()

# --- FINANZAS ---
elif st.session_state['seccion_actual'] == "Finanzas":
    st.title("📊 Panel Financiero")
    c_ex1, c_ex2 = st.columns(2)
    df_exp = df.drop(columns=['🔍 Mercado'], errors='ignore')
    c_ex1.download_button("📥 Stock (CSV)", df_exp[df_exp['Estado']=='En Stock'].to_csv(index=False).encode('utf-8-sig'), "stock.csv", "text/csv")
    c_ex2.download_button("💰 Ventas (CSV)", df_exp[df_exp['Estado']=='Vendido'].to_csv(index=False).encode('utf-8-sig'), "ventas.csv", "text/csv")
    st.divider()

    if not df.empty:
        hoy = datetime.now()
        df_sold = df[df['Estado'] == 'Vendido']; df_stock = df[df['Estado'] == 'En Stock']
        m_c_m = (df['Fecha Compra'].dt.month == hoy.month) & (df['Fecha Compra'].dt.year == hoy.year)
        m_v_m = (df_sold['Fecha Venta'].dt.month == hoy.month) & (df_sold['Fecha Venta'].dt.year == hoy.year)
        
        # Mejor venta
        ventas_mes_df = df_sold[m_v_m].copy()
        if not ventas_mes_df.empty:
            ventas_mes_df['ROI_Calc'] = ventas_mes_df.apply(lambda x: (x['Ganancia Neta'] / x['Precio Compra'] * 100) if x['Precio Compra'] > 0 else 0, axis=1)
            mejor = ventas_mes_df.loc[ventas_mes_df['ROI_Calc'].idxmax()]
            txt_mejor = f"🏆 Mejor: {mejor['Marca']} {mejor['Modelo']} (+{mejor['Ganancia Neta']:.2f}€)"
        else: txt_mejor = "🏆 Mejor: -"

        st.subheader(f"📅 {hoy.strftime('%B %Y')}")
        st.caption(txt_mejor) # Mostramos la mejor venta aquí pequeña
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Beneficio", f"{df_sold[m_v_m]['Ganancia Neta'].sum():.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        m2.metric("Gasto", f"{df[m_c_m]['Precio Compra'].sum():.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        m3.metric("Ventas", len(df_sold[m_v_m])); m4.metric("Compras", len(df[m_c_m]))
        
        st.divider()
        st.subheader("🌍 Global")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Beneficio Total", f"{df_sold['Ganancia Neta'].sum():.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        g2.metric("Stock (€)", f"{df_stock['Precio Compra'].sum():.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        g3.metric("Stock (Uds.)", len(df_stock)); g4.metric("Vendidos", len(df_sold))
        st.divider()
        if not df_sold.empty: st.bar_chart(df_sold.groupby('Marca')['Ganancia Neta'].sum().sort_values(ascending=False).head(5))
