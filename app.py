import streamlit as st
import pandas as pd
import os
import pdfplumber
import easyocr
import re
from datetime import datetime, timedelta
from PIL import Image
import numpy as np
import ssl

# --- SOLUCIÓN ERROR SSL ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Resell Master V11.2", layout="wide", page_icon="👟")
DATA_FILE = 'mi_inventario_zapatillas.csv'

# --- DEFINICIÓN DE CLAVES DEL FORMULARIO ---
keys_formulario = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio']

# --- LÓGICA DE LIMPIEZA (LA SOLUCIÓN AL ERROR ROJO) ---
# Esto se ejecuta ANTES de pintar nada en pantalla
if 'limpiar_ahora' in st.session_state and st.session_state['limpiar_ahora']:
    for key in keys_formulario:
        if 'precio' in key:
            st.session_state[key] = 0.0
        else:
            st.session_state[key] = ""
    st.session_state['limpiar_ahora'] = False # Apagamos la señal

# Inicializar variables si están vacías
for key in keys_formulario:
    if key not in st.session_state:
        st.session_state[key] = 0.0 if 'precio' in key else ""

# --- CARGA OCR ---
@st.cache_resource
def cargar_lector_ocr():
    return easyocr.Reader(['es', 'en']) 
try: reader = cargar_lector_ocr()
except: reader = None

# --- CARGA DATOS ---
def cargar_datos():
    columnas_base = [
        "ID", "Fecha Compra", "Fecha Venta", "Marca", "Modelo", "Talla", "Tienda Origen", 
        "Plataforma Venta", "Cuenta Venta", "Precio Compra", "Precio Venta", "Gastos Extra", 
        "Estado", "Ganancia Neta", "ROI %", "Ruta Archivo"
    ]
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            for col in columnas_base:
                if col not in df.columns:
                    df[col] = 0.0 if "Precio" in col or "Gasto" in col or "ROI" in col else ""
            
            df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], errors='coerce')
            df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], errors='coerce')
            df['Ruta Archivo'] = df['Ruta Archivo'].astype(str).replace('nan', '')
            df['Gastos Extra'] = df['Gastos Extra'].fillna(0.0)
            df['Talla'] = df['Talla'].astype(str).replace('nan', '')
            df['Tienda Origen'] = df['Tienda Origen'].astype(str).replace('nan', '')
            df['Cuenta Venta'] = df['Cuenta Venta'].astype(str).replace('nan', '')
            
            # Asegurar ID entero
            df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
            
            return df[columnas_base]
        except: pass
    return pd.DataFrame(columns=columnas_base)

def guardar_datos(df):
    df.to_csv(DATA_FILE, index=False)

# --- PROCESAMIENTO INTELIGENTE ---
def procesar_texto_inteligente(texto):
    datos = {"marca": "", "modelo": "", "talla": "", "precio": 0.0, "tienda": ""}
    texto_upper = texto.upper()
    
    marcas = ["THE NORTH FACE", "NEW BALANCE", "NIKE", "ADIDAS", "JORDAN", "PUMA", "ASICS", "SALOMON", "HOKA", "VEJA", "CROCS", "ON", "ZARA", "BERSHKA", "DR MARTENS", "TIMBERLAND", "UGG"]
    for m in marcas:
        if re.search(r'\b' + re.escape(m) + r'\b', texto_upper):
            datos["marca"] = m.title()
            texto_upper = texto_upper.replace(m, "")
            break
            
    match_precio = re.search(r'(\d+[.,]?\d*)\s?([€]|EUR|EUROS)', texto, re.IGNORECASE)
    if match_precio:
        p = match_precio.group(1).replace(',', '.')
        try: datos["precio"] = float(p)
        except: pass
    
    match_talla = re.search(r'(TALLA|SIZE|NUMERO)\s?(\d{2}\.?5?|XL|XXL|L|M|S)', texto_upper)
    if match_talla:
        datos["talla"] = match_talla.group(2)
    else:
        match_talla_suelta = re.search(r'\b(3[5-9]|[4][0-9])\.?5?\b', texto_upper)
        if match_talla_suelta: datos["talla"] = match_talla_suelta.group(0)

    match_tienda = re.search(r'(EN|DE)\s+([A-Z0-9]+)', texto_upper)
    if match_tienda:
        posibles_tiendas = ["PRIVALIA", "ZALANDO", "FOOTLOCKER", "NIKE", "ADIDAS", "VINTED", "WALLAPOP", "ASFAGOL", "JD", "SNIPES"]
        encontrada = False
        for t in posibles_tiendas:
            if t in texto_upper:
                datos["tienda"] = t.title()
                encontrada = True
                break
        if not encontrada:
             datos["tienda"] = match_tienda.group(2).title()

    palabras_borrar = ["COMPRADA", "EN", "POR", "EUROS", "EUR", "€", "TALLA", "SIZE", "LA", "EL", "UNAS", "DE"]
    texto_limpio = texto_upper
    for p in palabras_borrar: texto_limpio = texto_limpio.replace(p, "")
    if datos["marca"]: texto_limpio = texto_limpio.replace(datos["marca"].upper(), "")
    if datos["talla"]: texto_limpio = texto_limpio.replace(str(datos["talla"]), "")
    if datos["tienda"]: texto_limpio = texto_limpio.replace(datos["tienda"].upper(), "")
    if datos["precio"] > 0: texto_limpio = re.sub(r'\d+[.,]?\d*', '', texto_limpio)
    
    datos["modelo"] = re.sub(r'\s+', ' ', texto_limpio).strip().title()
    return datos

