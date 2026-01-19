import streamlit as st
import pandas as pd
import pdfplumber
import easyocr
import re
from datetime import datetime
from PIL import Image
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Resell Master Cloud", layout="wide", page_icon="☁️")

# --- CONEXIÓN GOOGLE SHEETS ---
def conectar_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Usamos los secretos de Streamlit
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("inventario_zapatillas").sheet1
    except Exception as e:
        return None

# --- CARGAR DATOS (DESDE LA NUBE) ---
def cargar_datos():
    columnas = ["ID", "Fecha Compra", "Fecha Venta", "Marca", "Modelo", "Talla", "Tienda Origen", 
                "Plataforma Venta", "Cuenta Venta", "Precio Compra", "Precio Venta", "Gastos Extra", 
                "Estado", "Ganancia Neta", "ROI %", "Ruta Archivo"]
    
    sheet = conectar_sheets()
    if sheet:
        try:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                # Asegurar columnas
                for col in columnas:
                    if col not in df.columns: df[col] = 0.0 if "Precio" in col else ""
                
                # Formatos
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
                return df[columnas]
        except: pass
    
    return pd.DataFrame(columns=columnas)

# --- GUARDAR DATOS (EN LA NUBE) ---
def guardar_datos(df):
    sheet = conectar_sheets()
    if sheet:
        df_save = df.copy()
        # Convertir fechas a texto para Google Sheets
        df_save['Fecha Compra'] = df_save['Fecha Compra'].astype(str).replace('NaT', '')
        df_save['Fecha Venta'] = df_save['Fecha Venta'].astype(str).replace('NaT', '')
        df_save = df_save.fillna("")
        
        sheet.clear()
        # Subir cabeceras y datos
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())

# --- GESTIÓN DE ESTADO ---
keys_form = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio']
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

# --- PROCESAMIENTO INTELIGENTE ---
def procesar_texto(texto):
    d = {"marca":"", "modelo":"", "talla":"", "precio":0.0, "tienda":""}
    txt = texto.upper()
    marcas = ["NIKE", "ADIDAS", "JORDAN", "NEW BALANCE", "ASICS", "PUMA", "SALOMON", "HOKA", "VEJA", "CROCS", "ON", "ZARA", "BERSHKA", "DR MARTENS", "UGG", "THE NORTH FACE"]
    for m in marcas:
        if re.search(r'\b'+re.escape(m)+r'\b', txt): d["marca"]=m.title(); txt=txt.replace(m,""); break
    
    mp = re.search(r'(\d+[.,]?\d*)\s?([€]|EUR)', texto, re.IGNORECASE)
    if mp: d["precio"] = float(mp.group(1).replace(',', '.'))
    
    mt = re.search(r'(TALLA|SIZE)\s?(\d{2}\.?5?|XL|L|M|S)', txt)
    if mt: d["talla"]=mt.group(2)
    else: 
        mts = re.search(r'\b(3[5-9]|[4][0-9])\.?5?\b', txt)
        if mts: d["talla"]=mts.group(0)
    
    mti = re.search(r'(EN|DE)\s+([A-Z0-9]+)', txt)
    if mti: d["tienda"] = mti.group(2).title()
    
    borrar = ["COMPRADA", "EN", "POR", "EUROS", "EUR", "€", "TALLA", "SIZE"]
    for b in borrar: txt=txt.replace(b,"")
    d["modelo"] = re.sub(r'\s+', ' ', txt).strip().title()
    return d

def procesar_archivo(file):
    txt = ""
    try:
        if file.type == "application/pdf":
            with pdfplumber.open(file) as pdf:
                for p in pdf.pages: txt += p.extract_text() + "\n"
        else:
            if reader:
                img = Image.open(file)
                txt = "\n".join(reader.readtext(np.array(img), detail=0))
    except: pass
    return txt

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú Cloud")
op = st.sidebar.radio("Ir a:", ["👟 Agregar", "💸 Vender", "📦 Historial", "📊 Finanzas", "🚨 Alertas"])
df = cargar_datos()

