
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V26", layout="wide", page_icon="👟")

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
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
def check_password():
    if st.session_state.password_input == "1234": st.session_state['autenticado'] = True
    else: st.error("🚫 Incorrecto")

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.text_input("Introduce PIN:", type="password", key="password_input", on_change=check_password)
    st.stop()

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except Exception as e:
        return None

# --- LIMPIADORES (Precios y Tallas) ---
def limpiar_precio(texto):
    if not texto: return 0.0
    try:
        # Quita € y cambia coma por punto
        limpio = str(texto).replace("€", "").strip().replace(",", ".")
        return float(limpio)
    except:
        return 0.0

def limpiar_talla(texto):
    # La talla siempre será TEXTO, pero cambiamos comas por puntos para que quede bonito
    if not texto: return ""
    return str(texto).replace(",", ".").strip()

# --- CARGAR DATOS ---
def cargar_datos():
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
                
                # --- LIMPIEZA DE DATOS ---
                # 1. Precios a números seguros
                df['Precio Compra'] = pd.to_numeric(df['Precio Compra'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Precio Venta'] = pd.to_numeric(df['Precio Venta'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                df['Ganancia Neta'] = pd.to_numeric(df['Ganancia Neta'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                
                # 2. Talla a Texto Seguro (y unificamos coma a punto)
                df['Talla'] = df['Talla'].astype(str).str.replace(',', '.').str.strip()
                
                # 3. Fechas y IDs
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                
                # 4. Textos bonitos
                if 'Marca' in df.columns: df['Marca'] = df['Marca'].astype(str).str.strip().str.title()
                if 'Tienda Origen' in df.columns: df['Tienda Origen'] = df['Tienda Origen'].astype(str).str.strip().str.title()
                
                return df[cols], True
            else:
                return pd.DataFrame(columns=cols), True
        except: pass
    return pd.DataFrame(columns=cols), False

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        dfs['Fecha Compra'] = dfs['Fecha Compra'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs['Fecha Venta'] = dfs['Fecha Venta'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        
        # Aseguramos que la talla se guarde como TEXTO en Google Sheets (poniendo una comilla simple delante si es necesario, o solo string)
        dfs['Talla'] = dfs['Talla'].astype(str)
        
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())

# --- LISTAS INTELIGENTES ---
def obtener_listas_actualizadas(df):
    marcas, tiendas = [], []
    if not df.empty:
        if 'Marca' in df.columns: marcas = df['Marca'].unique().tolist()
        if 'Tienda Origen' in df.columns: tiendas = df['Tienda Origen'].unique().tolist()
    
    todas_marcas = sorted(list(set(BASES_MARCAS + marcas)))
    todas_tiendas = sorted(list(set(BASES_TIENDAS + tiendas)))
    return [m for m in todas_marcas if str(m).strip() not in ["", "nan"]], [t for t in todas_tiendas if str(t).strip() not in ["", "nan"]]

# --- ESTADO ---
keys = ['k_marca_sel', 'k_marca_txt', 'k_modelo', 'k_tienda_sel', 'k_tienda_txt', 'k_talla', 'k_precio']
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys: st.session_state[k] = ""
    st.session_state['limpiar'] = False

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df, ok = cargar_datos()
if not ok: st.error("Error de conexión"); st.stop()

mis_marcas, mis_tiendas = obtener_listas_actualizadas(df)

# --- 1. NUEVO PRODUCTO ---
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        with c1:
            ms = st.selectbox("Marca", ["- Seleccionar -"] + mis_marcas, key="k_marca_sel")
            mt = st.text_input("¿Nueva?", key="k_marca_txt")
            mf = mt if mt else ms
            if mf == "- Seleccionar -": mf = ""

        mod = c2.text_input("Modelo", key="k_modelo")

        c3, c4, c5 = st.columns(3)
        with c3:
            ts = st.selectbox("Tienda", ["- Seleccionar -"] + mis_tiendas, key="k_tienda_sel")
            tt = st.text_input("¿Nueva?", key="k_tienda_txt")
            tf = tt if tt else ts
            if tf == "- Seleccionar -": tf = ""

        # TALLA (TEXTO LIBRE)
        ta_txt = c4.text_input("Talla", key="k_talla", placeholder="Ej: 42,5")
        
        # PRECIO (TEXTO LIBRE)
        pr_txt = c5.text_input("Precio Compra (€)", key="k_precio", placeholder="Ej: 50,90")
        
        if st.form_submit_button("GUARDAR", use_container_width=True):
            if not mf or not mod: st.error("⚠️ Falta datos")
            else:
                # Limpiamos talla y precio antes de guardar
                talla_final = limpiar_talla(ta_txt)
                precio_final = limpiar_precio(pr_txt)
                
                nid = 1 if df.empty else df['ID'].max()+1
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, 
                       "Marca":str(mf).strip().title(), "Modelo":mod, "Talla":talla_final, 
                       "Tienda Origen":str(tf).strip().title(), "Plataforma Venta":"", "Cuenta Venta":"", 
                       "Precio Compra":precio_final, "Precio Venta":0.0, "Estado":"En Stock", 
                       "Ganancia Neta":0.0, "ROI %":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df); st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

# --- 2. VENDER ---
elif op == "💸 Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    if dfs.empty: st.warning("Sin stock.")
    else:
        sel = st.selectbox("Busca:", ["Seleccionar..."] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist())
        if sel != "Seleccionar...":
            ids = int(float(sel.split(" |")[0].replace("ID:","")))
            row = df[df['ID']==ids].iloc[0]
            st.info(f"VENDIENDO: **{row['Marca']} {row['Modelo']}** (Talla: {row['Talla']})")
            with st.form("fv"):
                pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50")
                c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta Venta")
                if st.form_submit_button("CONFIRMAR VENTA", use_container_width=True):
                    pv = limpiar_precio(pv_txt); idx=df.index[df['ID']==ids][0]; g=pv-row['Precio Compra']
                    df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g
                    guardar_datos(df); st.balloons(); st.success("¡Vendido!"); st.rerun()

# --- 3. HISTORIAL ---
elif op == "📦 Historial":
    st.title("📦 Historial")
    with st.expander("🗑️ ELIMINAR"):
        sb = st.selectbox("Buscar:", ["- Elegir -"] + df.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1).tolist())
        if sb != "- Elegir -":
            idb = int(sb.split(" |")[0].replace("ID:", ""))
            if st.button(f"🗑️ BORRAR ID {idb}", type="primary"):
                guardar_datos(df[df['ID'] != idb]); st.success("Borrado."); st.rerun()

    col_config = {
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]),
        "ID": st.column_config.NumberColumn(disabled=True),
        "Talla": st.column_config.TextColumn() # Talla como texto para evitar líos
    }
    df_ed = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="fixed", use_container_width=True)
    if not df.equals(df_ed):
        df_ed['Ganancia Neta'] = df_ed['Precio Venta'] - df_ed['Precio Compra']
        guardar_datos(df_ed); st.toast("✅ Actualizado"); st.rerun()

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        ben = sold['Ganancia Neta'].sum() if not sold.empty else 0.0
        gasto = df[df['Estado']=='En Stock']['Precio Compra'].sum() if not df.empty else 0.0
        
        c1, c2 = st.columns(2)
        c1.metric("Beneficio Neto Total", f"{ben:.2f} €")
        c2.metric("Gasto Total en Stock", f"{gasto:.2f} €")
        st.divider()
        st.subheader("Gasto por Tienda"); st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        st.subheader("Beneficio por Plataforma"); st.bar_chart(sold.groupby('Plataforma Venta')['Ganancia Neta'].sum())