def procesar_archivo(uploaded_file):
    if not os.path.exists("comprobantes"): os.makedirs("comprobantes")
    ruta = os.path.join("comprobantes", uploaded_file.name)
    with open(ruta, "wb") as f: f.write(uploaded_file.getbuffer())

    texto = ""
    try:
        if uploaded_file.type == "application/pdf":
            with pdfplumber.open(ruta) as pdf:
                for page in pdf.pages: texto += page.extract_text() + "\n"
        else:
            if reader:
                image = Image.open(ruta)
                texto = "\n".join(reader.readtext(np.array(image), detail=0))
    except Exception: return ruta, ""
    return ruta, texto

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú")
opcion = st.sidebar.radio("Ir a:", ["👟 Agregar (Voz/Foto)", "💸 Registrar Venta", "📦 Historial", "📊 Finanzas", "🚨 Alertas Stock"])

df = cargar_datos()

# --- 1. AGREGAR ---
if opcion == "👟 Agregar (Voz/Foto)":
    st.title("👟 Nueva Compra")
    st.info("🎙️ Escribe o dicta: 'Marca Modelo Talla Tienda Precio'")
    
    # MENSAJE DE EXITO (Si venimos de guardar)
    if 'guardado_ok' in st.session_state and st.session_state['guardado_ok']:
        st.success("✅ ¡Guardado con éxito!")
        st.session_state['guardado_ok'] = False

    texto_voz = st.text_area("Dictado Inteligente:", height=70, placeholder="Ej: Nike Dunk Panda talla 44 comprada en Footlocker por 110 euros")
    if st.button("⚡ Procesar Texto"):
        if texto_voz:
            datos = procesar_texto_inteligente(texto_voz)
            st.session_state['k_marca'] = datos["marca"]
            st.session_state['k_modelo'] = datos["modelo"]
            st.session_state['k_talla'] = datos["talla"]
            st.session_state['k_precio'] = datos["precio"]
            st.session_state['k_tienda'] = datos["tienda"]
            st.toast("Datos rellenados")

    st.markdown("---")
    uploaded_file = st.file_uploader("O subir Foto", type=['pdf', 'png', 'jpg', 'jpeg'], key="uploader")
    ruta_archivo = ""
    if uploaded_file:
        with st.spinner('Leyendo...'):
            ruta_archivo, texto = procesar_archivo(uploaded_file)
            datos = procesar_texto_inteligente(texto)
            if not st.session_state['k_marca']: st.session_state['k_marca'] = datos["marca"]
            if not st.session_state['k_precio']: st.session_state['k_precio'] = datos["precio"]

    with st.form("form_compra"):
        c1, c2 = st.columns([1, 2])
        in_marca = c1.text_input("Marca", key="k_marca")
        in_modelo = c2.text_input("Modelo", key="k_modelo")
        c3, c4, c5 = st.columns(3)
        in_tienda = c3.text_input("Tienda Origen", key="k_tienda")
        in_talla = c4.text_input("Talla", key="k_talla")
        in_precio = c5.number_input("Precio Compra (€)", step=0.01, key="k_precio")
        
        if st.form_submit_button("💾 GUARDAR", use_container_width=True):
            nuevo_id = 1 if df.empty else df['ID'].max() + 1
            nueva_fila = {
                "ID": nuevo_id, "Fecha Compra": datetime.now(), "Fecha Venta": pd.NaT,
                "Marca": in_marca, "Modelo": in_modelo, "Talla": in_talla, "Tienda Origen": in_tienda,
                "Plataforma Venta": "", "Cuenta Venta": "", "Precio Compra": in_precio,
                "Precio Venta": 0.0, "Gastos Extra": 0.0, "Estado": "En Stock", "Ganancia Neta": 0.0, "ROI %": 0.0, "Ruta Archivo": ruta_archivo
            }
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            guardar_datos(df)
            
            # ACTIVAMOS LA SEÑAL DE LIMPIEZA
            st.session_state['limpiar_ahora'] = True
            st.session_state['guardado_ok'] = True # Para mostrar el mensaje verde
            st.rerun()

