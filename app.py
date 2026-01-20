import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V37", layout="wide", page_icon="👟")

# --- 🎨 ESTILO VISUAL ---
st.markdown("""
<style>
    .stApp {background-color: #0E1117; color: white;}
    section[data-testid="stSidebar"] {background-color: #000000;}
    section[data-testid="stSidebar"] * {color: white !important;}
    .stTextInput input, .stNumberInput input {
        background-color: #333333 !important; color: white !important; border: 1px solid #555;
    }
    div[data-baseweb="select"] > div {background-color: #333333 !important; color: white !important;}
    
    /* BOTÓN ROJO */
    button[data-testid="stFormSubmitButton"] {
        background-color: #FF0000 !important; color: white !important;
        border: 2px solid #FF0000 !important; font-weight: 900 !important; width: 100% !important;
    }
    button[data-testid="stFormSubmitButton"]:hover {
        background-color: #990000 !important; border-color: #990000 !important;
    }
    label {color: white !important;}
</style>
""", unsafe_allow_html=True)

# --- LISTAS BASE ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas")
    st.markdown("### Versión 37")
    with st.form("login_form_v37"):
        pin = st.text_input("PIN", type="password")
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

# --- LÓGICA DE CORRECCIÓN PRECIOS ---
def forzar_numero_real(valor):
    """
    Regla: Si precio > 150, divídelo porque falta la coma.
    """
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    
    try:
        str_val = str(valor).replace("€", "").replace(",", ".").strip()
        v = float(str_val)
        
        # REGLA VINCHY
        if v > 1000: v = v / 100   # 3525 -> 35.25
        elif v > 150: v = v / 10   # 144 -> 14.4
        
        return float(v)
    except:
        return 0.0

def arreglar_talla(valor):
    """Quita el .0 de las tallas"""
    v = str(valor).replace(".0", "").replace(",", ".").strip()
    if v == "nan": return ""
    return v

# --- CARGAR DATOS ---
@st.cache_data(ttl=5, show_spinner=False)
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
                    if c not in df.columns: df[c] = ""
                
                # LIMPIEZA
                df['Precio Compra'] = df['Precio Compra'].apply(forzar_numero_real)
                df['Precio Venta'] = df['Precio Venta'].apply(forzar_numero_real)
                df['Ganancia Neta'] = df['Precio Venta'] - df['Precio Compra']
                df.loc[df['Estado'] == 'En Stock', 'Ganancia Neta'] = 0.0
                
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Talla'] = df['Talla'].apply(arreglar_talla)
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
        # Guardar bonito
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
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos_cacheado()
list_m, list_t = obtener_listas(df)

# --- 1. NUEVO ---
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    # HEMOS CAMBIADO EL ID DEL FORMULARIO Y LAS KEYS PARA EVITAR EL ERROR
    with st.form("form_nuevo_prod_v37"): 
        c1, c2 = st.columns([1, 2])
        ms = c1.selectbox("Marca", ["-"] + list_m, key="v37_marca_sel")
        mt = c1.text_input("¿Nueva?", placeholder="Escribe aquí", key="v37_marca_txt")
        mf = str(mt if mt else ms).strip().title()
        if mf == "-": mf = ""
        
        mod = c2.text_input("Modelo", key="v37_modelo")
        
        c3, c4, c5 = st.columns(3)
        ts = c3.selectbox("Tienda", ["-"] + list_t, key="v37_tienda_sel")
        tt = c3.text_input("¿Nueva?", placeholder="Escribe aquí", key="v37_tienda_txt")
        tf = str(tt if tt else ts).strip().title()
        if tf == "-": tf = ""
        
        ta = c4.text_input("Talla", key="v37_talla")
        pr_txt = c5.text_input("Precio Compra (€)", placeholder="Ej: 45,50", key="v37_precio")
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            if not mod or not mf: st.error("Falta Marca o Modelo")
            else:
                # Convertimos input a numero
                try: p = float(str(pr_txt).replace(",", "."))
                except: p = 0.0
                
                # Aplicamos la regla de corrección también al guardar por si acaso
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
    sel = st.selectbox("Buscar:", opcs, key="v37_ven_sel")
    
    if sel != "-":
        ids = int(sel.split(" |")[0].replace("ID:",""))
        row = df[df['ID']==ids].iloc[0]
        st.info(f"VENDIENDO: {row['Marca']} {row['Modelo']}")
        with st.form("form_vender_v37"):
            pv_txt = st.text_input("Precio Venta (€)", placeholder="Ej: 100,50", key="v37_ven_precio")
            c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"], key="v37_plat"); cta=c4.text_input("Cuenta Venta", key="v37_cta")
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
    st.title("📦 Historial")
    with st.expander("🗑️ ELIMINAR"):
        lb = ["-"] + df.apply(lambda x: f"ID:{x['ID']} | {x['Modelo']}", axis=1).tolist()
        sb = st.selectbox("Elegir:", lb, key="v37_del_sel")
        if sb != "-":
            idb = int(sb.split(" |")[0].replace("ID:",""))
            if st.button("BORRAR", type="primary", key="v37_del_btn"):
                guardar_datos(df[df['ID']!=idb]); st.success("Borrado"); st.rerun()
    
    # Tabla Editable (Con protección de errores)
    try:
        col_config = {"Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"), "Precio Compra": st.column_config.NumberColumn(format="%.2f €", min_value=0.0, step=0.01), "Precio Venta": st.column_config.NumberColumn(format="%.2f €", min_value=0.0, step=0.01), "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €", disabled=True), "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]), "ID": st.column_config.NumberColumn(disabled=True)}
        df_editado = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True, key="v37_editor")

        if not df.equals(df_editado):
            df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
            df_editado['Talla'] = df_editado['Talla'].astype(str).apply(arreglar_talla)
            guardar_datos(df_editado); st.toast("✅ Guardado")
    except Exception as e:
        st.error("Error mostrando tabla. Recarga la página.")

# --- 4. FINANZAS ---
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        s=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        ben = s['Ganancia Neta'].sum()
        gst = df[df['Estado']=='En Stock']['Precio Compra'].sum()
        
        txt_ben = f"{ben:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        txt_gst = f"{gst:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        
        k1.metric("Beneficio Neto", txt_ben)
        k2.metric("Gasto Total en Stock", txt_gst)
        st.divider()
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        st.bar_chart(s.groupby('Plataforma Venta')['Ganancia Neta'].sum())
