import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas App", layout="wide", page_icon="👟")

# --- LISTAS BASE (Estas siempre estarán, el resto las aprende del Excel) ---
BASES_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell"]
BASES_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted"]

# --- LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
def check_password():
    if st.session_state.password_input == "1234": st.session_state['autenticado'] = True
    else: st.error("🚫 Incorrecto")

if not st.session_state['autenticado']:
    st.title("🔒 Acceso Vinchy Zapas") # CAMBIO DE NOMBRE AQUÍ
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
                
                df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], dayfirst=True, errors='coerce')
                df['Fecha Venta'] = pd.to_datetime(df['Fecha Venta'], dayfirst=True, errors='coerce')
                df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
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
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())

# --- GENERADOR DE LISTAS INTELIGENTES ---
def obtener_listas_actualizadas(df):
    # Cogemos las marcas que ya existen en el Excel
    marcas_en_db = df['Marca'].unique().tolist() if 'Marca' in df.columns else []
    tiendas_en_db = df['Tienda Origen'].unique().tolist() if 'Tienda Origen' in df.columns else []
    
    # Las mezclamos con las básicas y quitamos duplicados
    lista_marcas = sorted(list(set(BASES_MARCAS + marcas_en_db + ["OTRA (Escribir nueva)"])))
    lista_tiendas = sorted(list(set(BASES_TIENDAS + tiendas_en_db + ["OTRA (Escribir nueva)"])))
    
    # Movemos "OTRA" al final siempre
    if "OTRA (Escribir nueva)" in lista_marcas:
        lista_marcas.remove("OTRA (Escribir nueva)")
        lista_marcas.append("OTRA (Escribir nueva)")
        
    if "OTRA (Escribir nueva)" in lista_tiendas:
        lista_tiendas.remove("OTRA (Escribir nueva)")
        lista_tiendas.append("OTRA (Escribir nueva)")
        
    return lista_marcas, lista_tiendas

# --- GESTIÓN DE ESTADO ---
keys = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio', 'k_marca_otro', 'k_tienda_otro']
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys: 
        if k in st.session_state: st.session_state[k] = 0.0 if 'precio' in k else ""
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

# Generamos las listas inteligentes
mis_marcas, mis_tiendas = obtener_listas_actualizadas(df)

# ---------------------------------------------------------
# 1. NUEVO PRODUCTO
# ---------------------------------------------------------
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: 
        st.success("✅ Guardado correctamente"); st.session_state['ok']=False

    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        # MARCA INTELIGENTE
        marca_sel = c1.selectbox("Marca", mis_marcas, key="k_marca")
        marca_final = marca_sel
        if marca_sel == "OTRA (Escribir nueva)":
            marca_final = c1.text_input("Escribe la nueva Marca:", key="k_marca_otro")
        
        modelo = c2.text_input("Modelo", key="k_modelo")

        c3, c4, c5 = st.columns(3)
        # TIENDA INTELIGENTE
        tienda_sel = c3.selectbox("Tienda", mis_tiendas, key="k_tienda")
        tienda_final = tienda_sel
        if tienda_sel == "OTRA (Escribir nueva)":
            tienda_final = c3.text_input("Escribe la nueva Tienda:", key="k_tienda_otro")

        talla = c4.text_input("Talla", key="k_talla")
        precio = c5.number_input("Precio Compra (€)", min_value=0.0, step=0.01, key="k_precio")
        
        if st.form_submit_button("GUARDAR EN STOCK", use_container_width=True):
            if not marca_final or not modelo: st.error("Falta Marca o Modelo")
            else:
                nid = 1 if df.empty else df['ID'].max()+1
                # Normalizar texto (Primera mayúscula)
                marca_final = marca_final.strip().title()
                tienda_final = tienda_final.strip().title()
                
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, "Marca":marca_final, "Modelo":modelo, "Talla":talla, "Tienda Origen":tienda_final, "Plataforma Venta":"", "Cuenta Venta":"", "Precio Compra":precio, "Precio Venta":0.0, "Estado":"En Stock", "Ganancia Neta":0.0, "ROI %":0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df)
                st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

# ---------------------------------------------------------
# 2. VENDER
# ---------------------------------------------------------
elif op == "💸 Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    if dfs.empty: st.warning("No tienes stock.")
    else:
        opciones = ["Seleccionar..."] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist()
        sel = st.selectbox("Busca lo que vas a vender:", opciones)
        
        if sel != "Seleccionar...":
            ids = int(float(sel.split(" |")[0].replace("ID:","")))
            row = df[df['ID']==ids].iloc[0]
            st.info(f"VENDIENDO: **{row['Marca']} {row['Modelo']}**")
            with st.form("fv"):
                pv=st.number_input("Precio Venta €", min_value=0.0, step=0.01)
                c3,c4=st.columns(2)
                plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"]); cta=c4.text_input("Cuenta Venta")
                if st.form_submit_button("CONFIRMAR VENTA", use_container_width=True):
                    idx=df.index[df['ID']==ids][0]
                    g=pv-row['Precio Compra']
                    df.at[idx,'Estado']='Vendido'; df.at[idx,'Fecha Venta']=datetime.now(); df.at[idx,'Precio Venta']=pv; df.at[idx,'Plataforma Venta']=plat; df.at[idx,'Cuenta Venta']=cta; df.at[idx,'Ganancia Neta']=g
                    coste = row['Precio Compra']; df.at[idx,'ROI %']=(g/coste*100) if coste > 0 else 0
                    guardar_datos(df); st.balloons(); st.success("¡Vendido!"); st.rerun()

# ---------------------------------------------------------
# 3. HISTORIAL (NUEVO BORRADO)
# ---------------------------------------------------------
elif op == "📦 Historial":
    st.title("📦 Historial")
    
    # --- SISTEMA DE BORRADO SEGURO ---
    st.markdown("### 🗑️ Eliminar Producto")
    col_borrar_1, col_borrar_2 = st.columns([3, 1])
    
    # Buscador de ID para borrar
    lista_para_borrar = ["Seleccionar ID para borrar..."] + df.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Estado']})", axis=1).tolist()
    
    with col_borrar_1:
        seleccion_borrar = st.selectbox("Busca el número (ID) o nombre:", lista_para_borrar, label_visibility="collapsed")
    
    with col_borrar_2:
        # El botón solo aparece si has elegido algo
        if seleccion_borrar != "Seleccionar ID para borrar...":
            if st.button("🗑️ ELIMINAR", type="primary"):
                id_
