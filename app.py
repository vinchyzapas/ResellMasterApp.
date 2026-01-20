import streamlit as st
import pandas as pd
import pdfplumber
import easyocr
import re
from datetime import datetime
from PIL import Image, ImageOps, ImageEnhance
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pyzbar.pyzbar import decode

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Resell Master V19", layout="wide", page_icon="👟")

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
def check_password():
    if st.session_state.password_input == "1234": st.session_state['autenticado'] = True
    else: st.error("🚫 Incorrecto")

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Resell Master")
    st.text_input("Introduce PIN:", type="password", key="password_input", on_change=check_password)
    st.stop()

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Usamos los secretos corregidos
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except Exception as e:
        return None

# --- CARGAR DATOS ---
def cargar_datos():
    cols = ["ID", "Fecha Compra", "Fecha Venta", "Marca", "Modelo", "Talla", "Codigo Barras", 
            "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Precio Compra", 
            "Precio Venta", "Gastos Extra", "Estado", "Ganancia Neta", "ROI %", "Ruta Archivo"]
    
    sheet = conectar_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                for c in cols: 
                    if c not in df.columns: df[c] = 0.0 if "Precio" in c else ""
                
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Codigo Barras'] = df['Codigo Barras'].astype(str).replace('nan', '')
                return df[cols]
        except: pass
    return pd.DataFrame(columns=cols)

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        dfs = df.copy()
        # Formato fecha día/mes/año
        dfs['Fecha Compra'] = dfs['Fecha Compra'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs['Fecha Venta'] = dfs['Fecha Venta'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())

# --- GESTIÓN DE ESTADO ---
keys = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio', 'k_barras']
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys: st.session_state[k] = 0.0 if 'precio' in k else ""
    st.session_state['limpiar'] = False
for k in keys: 
    if k not in st.session_state: st.session_state[k] = 0.0 if 'precio' in k else ""

# --- OCR ---
@st.cache_resource
def cargar_ocr(): return easyocr.Reader(['es','en'])
try: reader = cargar_ocr()
except: reader = None

# --- PROCESAMIENTO IMAGEN (ANTI-BLOQUEO) ---
def procesar_imagen_completa(file):
    img = Image.open(file)
    
    # 1. REDIMENSIONAR (CRÍTICO PARA EL MÓVIL)
    if img.width > 1000:
        ratio = 1000 / float(img.width)
        h = int((float(img.height) * float(ratio)))
        img = img.resize((1000, h), Image.Resampling.LANCZOS)
    
    # 2. CÓDIGO BARRAS
    barras = ""
    try:
        d = decode(img)
        if d: barras = d[0].data.decode("utf-8")
    except: pass

    # 3. MEJORAR PARA TEXTO
    img = ImageOps.grayscale(img)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    
    # 4. LEER
    txt_list = []
    if reader:
        txt_list = reader.readtext(np.array(img), detail=0)
    
    return "\n".join(txt_list), barras, txt_list

def limpiar_modelo(texto):
    basura = ["FOR", "TR", "MENS", "WOMENS", "SHOE", "RUNNING", "ORIGINALS"]
    for b in basura: texto = re.sub(r'\b'+b+r'\b', '', texto, flags=re.IGNORECASE)
    return texto.strip().title()

def procesar_texto_etiqueta(lista, full_txt):
    d = {"marca":"", "modelo":"", "talla":"", "precio":0.0, "tienda":""}
    full_up = full_txt.upper()
    
    # MARCA
    marcas = ["MERRELL", "SALOMON", "ADIDAS", "ASICS", "NIKE", "JORDAN", "NEW BALANCE", "PUMA", "HOKA", "VEJA", "CROCS", "ON", "ZARA"]
    for m in marcas:
        if m in full_up: d["marca"]=m.title(); break
    
    # TALLA (Lógica tolerante)
    match_raro = re.search(r'\b(\d{2})\s(5)\b', full_up)
    match_eur = re.search(r'(EUR|EU|F)\s?(\d{2}\.?\d?)', full_up)
    match_simple = re.search(r'\b(3[5-9]|[4][0-9])\.?5?\b', full_up)

    if match_eur: d["talla"] = match_eur.group(2)
    elif match_raro: d["talla"] = f"{match_raro.group(1)}.5"
    elif match_simple: d["talla"] = match_simple.group(0)

    # MODELO
    for linea in lista:
        l = linea.upper().strip()
        if len(l) < 4 or any(x in l for x in ["EUR","USA","UK","CM","MADE","ART","123","456"]): continue
        if d["marca"] and d["marca"].upper() in l: continue 
        d["modelo"] = limpiar_modelo(l)
        break
    return d

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú V19")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial (Editable)", "📊 Finanzas", "🚨 Alertas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos()

# ---------------------------------------------------------
# 1. NUEVO PRODUCTO
# ---------------------------------------------------------
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: st.success("✅ Guardado"); st.session_state['ok']=False

    st.info("📸 Sube foto de la ETIQUETA de la caja.")
    up = st.file_uploader("Foto Etiqueta", type=['jpg','png','jpeg'])
    txt_debug = ""
    
    if up:
        with st.spinner("Procesando..."):
            txt, barras, lista = procesar_imagen_completa(up)
            d = procesar_texto_etiqueta(lista, txt)
            txt_debug = txt
            
            if not st.session_state['k_marca']: st.session_state['k_marca'] = d["marca"]
            if not st.session_state['k_modelo']: st.session_state['k_modelo'] = d["modelo"]
            if not st.session_state['k_talla']: st.session_state['k_talla'] = d["talla"]
            if barras: st.session_state['k_barras'] = barras; st.toast("Código OK")

    if txt_debug:
        with st.expander("🔍 Ver lo que ha leído el robot"): st.text(txt_debug)

    with st.form("fc"):
        c1,c2=st.columns([1,2]); m=c1.text_input("Marca", key="k_marca"); mod=c2.text_input("Modelo", key="k_modelo")
        c3,c4,c5=st.columns(3); td=c3.text_input("Tienda", key="k_tienda"); ta=c4.text_input("Talla", key="k_talla"); pr=c5.number_input("Precio (€)", key="k_precio")
        barras = st.text_input("Código Barras", key="k_barras")
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            nid = 1 if df.empty else df['ID'].max()+1
            new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":m, "Modelo":mod, "Talla":ta, "Codigo Barras":st.session_state['k_barras'], "Tienda Origen":td, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":pr, "Precio Venta":0.0, "Gastos Extra":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0, "Ruta Archivo":""}
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            guardar_datos(df); st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

