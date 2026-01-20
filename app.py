import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import ssl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Resell Master V20", layout="wide", page_icon="⚡")

# --- LISTAS PREDEFINIDAS (CONFIGURA AQUÍ TUS FAVORITAS) ---
LISTA_MARCAS = ["Adidas", "Nike", "Hoka", "Salomon", "Calvin Klein", "Asics", "New Balance", "Merrell", "Otras"]
LISTA_TIENDAS = ["Asos", "Asphaltgold", "Privalia", "Amazon", "Sneakersnuff", "Footlocker", "Zalando", "Vinted", "Otras"]

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
                return df[cols]
        except: pass
    return pd.DataFrame(columns=cols)

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

# --- GESTIÓN DE ESTADO (LIMPIEZA) ---
keys = ['k_marca', 'k_modelo', 'k_tienda', 'k_talla', 'k_precio', 'k_marca_otro', 'k_tienda_otro']
if 'limpiar' in st.session_state and st.session_state['limpiar']:
    for k in keys: 
        if k in st.session_state:
            st.session_state[k] = 0.0 if 'precio' in k else ""
    st.session_state['limpiar'] = False

# ==========================================
# INTERFAZ
# ==========================================
st.sidebar.title("Menú V20")
op = st.sidebar.radio("Ir a:", ["👟 Nuevo Producto", "💸 Vender", "📦 Historial", "📊 Finanzas"])
st.sidebar.divider()
if st.sidebar.button("🔒 Cerrar Sesión"): st.session_state['autenticado']=False; st.rerun()

df = cargar_datos()

# ---------------------------------------------------------
# 1. NUEVO PRODUCTO (RÁPIDO)
# ---------------------------------------------------------
if op == "👟 Nuevo Producto":
    st.title("👟 Nuevo Producto")
    if 'ok' in st.session_state and st.session_state['ok']: 
        st.success("✅ Guardado correctamente"); st.session_state['ok']=False

    with st.form("fc"):
        # MARCA (Desplegable)
        c1, c2 = st.columns([1, 2])
        marca_sel = c1.selectbox("Marca", LISTA_MARCAS, key="k_marca")
        marca_final = marca_sel
        if marca_sel == "Otras":
            marca_final = c1.text_input("Escribe la Marca", key="k_marca_otro")
        
        # MODELO
        modelo = c2.text_input("Modelo", key="k_modelo")

        # TIENDA (Desplegable)
        c3, c4, c5 = st.columns(3)
        tienda_sel = c3.selectbox("Tienda", LISTA_TIENDAS, key="k_tienda")
        tienda_final = tienda_sel
        if tienda_sel == "Otras":
            tienda_final = c3.text_input("Escribe la Tienda", key="k_tienda_otro")

        # TALLA Y PRECIO
        talla = c4.text_input("Talla", key="k_talla")
        precio = c5.number_input("Precio Compra (€)", min_value=0.0, step=0.01, key="k_precio")
        
        if st.form_submit_button("GUARDAR EN STOCK", use_container_width=True):
            if not marca_final or not modelo:
                st.error("Falta Marca o Modelo")
            else:
                nid = 1 if df.empty else df['ID'].max()+1
                new = {
                    "ID":nid, "Fecha Compra":datetime.now(), "Fecha Venta":pd.NaT, 
                    "Marca":marca_final, "Modelo":modelo, "Talla":talla, 
                    "Tienda Origen":tienda_final, "Plataforma Venta":"", "Cuenta Venta":"", 
                    "Precio Compra":precio, "Precio Venta":0.0, "Estado":"En Stock", 
                    "Ganancia Neta":0.0, "ROI %":0.0
                }
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                guardar_datos(df)
                st.session_state['limpiar']=True; st.session_state['ok']=True; st.rerun()