if op == "👟 Agregar":
    st.title("👟 Agregar (Nube)")
    if 'ok' in st.session_state and st.session_state['ok']:
        st.success("✅ Guardado en Google Sheets!"); st.session_state['ok']=False

    voz = st.text_area("Dictado:", height=70, placeholder="Ej: Nike Dunk talla 43 en Zalando 100 euros")
    if st.button("⚡ Procesar"):
        d = procesar_texto(voz)
        st.session_state['k_marca']=d["marca"]; st.session_state['k_modelo']=d["modelo"]
        st.session_state['k_talla']=d["talla"]; st.session_state['k_precio']=d["precio"]
        st.session_state['k_tienda']=d["tienda"]

    up = st.file_uploader("Foto", type=['jpg','png','pdf'])
    if up:
        txt = procesar_archivo(up)
        d = procesar_texto(txt)
        if not st.session_state['k_marca']: st.session_state['k_marca']=d["marca"]
        if not st.session_state['k_precio']: st.session_state['k_precio']=d["precio"]

    with st.form("fc"):
        c1,c2=st.columns([1,2]); m=c1.text_input("Marca", key="k_marca"); mod=c2.text_input("Modelo", key="k_modelo")
        c3,c4,c5=st.columns(3); td=c3.text_input("Tienda", key="k_tienda"); ta=c4.text_input("Talla", key="k_talla"); pr=c5.number_input("Precio", key="k_precio")
        if st.form_submit_button("GUARDAR"):
            nid = 1 if df.empty else df['ID'].max()+1
            new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":m, "Modelo":mod, "Talla":ta, "Tienda Origen":td, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":pr, "Precio Venta":0.0, "Gastos Extra":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0, "Ruta Archivo":""}
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            guardar_datos(df)
            st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

elif op == "💸 Vender":
    st.title("💸 Vender (Nube)")
    dfs = df[df['Estado']=='En Stock'].copy()
    if dfs.empty: st.warning("Sin stock.")
    else:
        dfs['D'] = dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1)
        sel = st.selectbox("Elegir:", dfs['D'])
        if sel:
            ids = int(float(sel.split(" |")[0].replace("ID:","")))
            row = df[df['ID']==ids].iloc[0]
            st.write(f"Vender: **{row['Marca']} {row['Modelo']}**")
            with st.form("fv"):
                pv=st.number_input("Venta €"); gas=st.number_input("Gastos €"); plat=st.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=st.text_input("Cuenta")
                if st.form_submit_button("VENDER"):
                    idx=df.index[df['ID']==ids][0]
                    g=pv-row['Precio Compra']-gas
                    df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now()
                    df.at[idx,'Precio Venta']=pv; df.at[idx,'Gastos Extra']=gas
                    df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta
                    df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=(g/(row['Precio Compra']+gas)*100) if row['Precio Compra']>0 else 0
                    guardar_datos(df); st.success("Vendido!"); st.rerun()

elif op == "📦 Historial":
    st.title("Historial (Google Sheets)")
    st.dataframe(df)

elif op == "📊 Finanzas":
    st.title("Finanzas Cloud")
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        k1.metric("Beneficio Neto", f"{sold['Ganancia Neta'].sum():.2f} €")
        k2.metric("Gasto Total", f"{df['Precio Compra'].sum():.2f} €")
        st.subheader("Gasto por Tienda")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())

elif op == "🚨 Alertas":
    st.title("Alertas Cloud")
    if not df.empty:
        ds = df[df['Estado']=='En Stock'].copy()
        ds['D'] = (datetime.now() - ds['Fecha Compra']).dt.days
        old = ds[ds['D']>=30]
        if not old.empty: st.error(f"{len(old)} artículos +30 días"); st.dataframe(old[['D','Marca','Modelo']])
        else: st.success("Todo fresco.")
