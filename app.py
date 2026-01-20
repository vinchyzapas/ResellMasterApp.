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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Resell Master V17", layout="wide", page_icon="🔐")

# ==========================================
# 🔐 SISTEMA DE LOGIN (SEGURIDAD)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def check_password():
    # CONTRASEÑA: Aquí puedes cambiar el "1234" por lo que quieras
    if st.session_state.password_input == "1234":
        st.session_state['autenticado'] = True
    else:
        st.error("🚫 Contraseña incorrecta")

if not st.session_state['autenticado']:
    st.title("🔒 Resell Master")
    st.text_input("Introduce PIN de acceso:", type="password", key="password_input", on_change=check_password)
    st.stop() # Detiene el programa aquí si no hay login

# ==========================================
# 🚀 PROGRAMA PRINCIPAL
# ==========================================

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except Exception as e:
        return None

# --- CARGAR DATOS ---
def cargar_datos():
    columnas = ["ID", "Fecha Compra", "Fecha Venta", "Marca", "Modelo", "Talla", "Codigo Barras", 
                "Tienda Origen", "Plataforma Venta", "Cuenta Venta", "Precio Compra", 
                "Precio Venta", "Gastos Extra", "Estado", "Ganancia Neta", "ROI %", "Ruta Archivo"]
    sheet = conectar_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                for col in columnas:
                    if col not in df.columns: df[col] = 0.0 if "Precio" in col else ""
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                df['Codigo Barras'] = df['Codigo Barras'].astype(str).replace('nan', '')
                return df[columnas]
        except: pass
    return pd.DataFrame(columns=columnas)

# --- GUARDAR DATOS ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        df_save = df.copy()
        df_save['Fecha Compra'] = df_save['Fecha Compra'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        df_save['Fecha Venta'] = df_save['Fecha Venta'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
        df_save = df_save.fillna("")
        sheet.clear()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())

# --- GESTIÓN DE ESTADO ---
keys_form = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio', 'k_barras']
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys_form: st.session_state[k] = 0.0 if 'precio' in k else ""
    st.session_state['limpiar'] = False
for k in keys_form:
    if k not in st.session_state: st.session_state[k] = 0.0 if 'precio' in k else ""

# --- OCR ---
@st.cache_resource
def cargar_ocr(): return easyocr.Reader(['es','en'])
try: reader = cargar_ocr()
except: reader = None

def mejorar_imagen(img):
    img = ImageOps.grayscale(img)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img

def procesar_imagen_completa(file):
    img = Image.open(file)
    codigo_barras = ""
    
    # Intento de leer barras (con protección de error)
    try:
        codigos_encontrados = decode(img) 
        if codigos_encontrados:
            codigo_barras = codigos_encontrados[0].data.decode("utf-8")
    except Exception as e:
        print(f"Error lector barras: {e}")

    # Procesar texto
    img_procesada = mejorar_imagen(img)
    img_np = np.array(img_procesada)
    
    texto_lista = []
    if reader:
        texto_lista = reader.readtext(img_np, detail=0)
        
    return "\n".join(texto_lista), codigo_barras, texto_lista

def procesar_texto_etiqueta(texto_lista, texto_completo):
    d = {"marca":"", "modelo":"", "talla":"", "precio":0.0, "tienda":""}
    txt_upper = texto_completo.upper()
    
    marcas = ["MERRELL", "SALOMON", "ADIDAS", "ASICS", "NIKE", "JORDAN", "NEW BALANCE", "PUMA", "HOKA", "VEJA", "CROCS", "ON", "ZARA", "BERSHKA"]
    for m in marcas:
        if m in txt_upper: d["marca"]=m.title(); break
            
    match_eur = re.search(r'(EUR|EU)\s?(\d{2}\.?\d?)', txt_upper)
    match_f = re.search(r'\bF\s?(\d{2}\.?\d?)', txt_upper)
    match_suelto = re.search(r'\b(3[5-9]|[4][0-9])\.?5?\b', txt_upper)

    if match_eur: d["talla"] = match_eur.group(2)
    elif match_f: d["talla"] = match_f.group(1)
    elif match_suelto: d["talla"] = match_suelto.group(0)

    posibles_modelos = []
    palabras_prohibidas = ["EUR", "USA", "UK", "CM", "MM", "CN", "MADE", "FABRIQUE", "HOMMES", "MENS", "WOMENS", "UNISEX", "J03", "IG9", "ART", "H0", "4729", "V0", "ID"]
    
    for linea in texto_lista:
        linea_up = linea.upper().strip()
        if len(linea_up) < 4: continue
        es_basura = False
        for p in palabras_prohibidas:
            if p in linea_up: es_basura = True; break
        if d["marca"] and d["marca"].upper() in linea_up: es_basura = True
        
        if not es_basura: posibles_modelos.append(linea_up)
    
    if posibles_modelos: d["modelo"] = posibles_modelos[0].title()
    return d

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú V17")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender (Escáner)", "📦 Historial", "📊 Finanzas", "🚨 Alertas"])

# BOTÓN DE CERRAR SESIÓN
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión", type="primary"):
    st.session_state['autenticado'] = False
    st.rerun()

df = cargar_datos()