# ---------------------------------------------------------
# 2. VENDER
# ---------------------------------------------------------
elif op == "💸 Vender":
    st.title("💸 Vender")
    dfs = df[df['Estado']=='En Stock'].copy()
    if dfs.empty: st.warning("No tienes stock para vender.")
    else:
        # Buscador manual mejorado
        opciones = ["Seleccionar..."] + dfs.apply(lambda x: f"ID:{x['ID']} | {x['Marca']} {x['Modelo']} ({x['Talla']})", axis=1).tolist()
        sel = st.selectbox("Busca lo que vas a vender:", opciones)
        
        if sel != "Seleccionar...":
            ids = int(float(sel.split(" |")[0].replace("ID:","")))
            row = df[df['ID']==ids].iloc[0]
            
            st.info(f"VENDIENDO: **{row['Marca']} {row['Modelo']}**")
            with st.form("fv"):
                pv=st.number_input("Precio Venta €", min_value=0.0, step=0.01)
                c3,c4=st.columns(2)
                plat=c3.selectbox("Plataforma",["Vinted","Wallapop","StockX","Otro"])
                cta=c4.text_input("Cuenta Venta")
                
                if st.form_submit_button("CONFIRMAR VENTA", use_container_width=True):
                    idx=df.index[df['ID']==ids][0]
                    g=pv-row['Precio Compra']
                    df.at[idx,'Estado']='Vendido'
                    df.at[idx,'Fecha Venta']=datetime.now()
                    df.at[idx,'Precio Venta']=pv
                    df.at[idx,'Plataforma Venta']=plat
                    df.at[idx,'Cuenta Venta']=cta
                    df.at[idx,'Ganancia Neta']=g
                    # ROI: Evitar división por cero
                    coste = row['Precio Compra']
                    df.at[idx,'ROI %']=(g/coste*100) if coste > 0 else 0
                    
                    guardar_datos(df)
                    st.balloons(); st.success("¡Vendido!"); st.rerun()

# ---------------------------------------------------------
# 3. HISTORIAL (CON BORRADO FÁCIL)
# ---------------------------------------------------------
elif op == "📦 Historial":
    st.title("📦 Historial")
    
    # --- ZONA DE BORRADO ---
    with st.expander("🗑️ BORRAR ZAPATILLAS (Pulsa aquí)"):
        st.warning("Cuidado: Lo que borres aquí desaparece para siempre.")
        
        # Multiselector para borrar varias a la vez
        lista_borrar = df.apply(lambda x: f"ID:{x['ID']} - {x['Marca']} {x['Modelo']} ({x['Estado']})", axis=1).tolist()
        seleccionados = st.multiselect("Selecciona las que quieras eliminar:", lista_borrar)
        
        if seleccionados:
            if st.button(f"ELIMINAR {len(seleccionados)} ARTÍCULOS", type="primary"):
                ids_a_borrar = [int(s.split(" -")[0].replace("ID:", "")) for s in seleccionados]
                # Filtramos el dataframe quedándonos con lo que NO queremos borrar
                df_nuevo = df[~df['ID'].isin(ids_a_borrar)]
                guardar_datos(df_nuevo)
                st.success("Artículos eliminados correctamente.")
                st.rerun()

    # --- TABLA EDITABLE ---
    st.write("Puedes editar celdas directamente:")
    col_config = {
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Precio Compra": st.column_config.NumberColumn(format="%.2f €"),
        "Precio Venta": st.column_config.NumberColumn(format="%.2f €"),
        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f €"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"]),
        "ID": st.column_config.NumberColumn(disabled=True)
    }
    
    df_editado = st.data_editor(df, column_config=col_config, hide_index=True, num_rows="fixed", use_container_width=True)
    
    if not df.equals(df_editado):
        # Recálculo automático de ganancias al editar a mano
        df_editado['Ganancia Neta'] = df_editado['Precio Venta'] - df_editado['Precio Compra']
        guardar_datos(df_editado)
        st.toast("✅ Historial Actualizado")
        st.rerun()

# ---------------------------------------------------------
# 4. FINANZAS
# ---------------------------------------------------------
elif op == "📊 Finanzas":
    st.title("📊 Finanzas")
    if not df.empty:
        sold=df[df['Estado']=='Vendido']
        k1,k2=st.columns(2)
        k1.metric("Beneficio Neto Total", f"{sold['Ganancia Neta'].sum():.2f} €")
        k2.metric("Gasto Total en Stock", f"{df['Precio Compra'].sum():.2f} €")
        
        st.divider()
        st.subheader("Gasto por Tienda")
        st.bar_chart(df.groupby('Tienda Origen')['Precio Compra'].sum())
        
        st.subheader("Beneficio por Plataforma")
        if not sold.empty:
            st.bar_chart(sold.groupby('Plataforma Venta')['Ganancia Neta'].sum())
