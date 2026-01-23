import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Zapas SQLite", layout="wide")

DB_FILE = "inventario.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def crear_tabla():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zapatillas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo TEXT,
            talla TEXT,
            precio_compra REAL,
            precio_venta REAL,
            ganancia REAL,
            fecha_compra TEXT,
            fecha_venta TEXT
        )
    """)
    conn.commit()
    conn.close()

def cargar_datos():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM zapatillas", conn)
    conn.close()
    return df

def guardar_datos(df):
    conn = get_connection()
    conn.execute("DELETE FROM zapatillas")
    df.to_sql("zapatillas", conn, if_exists="append", index=False)
    conn.close()

st.title("👟 Gestión de Zapatillas (SQLite)")

crear_tabla()

df = cargar_datos()

if df.empty:
    df = pd.DataFrame(columns=[
        "id", "modelo", "talla",
        "precio_compra", "precio_venta",
        "ganancia", "fecha_compra", "fecha_venta"
    ])

df["ganancia"] = df["precio_venta"] - df["precio_compra"]

df_edit = st.data_editor(
    df,
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True
)

if st.button("💾 Guardar cambios"):
    df_edit["ganancia"] = df_edit["precio_venta"] - df_edit["precio_compra"]
    guardar_datos(df_edit)
    st.success("✅ Datos guardados correctamente")
