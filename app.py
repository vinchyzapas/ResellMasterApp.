# --- HISTORIAL ---
elif st.session_state['seccion_actual'] == "Historial":
    st.title("📋 Historial")
    st.info("💡 Escribe los precios con coma o punto (ej: 65,5 o 65.5)")

    bus = st.text_input("🔍 Filtrar:", placeholder="Escribe...")
    cri = st.selectbox(
        "🔃 Ordenar:",
        ["Fecha Compra (Reciente)", "Marca (A-Z)", "Precio (Bajo-Alto)", "Talla (Menor-Mayor)", "Talla (Mayor-Menor)"]
    )

    df_v = df.copy()

    if bus:
        mask = df_v.astype(str).apply(
            lambda row: row.str.contains(bus, case=False).any(), axis=1
        )
        df_v = df_v[mask]

    if "Reciente" in cri:
        df_v = df_v.sort_values(by="Fecha Compra", ascending=False)
    elif "Marca" in cri:
        df_v = df_v.sort_values(by="Marca")
    elif "Precio" in cri:
        df_v = df_v.sort_values(by="Precio Compra")
    elif "Talla" in cri:
        df_v['T_Num'] = pd.to_numeric(df_v['Talla'], errors='coerce')
        if "Menor-Mayor" in cri:
            df_v = df_v.sort_values(by="T_Num")
        else:
            df_v = df_v.sort_values(by="T_Num", ascending=False)

    cols_ord = [
        "ID", "🌐 Web", "Marca", "Modelo", "Talla",
        "Precio Compra", "Precio Venta", "Ganancia Neta",
        "Estado", "Tracking", "Fecha Compra", "Fecha Venta"
    ]

    col_cfg = {
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "🌐 Web": st.column_config.LinkColumn(display_text="🔎 Buscar"),

        # 👇 PRECIOS COMO TEXTO (CLAVE)
        "Precio Compra": st.column_config.TextColumn(),
        "Precio Venta": st.column_config.TextColumn(),

        "Ganancia Neta": st.column_config.NumberColumn(format="%.2f", disabled=True),
        "Fecha Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fecha Venta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Estado": st.column_config.SelectboxColumn(options=["En Stock", "Vendido"])
    }

    df_ed = st.data_editor(
        df_v[[c for c in cols_ord if c in df_v.columns]],
        column_config=col_cfg,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="ev65"
    )

    if not df.equals(df_ed):
        df_ag = df_ed.drop(columns=['🌐 Web', 'T_Num'], errors='ignore')

        # 🔥 CONVERSIÓN SEGURA
        df_ag['Precio Compra'] = df_ag['Precio Compra'].apply(leer_numero_literal)
        df_ag['Precio Venta']  = df_ag['Precio Venta'].apply(leer_numero_literal)

        df_ag['Ganancia Neta'] = df_ag['Precio Venta'] - df_ag['Precio Compra']
        df_ag['Talla'] = df_ag['Talla'].apply(arreglar_talla)

        df.update(df_ag)
        guardar_datos_zapas(df)
        st.toast("✅ Guardado correctamente")