# ---------------------------------------------------------
# 2. VENDER
# ---------------------------------------------------------
elif op == "💸 Vender":
    st.title("💸 Vender")
    scan = st.file_uploader("Escanear Código", key="scan")
    zapatilla = None
    
    if scan:
        try:
            img = Image.open(scan)
            if img.width > 1000: img = img.resize((1000, int(float(img.height)*(1000/float(img.width)))), Image.Resampling.LANCZOS)
            d = decode(img)
            if d:
                c = d[0].data.decode("utf-8"); st.success(f"Código: {c}")
                f = df[(df['Codigo Barras']==c)&(df['Estado']=='En Stock')]
                if not f.empty: zapatilla=f.iloc[0]
                else: st.error("No encontrado")
        except: pass

    dfs = df[df['Estado']=='En Stock'].copy()
    opcs = ["Seleccionar..."] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1).tolist() if not dfs.empty else []
    
    if not zapatilla:
        sel = st.selectbox("Manual:", opcs)
        if sel != "Seleccionar...": zapatilla = df[df['ID']==int(float(sel.split(" |")[0].replace("ID:","")))].iloc[0]

    if zapatilla is not None:
        st.info(f"VENDIENDO: {zapatilla['Marca']} {zapatilla['Modelo']}")
        with st.form("fv"):
            pv=st.number_input("Precio Venta €", min_value=0.0, step=0.01)
            # SIN GASTOS
            c3,c4=st.columns(2); pl=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX"]); cu=c4.text_input("Cuenta")
            if st.form_submit_button("VENDER"):
                idx=df.index[df['ID']==zapatilla['ID']][0]
                g=pv-zapatilla['Precio Compra']
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Gastos Extra']=0.0
                df.at[idx,'Plataforma Venta']=pl; df.at[idx,'Cuenta Venta']=cu; df.at[idx,'Ganancia Neta']=g
                guardar_datos(df); st.balloons(); st.success("Vendido"); st.rerun()

# ---------------------------------------------------------
# 3. HISTORIAL (EDITABLE)
# ---------------------------------------------------------
elif op == "📦 Historial (Editable)":
    st.title("Historial")
    col_config = {"Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"), "Precio Compra": st.column_config.NumberColumn(format="%.2f €"), "Precio Venta": st.column_config.NumberColumn(format="%.2f €"), "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €"), "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]), "ID": st.column_config.NumberColumn(disabled=True)}
    df_editado = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True)
    if not df.equals(df_editado):
        # Recálculo simple sin gastos
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
        guardar_datos(df_editado); st.toast("✅ Guardado"); st.rerun()

elif op == "📊 Finanzas":
    st.title("Finanzas"); s=df[df['Estado']=='Vendido']
    if not df.empty: st.metric("Beneficio", f"{s['Ganancia Neta'].sum():.2f} €"); st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())

elif op == "🚨 Alertas":
    if not df.empty:
        ds=df[df['Estado']=='En Stock'].copy(); ds['D']=(datetime.now()-ds['Fecha Compra']).dt.days; o=ds[ds['D']>=30]
        if not o.empty: st.error(f"{len(o)} antiguos"); st.dataframe(o[['D','Marca']])
        else: st.success("Todo bien")
