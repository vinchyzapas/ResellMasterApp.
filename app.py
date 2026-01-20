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
from pyzbar.pyzbar import decode # LIBRERÍA NUEVA PARA CÓDIGOS DE BARRAS

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Resell Master V15", layout="wide", page_icon="🦓")

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
    # AÑADIMOS COLUMNA 'Codigo Barras'
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
                # El código de barras debe ser texto para que no pierda ceros
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
keys_form = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio', 'k_barras'] # Añadido k_barras
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys_form: st.session_state[k] = 0.0 if 'precio' in k else ""
    st.session_state['limpiar'] = False
for k in keys_form:
    if k not in st.session_state: st.session_state[k] = 0.0 if 'precio' in k else ""

# --- OCR Y LECTOR DE BARRAS ---
@st.cache_resource
def cargar_ocr(): return easyocr.Reader(['es','en'])
try: reader = cargar_ocr()
except: reader = None

def procesar_imagen_completa(file):
    """
    Esta función hace 2 cosas:
    1. Lee el texto (OCR)
    2. Busca códigos de barras en la imagen
    """
    img = Image.open(file)
    img_np = np.array(img)
    
    # 1. BUSCAR CÓDIGO DE BARRAS
    codigo_barras = ""
    codigos_encontrados = decode(img) # Escanea la imagen buscando barras
    if codigos_encontrados:
        # Cogemos el primero que encuentre
        codigo_barras = codigos_encontrados[0].data.decode("utf-8")
    
    # 2. LEER TEXTO (OCR)
    texto_ocr = ""
    if reader:
        texto_ocr = "\n".join(reader.readtext(img_np, detail=0))
        
    return texto_ocr, codigo_barras

def procesar_texto(texto):
    d = {"marca":"", "modelo":"", "talla":"", "precio":0.0, "tienda":""}
    txt = texto.upper()
    marcas = ["NIKE", "ADIDAS", "JORDAN", "NEW BALANCE", "ASICS", "PUMA", "SALOMON", "HOKA", "VEJA", "CROCS", "ON", "ZARA", "BERSHKA", "DR MARTENS", "UGG", "THE NORTH FACE", "TIMBERLAND", "CONVERSE", "VANS"]
    for m in marcas:
        if re.search(r'\b'+re.escape(m)+r'\b', txt): 
            d["marca"]=m.title(); txt=txt.replace(m, ""); break
    
    mp = re.search(r'(\d+[.,]?\d*)\s?([€]|EUR)', texto, re.IGNORECASE)
    if mp: 
        d["precio"] = float(mp.group(1).replace(',', '.'))
        txt = txt.replace(mp.group(0), "") 

    match_t = re.search(r'(TALLA|SIZE|NUMERO|UK|US|CM)\s?(\d{1,2}\.?5?|XL|L|M|S|XS)', txt)
    if match_t: 
        d["talla"]=match_t.group(2)
        txt = txt.replace(match_t.group(0), "")
    else: 
        mts = re.search(r'\b(3[5-9]|[4][0-9])\.?5?\b', txt)
        if mts: d["talla"]=mts.group(0); txt = txt.replace(mts.group(0), "")

    mti = re.search(r'(EN|DE|COMPRADA EN)\s+([A-Z0-9]+)', txt)
    tiendas_comunes = ["ZALANDO", "PRIVALIA", "FOOTLOCKER", "VINTED", "WALLAPOP", "ASFAGOL", "NIKE", "ADIDAS", "SNIPES", "JD", "CORTE INGLES"]
    for t in tiendas_comunes:
        if t in txt: d["tienda"] = t.title(); txt = txt.replace(t, ""); break
    if not d["tienda"] and mti: d["tienda"] = mti.group(2).title(); txt = txt.replace(mti.group(0), "")
    
    borrar = ["COMPRADA", "EN", "POR", "EUROS", "EUR", "€", "TALLA", "SIZE", "LA", "EL", "UNAS", "LOS", "ZAPATILLA", "ZAPATILLAS", "MODELO", "DE", "BOX", "ORIGINAL"]
    for b in borrar: txt = re.sub(r'\b'+re.escape(b)+r'\b', "", txt)
    d["modelo"] = re.sub(r'\s+', ' ', txt).strip().title()
    return d

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú V15")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender (Escáner)", "📦 Historial", "📊 Finanzas", "🚨 Alertas"])
df = cargar_datos()

