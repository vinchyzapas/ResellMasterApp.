
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Vinchy Zapas V22", layout="wide", page_icon="👟")

# --- LISTAS BASE (Marcas que siempre estarán) ---
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
                # Limpiar espacios en blanco de marcas y tiendas para que no se dupliquen
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
        dfs = dfs.fillna("")
        sheet.clear()
        sheet.update([dfs.columns.values.tolist()] + dfs.values.tolist())

# --- GENERADOR DE LISTAS QUE APRENDEN ---
def obtener_listas_actualizadas(df):
    # 1. Leemos lo que ya hay guardado en el Excel
    marcas_guardadas = []
    tiendas_guardadas = []
    
    if not df.empty:
        if 'Marca' in df.columns:
            marcas_guardadas = df['Marca'].unique().tolist()
        if 'Tienda Origen' in df.columns:
            tiendas_guardadas = df['Tienda Origen'].unique().tolist()
    
    # 2. Juntamos con las básicas y quitamos vacíos
    todas_marcas = list(set(BASES_MARCAS + marcas_guardadas))
    todas_tiendas = list(set(BASES_TIENDAS + tiendas_guardadas))
    
    # 3. Limpiamos y Ordenamos alfabéticamente
    todas_marcas = sorted([m for m in todas_marcas if str(m).strip() != "" and str(m) != "nan"])
    todas_tiendas = sorted([t for t in todas_tiendas if str(t).strip() != "" and str(t) != "nan"])
    
    return todas_marcas, todas_tiendas

# --- GESTIÓN DE ESTADO ---
keys = ['k_marca_sel', 'k_marca_txt', 'k_modelo', 'k_tienda_sel', 'k_tienda_txt', 'k_talla', 'k_precio']
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

# GENERAMOS LAS LISTAS CON LO APRENDIDO
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
        
        # --- ZONA MARCA (HÍBRIDA) ---
        with c1:
            marca_sel = st.selectbox("Marca (Seleccionar)", ["- Seleccionar -"] + mis_marcas, key="k_marca_sel")
            marca_txt = st.text_input("¿Es nueva? Escríbela aquí:", key="k_marca_txt", placeholder="Ej: Converse")
            
            # Lógica: Si escribe texto, gana el texto. Si no, gana el selector.
            marca_final = marca_txt if marca_txt else marca_sel
            if marca_final == "- Seleccionar -": marca_final = ""

        # --- MODELO ---
        modelo = c2.text_input("Modelo", key="k_modelo")

        c3, c4, c5 = st.columns(3)
        
        # --- ZONA TIENDA (HÍBRIDA) ---
        with c3:
            tienda_sel = st.selectbox("Tienda (Seleccionar)", ["- Seleccionar -"] + mis_tiendas, key="k_tienda_sel")
            tienda_txt = st.text_input("¿Nueva? Escríbela aquí:", key="k_tienda_txt")
            
            tienda_final = tienda_txt if tienda_txt else tienda_sel
            if tienda_final == "- Seleccionar -": tienda_final = ""

        talla = c4.text_input("Talla", key="k_talla")
        precio = c5.number_input("Precio Compra (€)", min_value=0.0, step=0.01, key="k_precio")
        
        if st.form_submit_button("GUARDAR EN STOCK", use_container_width=True):
            if not marca_final or not modelo: 
                st.error("⚠️ Falta poner la Marca o el Modelo")
            else:
                nid = 1 if df.empty else df['ID'].max()+1
                
                # Normalizamos (Ponemos mayúscula inicial)
                marca_final = str(marca_final).strip().title()
                tienda_final = str(tienda_final).strip().title()
                
                new = {"ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, 
                       "Marca":marca_final, "Modelo":modelo, "Talla":talla, 
                       "Tienda Origen":tienda_final, "Plataforma Venta":"", "Cuenta Venta":"", 
                       "Precio Compra":precio, "Precio Venta":0.0, "Estado":"En Stock", 
                       "Ganancia Neta":0.0, "ROI %":0.0}
                
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
# 3. HISTORIAL (BORRADO FÁCIL)
# ---------------------------------------------------------
elif op == "📦 Historial":
    st.title("📦 Historial")
    
    # --- ZONA BORRADO ---
    with st.expander("🗑️ ELIMINAR UN PRODUCTO"):
        st.write("Selecciona el ID que quieres borrar:")
        lista_borrar = ["- Elegir -"] + df.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']}", axis=1).tolist()
        seleccion_borrar = st.selectbox("Buscar zapatilla:", lista_borrar)
        
        if seleccion_borrar != "- Elegir -":
            id_b = int(seleccion_borrar.split(" |")[0].replace("ID:", ""))
            if st.button(f"🗑️ BORRAR ID {id_b}", type="primary"):
                df_nuevo = df[df['ID'] != id_b]
                guardar_datos(df_nuevo)
                st.success(f"ID {id_b} eliminado."); st.rerun()

    # --- TABLA ---
    col_config = {"Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"), "Precio Compra": st.column_config.NumberColumn(format="%.2f €"), "Precio Venta": st.column_config.NumberColumn(format="%.2f €"), "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €"), "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]), "ID": st.column_config.NumberColumn(disabled=True)}
    df_editado = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="fixed", use_container_width=True)
    if not df.equals(df_editado):
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
        guardar_datos(df_editado); st.toast("✅ Actualizado"); st.rerun()

# ---------------------------------------------------------
# 4. FINANZAS
# ---------------------------------------------------------
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        k1.metric("Beneficio Neto", f"{sold['Ganancia Neta'].sum():.2f} €")
        k2.metric("Gasto Stock", f"{df['Precio Compra'].sum():.2f} €")
        st.divider()
        st.subheader("Gasto por Tienda"); st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        st.subheader("Beneficio por Plataforma"); st.bar_chart(sold.groupby('Plataforma Venta')['Ganancia Neta'].sum())