if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']:
        st.success("✅ Guardado"); st.session_state['ok']=False

    st.info("📸 Haz foto a la etiqueta (cerca y clara).")
    up = st.file_uploader("Foto Etiqueta", type=['jpg','png','jpeg'])
    
    # VARIABLES PARA DEBUG
    txt_debug = ""
    
    if up:
        with st.spinner("Procesando..."):
            txt, barras, lista_txt = procesar_imagen_completa(up)
            d = procesar_texto_etiqueta(lista_txt, txt)
            
            # Guardamos para el debug
            txt_debug = txt
            
            if not st.session_state['k_marca']: st.session_state['k_marca'] = d["marca"]
            if not st.session_state['k_modelo']: st.session_state['k_modelo'] = d["modelo"]
            if not st.session_state['k_talla']: st.session_state['k_talla'] = d["talla"]
            
            if barras:
                st.session_state['k_barras'] = barras
                st.toast(f"Código: {barras}")
            elif not d["marca"]:
                st.warning("⚠️ No he detectado marca. Revisa la foto.")

    # --- ZONA DE DEBUG (PARA VER QUÉ PASA) ---
    if txt_debug:
        with st.expander("👁️ VER QUÉ HA LEÍDO EL ROBOT (Si falla, abre esto)"):
            st.text(txt_debug)
            st.info("Si aquí no aparece el nombre de la zapatilla, la foto está borrosa o la letra es muy rara.")

    with st.form("fc"):
        c1,c2=st.columns([1,2]); m=c1.text_input("Marca", key="k_marca"); mod=c2.text_input("Modelo", key="k_modelo")
        c3,c4,c5=st.columns(3); td=c3.text_input("Tienda", key="k_tienda"); ta=c4.text_input("Talla", key="k_talla"); pr=c5.number_input("Precio Compra (€)", key="k_precio")
        barras_input = st.text_input("Código Barras", key="k_barras")
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            nid = 1 if df.empty else df['ID'].max()+1
            new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":m, "Modelo":mod, "Talla":ta, "Codigo Barras":st.session_state['k_barras'], 
                   "Tienda Origen":td, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":pr, "Precio Venta":0.0, "Gastos Extra":0.0, 
                   "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0, "Ruta Archivo":""}
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            guardar_datos(df)
            st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

elif op == "💸 Vender (Escáner)":
    st.title("💸 Vender")
    scan_up = st.file_uploader("Escanear Código", type=['jpg','png','jpeg'], key="vender_scan")
    zapatilla_encontrada = None
    if scan_up:
        img_scan = Image.open(scan_up)
        try:
            codigos = decode(img_scan)
            if codigos:
                code = codigos[0].data.decode("utf-8")
                st.success(f"Código: {code}")
                encontrados = df[(df['Codigo Barras'] == code) & (df['Estado'] == 'En Stock')]
                if not encontrados.empty: zapatilla_encontrada = encontrados.iloc[0]
                else: st.error("No está en stock.")
        except: st.error("Error leyendo código. Intenta manual.")
    
    st.divider()
    dfs = df[df['Estado']=='En Stock'].copy()
    opciones = ["Seleccionar..."]
    if not dfs.empty:
        dfs['D'] = dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1)
        opciones += dfs['D'].tolist()
    
    if zapatilla_encontrada is None:
        sel = st.selectbox("O busca manual:", opciones)
        if sel and sel != "Seleccionar...":
            ids = int(float(sel.split(" |")[0].replace("ID:","")))
            zapatilla_encontrada = df[df['ID']==ids].iloc[0]

    if zapatilla_encontrada is not None:
        row = zapatilla_encontrada
        st.info(f"VENDIENDO: **{row['Marca']} {row['Modelo']}**")
        with st.form("fv"):
            pv=st.number_input("Precio Venta €", min_value=0.0, step=0.01)
            c3,c4=st.columns(2); plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta")
            if st.form_submit_button("CONFIRMAR VENTA"):
                idx = df.index[df['ID'] == row['ID']].tolist()[0]
                g = pv - row['Precio Compra']
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now()
                df.at[idx,'Precio Venta']=pv; df.at[idx,'Gastos Extra']=0.0
                df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta
                df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=(g/row['Precio Compra']*100) if row['Precio Compra']>0 else 0
                guardar_datos(df); st.balloons(); st.success("¡Vendido!"); st.rerun()

elif op == "📦 Historial":
    st.title("Historial")
    col_config = {"Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"), "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"), "Precio Compra": st.column_config.NumberColumn(format="%.2f €"), "Precio Venta": st.column_config.NumberColumn(format="%.2f €"), "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €"), "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]), "ID": st.column_config.NumberColumn(disabled=True), "Codigo Barras": st.column_config.TextColumn(disabled=True)}
    df_editado = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True)
    if not df.equals(df_editado):
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra'] - df_editado['Gastos Extra']
        guardar_datos(df_editado); st.toast("✅ Guardado"); st.rerun()

elif op == "📊 Finanzas":
    st.title("Finanzas"); sold=df[df['Estado']=='Vendido']
    if not df.empty:
        k1,k2=st.columns(2); k1.metric("Beneficio", f"{sold['Ganancia Neta'].sum():.2f} €"); k2.metric("Gasto Total", f"{df['Precio Compra'].sum():.2f} €")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())

elif op == "🚨 Alertas":
    st.title("Alertas")
    if not df.empty:
        ds=df[df['Estado']=='En Stock'].copy(); ds['D']=(datetime.now()-ds['Fecha Compra']).dt.days; old=ds[ds['D']>=30]
        if not old.empty: st.error(f"{len(old)} antiguos"); st.dataframe(old[['D','Marca','Modelo']])
        else: st.success("Stock fresco.")