# ---------------------------------------------------------
# 1. NUEVO PRODUCTO (Escanea Caja Completa)
# ---------------------------------------------------------
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']:
        st.success("✅ Guardado en la nube"); st.session_state['ok']=False

    st.info("📸 **Haz una foto a la ETIQUETA de la caja.** Intentaré leer Marca, Modelo, Talla y **Código de Barras**.")

    up = st.file_uploader("Subir Foto Caja", type=['jpg','png','jpeg'])
    
    if up:
        with st.spinner("Analizando etiqueta y buscando código de barras..."):
            txt, barras = procesar_imagen_completa(up)
            
            # Procesamos el texto
            d = procesar_texto(txt)
            
            # Rellenamos sesión
            st.session_state['k_marca'] = d["marca"]
            st.session_state['k_modelo'] = d["modelo"] # El modelo saldrá de lo que lea en la etiqueta
            st.session_state['k_talla'] = d["talla"]
            # El precio no suele venir en la etiqueta de la caja, hay que ponerlo a mano
            
            if barras:
                st.session_state['k_barras'] = barras
                st.toast(f"🦓 ¡Código de barras detectado! {barras}")
            else:
                st.toast("Texto leído, pero no veo código de barras.")

    with st.form("fc"):
        c1,c2=st.columns([1,2]); m=c1.text_input("Marca", key="k_marca"); mod=c2.text_input("Modelo", key="k_modelo")
        c3,c4,c5=st.columns(3); td=c3.text_input("Tienda", key="k_tienda"); ta=c4.text_input("Talla", key="k_talla"); pr=c5.number_input("Precio Compra (€)", key="k_precio")
        
        # CAMPO OCULTO/VISUAL DEL CÓDIGO DE BARRAS
        # Lo mostramos desactivado para que sepas que está ahí, pero no hace falta tocarlo
        barras_input = st.text_input("Código de Barras (Detectado autom.)", key="k_barras", disabled=True)
        
        if st.form_submit_button("GUARDAR EN STOCK"):
            nid = 1 if df.empty else df['ID'].max()+1
            # Guardamos el código de barras en la base de datos
            new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":m, "Modelo":mod, "Talla":ta, "Codigo Barras":st.session_state['k_barras'], 
                   "Tienda Origen":td, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":pr, "Precio Venta":0.0, "Gastos Extra":0.0, 
                   "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0, "Ruta Archivo":""}
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            guardar_datos(df)
            st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

# ---------------------------------------------------------
# 2. VENDER (POR ESCÁNER)
# ---------------------------------------------------------
elif op == "💸 Vender (Escáner)":
    st.title("💸 Vender por Código de Barras")
    
    # Opción A: Escanear
    st.write("🦓 **Sube foto del código de barras para encontrar la zapatilla:**")
    scan_up = st.file_uploader("Escanear Barras", type=['jpg','png','jpeg'], key="vender_scan")
    
    zapatilla_encontrada = None
    
    if scan_up:
        with st.spinner("Buscando en tu stock..."):
            # Usamos una imagen temporal en memoria para decode
            img_scan = Image.open(scan_up)
            codigos = decode(img_scan)
            
            if codigos:
                code_leido = codigos[0].data.decode("utf-8")
                st.success(f"Leído: {code_leido}")
                
                # BUSCAR EN EL DATAFRAME
                # Buscamos coincidencias en stock con ese código
                encontrados = df[(df['Codigo Barras'] == code_leido) & (df['Estado'] == 'En Stock')]
                
                if not encontrados.empty:
                    zapatilla_encontrada = encontrados.iloc[0]
                else:
                    st.error("❌ Código leído, pero no está en tu Stock (o ya se vendió).")
            else:
                st.warning("No pude leer el código. Intenta que se vea claro y plano.")

    st.divider()
    
    # Opción B: Si no escanea, búsqueda manual (Fallback)
    if zapatilla_encontrada is None:
        st.write("...o busca manualmente:")
        dfs = df[df['Estado']=='En Stock'].copy()
        if not dfs.empty:
            dfs['D'] = dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1)
            sel = st.selectbox("Elegir:", ["Seleccionar..."] + dfs['D'].tolist())
            if sel and sel != "Seleccionar...":
                ids = int(float(sel.split(" |")[0].replace("ID:","")))
                zapatilla_encontrada = df[df['ID']==ids].iloc[0]

    # FORMULARIO DE VENTA (Solo sale si encontramos zapatilla)
    if zapatilla_encontrada is not None:
        row = zapatilla_encontrada
        st.markdown(f"### ✅ Vendiendo: {row['Marca']} {row['Modelo']}")
        st.markdown(f"Talla: **{row['Talla']}** | Comprado: **{row['Precio Compra']}€**")
        
        with st.form("fv"):
            pv=st.number_input("Precio Venta €", min_value=0.0, step=0.01)
            c3,c4=st.columns(2)
            plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta")
            
            if st.form_submit_button("CONFIRMAR VENTA"):
                idx = df.index[df['ID'] == row['ID']].tolist()[0]
                g = pv - row['Precio Compra']
                df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now()
                df.at[idx,'Precio Venta']=pv; df.at[idx,'Gastos Extra']=0.0
                df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta
                df.at[idx,'Ganancia Neta']=g; df.at[idx,'ROI %']=(g/row['Precio Compra']*100) if row['Precio Compra']>0 else 0
                guardar_datos(df)
                st.balloons()
                st.success("¡Venta Realizada!")
                st.rerun()

elif op == "📦 Historial (Editable)":
    st.title("Historial")
    col_config = {
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]),
        "ID": st.column_config.NumberColumn(disabled=True),
        "Codigo Barras": st.column_config.TextColumn(disabled=True)
    }
    df_editado = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="dynamic", use_container_width=True)
    if not df.equals(df_editado):
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra'] - df_editado['Gastos Extra']
        guardar_datos(df_editado); st.toast("✅ Guardado"); st.rerun()

elif op == "📊 Finanzas":
    st.title("Finanzas")
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        k1.metric("Beneficio Neto", f"{sold['Ganancia Neta'].sum():.2f} €")
        k2.metric("Gasto Total", f"{df['Precio Compra'].sum():.2f} €")
        st.subheader("Gasto por Tienda")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())

elif op == "🚨 Alertas":
    st.title("Alertas")
    if not df.empty:
        ds = df[df['Estado']=='En Stock'].copy()
        ds['D'] = (datetime.now() - ds['Fecha Compra']).dt.days
        old = ds[ds['D']>=30]
        if not old.empty: st.error(f"{len(old)} artículos +30 días"); st.dataframe(old[['D','Marca','Modelo']])
        else: st.success("Todo fresco.")