# --- 2. VENDER ---
elif opcion == "💸 Registrar Venta":
    st.title("💸 Vender")
    df_stock = df[df['Estado'] == 'En Stock'].copy()
    if df_stock.empty: st.warning("No hay stock.")
    else:
        df_stock['Display'] = df_stock.apply(lambda x: f"ID:{int(x['ID'])} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1)
        seleccion = st.selectbox("Elegir Zapatilla:", df_stock['Display'].tolist())
        if seleccion:
            try:
                id_texto = seleccion.split(" |")[0].replace("ID:", "")
                id_sel = int(float(id_texto))
            except: id_sel = 0
                
            fila = df[df['ID'] == id_sel].iloc[0]
            st.write(f"Vender: **{fila['Marca']} {fila['Modelo']}**")
            
            with st.form("f_venta"):
                c1,c2 = st.columns(2)
                pv = c1.number_input("Precio Venta (€)", step=0.01)
                gastos = c2.number_input("Gastos", step=0.01)
                c3,c4 = st.columns(2)
                plat = c3.selectbox("Plataforma", ["Vinted", "Wallapop", "StockX", "En Mano"])
                cta = c4.text_input("Cuenta")
                if st.form_submit_button("CONFIRMAR VENTA", use_container_width=True):
                    idx = df.index[df['ID']==id_sel][0]
                    g = pv - fila['Precio Compra'] - gastos
                    df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now()
                    df.at[idx,'Precio Venta']=pv; df.at[idx,'Gastos Extra']=gastos
                    df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta
                    df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=(g/(fila['Precio Compra']+gastos)*100) if fila['Precio Compra']>0 else 0
                    guardar_datos(df); st.success("Vendido!"); st.rerun()

# --- 3. HISTORIAL ---
elif opcion == "📦 Historial":
    st.title("Inventario Completo")
    st.data_editor(df, hide_index=True, num_rows="dynamic")

# --- 4. FINANZAS ---
elif opcion == "📊 Finanzas":
    st.title("Finanzas")
    if not df.empty:
        df_sold = df[df['Estado'] == 'Vendido']
        k1, k2 = st.columns(2)
        k1.metric("Beneficio Neto", f"{df_sold['Ganancia Neta'].sum():.2f} €")
        k2.metric("Gasto en Compras", f"{df['Precio Compra'].sum():.2f} €")
        st.subheader("Gastos por Tienda")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())

# --- 5. ALERTAS ---
elif opcion == "🚨 Alertas Stock":
    st.title("Alertas")
    if not df.empty:
        hoy = datetime.now()
        df_stock = df[df['Estado'] == 'En Stock'].copy()
        df_stock['Días'] = (hoy - df_stock['Fecha Compra']).dt.days
        old = df_stock[df_stock['Días'] >= 30]
        if not old.empty:
            st.error(f"Tienes {len(old)} artículos con +30 días:")
            st.dataframe(old[['Días', 'Marca', 'Modelo', 'Precio Compra']], hide_index=True)
        else:
            st.success("Tu stock es reciente.")