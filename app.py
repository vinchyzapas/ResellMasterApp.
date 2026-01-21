
    import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V39", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL (CSS) ---
st.markdown("""
<style>
    /* Fondo General */
    .stApp {background-color: #0E1117; color: white;}
    section[data-testid="stSidebar"] {background-color: #000000;}
    section[data-testid="stSidebar"] * {color: white !important;}
    
    .stTextInput input, .stNumberInput input {
        background-color: #333333 !important; color: white !important; border: 1px solid #555;
    }
    div[data-baseweb="select"] > div {background-color: #333333 !important; color: white !important;}
    
    /* BOTÓN ROJO DE ENTRADA */
    .stButton > button {
        background-color: #D32F2F !important; color: #FFFFFF !important;
        border: 2px solid #B71C1C !important; font-weight: 900 !important; width: 100% !important;
    }
    .stButton > button:hover {background-color: #FF5252 !important;}
    
    /* Métricas */
    div[data-testid="stMetricValue"] {font-size: 24px !important; color: #4CAF50 !important;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.markdown("### Versión 39")
    with st.form("login_form"):
        pin = st.text_input("INTRODUCE PIN:", type="password")
        submit = st.form_submit_button("ENTRAR AL SISTEMA")
        if submit:
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

# --- LÓGICA PRECIOS Y TALLAS ---
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

# --- FUNCIÓN EXPORTAR EXCEL ---
def convertir_df_csv(df):
    # utf-8-sig es importante para que Excel lea bien las tildes y la Ñ
    return df.to_csv(index=False).encode('utf-8-sig')

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
                
                df['Precio Compra'] = df['Precio Compra'].apply(forzar_numero_real)
                df['Precio Venta'] = df['Precio Venta'].apply(forzar_numero_real)
                df['Ganancia Neta'] = df['Precio Venta'] - df['Precio Compra']
                df.loc[df['Estado'] == 'En Stock', 'Ganancia Neta'] = 0.0
                
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Talla'] = df['Talla'].apply(arreglar_talla)
                
                # Convertir a objetos DATETIME reales para que se puedan ordenar
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

# --- INTERFAZ ---
st.sidebar.title("Menú")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo", "💸 Vender", "📦 Historial", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos_cacheado()
list_m, list_t = obtener_listas(df)

# --- 1. NUEVO ---
if op == "👟 Nuevo":
    st.title("👟 Nuevo")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    with st.form("form_nuevo"):
        c1, c2 = st.columns([1, 2])
        ms = c1.selectbox("Marca", ["-"] + list_m); mt = c1.text_input("¿Nueva?", placeholder="Escribe aquí")
        mf = str(mt if mt else ms).strip().title()
        if mf == "-": mf = ""
        mod = c2.text_input("Modelo")
        
        c3, c4, c5 = st.columns(3)
        ts = c3.selectbox("Tienda", ["-"] + list_t); tt = c3.text_input("¿Nueva?", placeholder="Escribe aquí")
        tf = str(tt if tt else ts).strip().title()
        if tf == "-": tf = ""
        ta = c4.text_input("Talla")
        pr_txt = c5.text_input("Precio Compra (€)", placeholder="Ej: 45,50")
        
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
        with st.form("form_vender"):
            pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50")
            c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta Venta")
            if st.form_submit_button("CONFIRMAR VENTA"):
                try: pv = float(str(pv_txt).replace(",", "."))
                except: pv = 0.0
                idx = df.index[df['ID']==ids][0]
                g = pv - row['Precio Compra']
                coste = row['Precio Compra']
                roi = (g/coste*100) if coste > 0 else 0
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=roi
                guardar_datos(df); st.balloons(); st.success("Vendido"); st.rerun()

# --- 3. HISTORIAL ---
elif op == "📦 Historial":
    st.title("📦 Historial Global")
    
    busqueda = st.text_input("🔍 BUSCADOR (Marca, Modelo, ID...)", placeholder="Escribe para filtrar...")
    
    df_ver = df.copy()
    # Filtrado por texto (convirtiendo todo a texto temporalmente para buscar)
    if busqueda:
        mask = df_ver.astype(str).apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1)
        df_ver = df_ver[mask]

    col_config = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "Marca": st.column_config.TextColumn(width="medium"),
        "Modelo": st.column_config.TextColumn(width="large"),
        "Talla": st.column_config.TextColumn(width="small"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"), # Esto permite ordenar por fecha
        "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }
    
    st.caption("💡 Pincha en 'Fecha Compra' o 'Fecha Venta' para ordenar.")
    
    df_editado = st.data_editor(
        df_ver, 
        column_config=col_config, 
        hide_index=True, 
        use_container_width=True,
        num_rows="dynamic"
    )

    if not df.equals(df_editado):
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
        df_editado['Talla'] = df_editado['Talla'].apply(arreglar_talla)
        # Actualización segura: Solo actualizamos las filas que han cambiado
        df.update(df_editado)
        guardar_datos(df)
        st.toast("✅ Cambios guardados")

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Panel Financiero")
    
    if not df.empty:
        hoy = datetime.now()
        df_vendidos = df[df['Estado'] == 'Vendido']
        df_stock = df[df['Estado'] == 'En Stock']
        
        # Cálculos Mes
        compras_mes = df[(df['Fecha Compra'].dt.month == hoy.month) & (df['Fecha Compra'].dt.year == hoy.year)]
        ventas_mes = df_vendidos[(df_vendidos['Fecha Venta'].dt.month == hoy.month) & (df_vendidos['Fecha Venta'].dt.year == hoy.year)]
        
        gasto_mes = compras_mes['Precio Compra'].sum()
        ganancia_mes = ventas_mes['Ganancia Neta'].sum()
        dinero_stock = df_stock['Precio Compra'].sum()
        
        coste_total_vendidos = df_vendidos['Precio Compra'].sum()
        beneficio_total = df_vendidos['Ganancia Neta'].sum()
        roi_total = (beneficio_total / coste_total_vendidos * 100) if coste_total_vendidos > 0 else 0.0
        
        # Visuales
        st.markdown(f"### 📅 {hoy.strftime('%B %Y')}")
        c1, c2 = st.columns(2)
        c1.metric("Gasto Mes", f"{gasto_mes:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        c2.metric("Beneficio Mes", f"{ganancia_mes:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."), delta_color="normal")
        
        st.markdown("### 🌍 Globales")
        c3, c4 = st.columns(2)
        c3.metric("Stock Activo", f"{dinero_stock:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        c4.metric("ROI Histórico", f"{roi_total:.1f} %")
        
        st.divider()
        
        # --- ZONA EXPORTACIÓN (NUEVO) ---
        st.subheader("📂 Exportar Datos")
        col_ex1, col_ex2 = st.columns(2)
        
        with col_ex1:
            # Botón Stock
            csv_stock = convertir_df_csv(df_stock)
            st.download_button(
                label="📥 Descargar SOLO STOCK (Excel)",
                data=csv_stock,
                file_name=f"stock_vinchy_{hoy.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col_ex2:
            # Botón Ventas
            csv_ventas = convertir_df_csv(df_vendidos)
            st.download_button(
                label="💰 Descargar SOLO VENTAS (Excel)",
                data=csv_ventas,
                file_name=f"ventas_vinchy_{hoy.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        st.divider()
        st.subheader("Beneficio por Plataforma")
        if not df_vendidos.empty:
            st.bar_chart(df_vendidos.groupby('Plataforma Venta')['Ganancia Neta'].sum())
