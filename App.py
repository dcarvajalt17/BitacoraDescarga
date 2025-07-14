import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "bitacora_descarga.db"

def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def resumen_viajes_por_fecha():
    conn = connect_db()
    df_jornadas = pd.read_sql_query("SELECT * FROM jornadas", conn)
    df_viajes = pd.read_sql_query("SELECT * FROM viajes", conn)
    df_descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    # Unir viajes con jornadas
    df = df_viajes.merge(df_jornadas, left_on="id_jornada", right_on="id", suffixes=("_viaje", "_jornada"))

    # Aseguramos que la columna se llame correctamente
    if "clave_descarga" not in df.columns:
        # Buscar una columna parecida (por seguridad, revisar sufijos)
        posibles = [col for col in df.columns if "clave_descarga" in col]
        if posibles:
            df.rename(columns={posibles[0]: "clave_descarga"}, inplace=True)

    # Ahora sí hacemos el merge con descargas
    df = df.merge(df_descargas, left_on="clave_descarga", right_on="clave", suffixes=("", "_descarga"))


    # Filtramos solo los finalizados
    df = df[df["estado"] == "FINALIZADO"]

    return df




def calcular_diferencias(df):
    df = df.copy()
    for col in ["hora_inicio_cargue", "hora_fin_cargue", "hora_inicio_transito", "hora_llegada_planta", "hora_ingreso_planta", "hora_inicio_descarga", "hora_fin_descarga"]:
        df[col] = pd.to_datetime(df[col], format="%H:%M:%S", errors="coerce")
    df["Duracion Cargue"] = (df["hora_fin_cargue"] - df["hora_inicio_cargue"]).dt.total_seconds() / 60
    df["Transito"] = (df["hora_llegada_planta"] - df["hora_inicio_transito"]).dt.total_seconds() / 60
    df["Espera Planta"] = (df["hora_ingreso_planta"] - df["hora_llegada_planta"]).dt.total_seconds() / 60
    df["Inicio Descarga"] = (df["hora_inicio_descarga"] - df["hora_ingreso_planta"]).dt.total_seconds() / 60
    df["Duracion Descarga"] = (df["hora_fin_descarga"] - df["hora_inicio_descarga"]).dt.total_seconds() / 60
    return df

st.set_page_config("Bitácora Barco", layout="wide")
st.title("🚢 Bitácora de Descarga de Barco")

tabs = st.tabs(["🔧 Crear Descarga", "📅 Jornadas", "🚛 Viajes", "🌡️ Temperaturas", "📊 Resumen", "📤 Exportar"])

# ======= TAB 1: Crear Descarga =======
with tabs[0]:
    st.subheader("Registrar nueva descarga")
    barco = st.text_input("Nombre del barco")
    lote = st.text_input("Lote")
    fecha = st.date_input("Fecha", value=datetime.today())
    if st.button("Crear descarga"):
        if not barco or not lote:
            st.warning("⚠️ Debe ingresar el nombre del barco y el lote.")
        else:
            clave = f"{barco.upper()}-{fecha.strftime('%Y%m%d')}-{lote}"
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS descargas (clave TEXT PRIMARY KEY, barco TEXT, lote TEXT, fecha TEXT)")
            cursor.execute("INSERT OR IGNORE INTO descargas (clave, barco, lote, fecha) VALUES (?, ?, ?, ?)", 
                           (clave, barco, lote, str(fecha)))
            conn.commit()
            conn.close()
            st.success(f"✅ Descarga registrada con clave: {clave}")

# ======= TAB 2: Jornadas =======
with tabs[1]:
    st.subheader("Jornadas")
    conn = connect_db()
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()
    if not descargas.empty:
        clave_sel = st.selectbox("Selecciona descarga", descargas["clave"].tolist())
        if st.button("Iniciar jornada para descarga"):
            hora_inicio = datetime.now().strftime("%H:%M:%S")
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jornadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clave_descarga TEXT,
                    fecha TEXT,
                    hora_inicio TEXT,
                    hora_fin TEXT
                )
            """)
            cursor.execute("INSERT INTO jornadas (clave_descarga, fecha, hora_inicio) VALUES (?, ?, ?)", 
                           (clave_sel, str(datetime.today().date()), hora_inicio))
            conn.commit()
            conn.close()
            st.success("✅ Jornada iniciada")
        conn = connect_db()
        df_jornadas = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = ?", conn, params=(clave_sel,))
        conn.close()
        st.dataframe(df_jornadas)
        if not df_jornadas.empty:
            ultima_jornada = df_jornadas.sort_values(by="id", ascending=False).iloc[0]
            if pd.isna(ultima_jornada["hora_fin"]):
                if st.button("🛑 Finalizar jornada actual"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE jornadas SET hora_fin = ? WHERE id = ?", (datetime.now().strftime("%H:%M:%S"), ultima_jornada["id"]))
                    conn.commit()
                    conn.close()
                    st.success("✅ Jornada finalizada.")
                    st.rerun()

            else:
                st.info("La jornada más reciente ya fue finalizada.")
    else:
        st.info("No hay descargas registradas.")

# ======= TAB 3: Viajes =======
with tabs[2]:
    st.subheader("Gestión de viajes")
    conn = connect_db()

    # Cargamos jornadas aún abiertas
    jornadas_abiertas = pd.read_sql_query("SELECT * FROM jornadas WHERE hora_fin IS NULL", conn)

    if not jornadas_abiertas.empty:
        # Traer la tabla descargas para obtener barco y lote
        descargas = pd.read_sql_query("SELECT * FROM descargas", conn)

        # Unir jornadas abiertas con descargas para mostrar más información
        jornadas_detalle = jornadas_abiertas.merge(descargas, left_on="clave_descarga", right_on="clave")
        
        if "fecha_y" in jornadas_detalle.columns:
            jornadas_detalle.rename(columns={"fecha_y": "fecha_descarga"}, inplace=True)
        elif "fecha" in jornadas_detalle.columns:
            jornadas_detalle.rename(columns={"fecha": "fecha_descarga"}, inplace=True)
        jornadas_detalle.rename(columns={
    "id_x": "id_jornada",
    "barco": "barco_descarga",
    "lote": "lote_descarga",
    "fecha_y": "fecha_descarga"
}, inplace=True)



        # Crear un selector con info del barco, lote y fecha
        jornadas_detalle["label"] = jornadas_detalle.apply(
    lambda row: f"{row['barco_descarga']} - Lote {row['lote_descarga']} ({row['fecha_descarga']}) [Jornada ID {row['id_jornada']}]",
    axis=1
)



        seleccion = st.selectbox("Selecciona una jornada abierta (por barco/lote)", jornadas_detalle["label"])
        jornada_id = jornadas_detalle[jornadas_detalle["label"] == seleccion]["id_jornada"].values[0]
        clave_desc = jornadas_detalle[jornadas_detalle["label"] == seleccion]["clave_descarga"].values[0]


    conn.close()

    if not jornadas_detalle.empty:
        jornada_id = jornadas_detalle[jornadas_detalle["label"] == seleccion]["id_jornada"].values[0]
        clave_desc = jornadas_detalle[jornadas_detalle["label"] == seleccion]["clave_descarga"].values[0]


        def get_num_viajes_en_estado(jornada_id, estado):
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = ? AND estado = ?", (jornada_id, estado))
            count = cursor.fetchone()[0]
            conn.close()
            return count

        def placa_ya_activa(jornada_id, placa):
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = ? AND placa = ? AND estado != 'FINALIZADO'", (jornada_id, placa))
            exists = cursor.fetchone()[0] > 0
            conn.close()
            return exists

        if get_num_viajes_en_estado(jornada_id, "CARGUE") < 2:
            placa = st.text_input("Placa del vehículo")
            if st.button("Crear nuevo viaje"):
                if not placa:
                    st.warning("⚠️ Debe ingresar la placa del vehículo.")
                elif placa_ya_activa(jornada_id, placa):
                    st.error("Este vehículo ya tiene un viaje activo.")
                else:
                    conn = connect_db()
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS viajes (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, clave_descarga TEXT, id_jornada INTEGER, consecutivo TEXT,
                            placa TEXT, estado TEXT,
                            hora_inicio_cargue TEXT, hora_fin_cargue TEXT, hora_inicio_transito TEXT,
                            hora_llegada_planta TEXT, hora_ingreso_planta TEXT, hora_inicio_descarga TEXT, hora_fin_descarga TEXT)
                    """)
                    cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = ?", (jornada_id,))
                    count = cursor.fetchone()[0] + 1
                    consecutivo = f"V{count:03d}"
                    hora_inicio = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("INSERT INTO viajes (clave_descarga, id_jornada, consecutivo, placa, estado, hora_inicio_cargue) VALUES (?, ?, ?, ?, 'CARGUE', ?)",
                                   (clave_desc, jornada_id, consecutivo, placa, hora_inicio))
                    conn.commit()
                    conn.close()
                    st.success("✅ Viaje creado.")
        else:
            st.warning("🚧 Solo se permiten 2 viajes en estado CARGUE simultáneamente.")

        conn = connect_db()
        df = pd.read_sql_query("SELECT * FROM viajes WHERE id_jornada = ? AND estado != 'FINALIZADO'", conn, params=(jornada_id,))
        conn.close()
        for _, row in df.iterrows():
            st.markdown(f"---\n**{row['consecutivo']} - {row['placa']} - Estado: {row['estado']}**")
            col1, _ = st.columns(2)
            if row['estado'] == "CARGUE":
                if col1.button("✅ Fin Cargue", key=f"fc_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = ?, hora_fin_cargue = ?, hora_inicio_transito = ? WHERE id = ?", ("TRANSITO", hora, hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "TRANSITO":
                if col1.button("🏁 Llegada Planta", key=f"t_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = ?, hora_llegada_planta = ? WHERE id = ?", ("EN ESPERA", hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "EN ESPERA":
                if col1.button("🏭 Ingreso Planta", key=f"e_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = ?, hora_ingreso_planta = ? WHERE id = ?", ("DESCARGA", hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "DESCARGA":
                if col1.button("🚚 Inicio Descarga", key=f"id_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = ?, hora_inicio_descarga = ? WHERE id = ?", ("EN DESCARGA", hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "EN DESCARGA":
                if col1.button("📦 Fin Descarga", key=f"fd_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = ?, hora_fin_descarga = ? WHERE id = ?", ("FINALIZADO", hora, row['id']))
                    conn.commit()
                    conn.close()

        st.dataframe(df)
        
with tabs[3]:
    st.subheader("🌡️ Registro de Temperaturas")

    ESPECIES = ["YELLOWFIN", "BIGEYE", "SKIPJACK", "ALBACORA"]
    TALLAS = ["2-3", "3-4","4-5","5-7.5","7.5-10","10-16","16-20", "20-30", "30-40", "40-60", "60-80", "80-100", ">100","RC","RR"]

    conn = connect_db()
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if descargas.empty:
        st.warning("⚠️ No hay descargas registradas.")
    else:
        clave_sel = st.selectbox("Selecciona la descarga", descargas["clave"].tolist())

        conn = connect_db()
        jornadas = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = ?", conn, params=(clave_sel,))
        conn.close()

        if jornadas.empty:
            st.info("ℹ️ No hay jornadas registradas para esta descarga.")
        else:
            jornada_id = st.selectbox("Selecciona la jornada", jornadas["id"].tolist())
            hora = st.time_input("Hora de medición", value=datetime.now().time())
            bodega = st.text_input("Bodega")
            especie = st.selectbox("Especie", ESPECIES)
            talla = st.selectbox("Talla", TALLAS)
            temperatura = st.number_input("Temperatura (°C)", step=0.1)
            lugar = st.radio("Lugar de medición", ["Puerto", "Planta"])

            if st.button("💾 Guardar temperatura"):
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS temperaturas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hora_medicion TEXT,
                        bodega TEXT,
                        especie TEXT,
                        talla TEXT,
                        temperatura REAL,
                        lugar TEXT,
                        clave_descarga TEXT,
                        id_jornada INTEGER
                    )
                """)
                cursor.execute("""
                    INSERT INTO temperaturas 
                    (hora_medicion, bodega, especie, talla, temperatura, lugar, clave_descarga, id_jornada)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (hora.strftime("%H:%M:%S"), bodega, especie, talla, temperatura, lugar, clave_sel, jornada_id))
                conn.commit()
                conn.close()
                st.success("✅ Registro guardado exitosamente.")

            # Mostrar temperaturas registradas
            conn = connect_db()
            df_temp = pd.read_sql_query("SELECT * FROM temperaturas WHERE clave_descarga = ?", conn, params=(clave_sel,))
            conn.close()

            if not df_temp.empty:
                st.markdown("### 📋 Registros guardados")
                st.dataframe(df_temp, use_container_width=True)
       

# ======= TAB 4: Resumen =======
with tabs[4]:
    st.subheader("📊 Resumen de Operaciones")
    df = resumen_viajes_por_fecha()
    if df.empty:
        st.info("No hay viajes finalizados para mostrar.")
    else:
        barcos = df["barco"].unique()
        barco_sel = st.selectbox("Selecciona un barco", sorted(barcos))
        df_barco = df[df["barco"] == barco_sel]
        

        fechas = df_barco["fecha_descarga"].unique()

        fecha_sel = st.selectbox("Selecciona una fecha", sorted(fechas, reverse=True))
        df_filtrado = df_barco[df_barco["fecha"] == fecha_sel]
        df_resultado = calcular_diferencias(df_filtrado)
        
        lotes = df_barco["lote"].unique()
        lote_sel = st.selectbox("Selecciona un lote", sorted(lotes))
        df_filtrado = df_barco[(df_barco["lote"] == lote_sel) & (df_barco["fecha"] == fecha_sel)]


        st.metric("Total de viajes", len(df_resultado))
        viajes_por_vehiculo = df_resultado.groupby("placa").size().reset_index(name="# Viajes")
        st.dataframe(viajes_por_vehiculo, use_container_width=True)

        st.subheader("⏱️ Tiempos promedio por eslabón (minutos)")
        promedios = df_resultado[["Duracion Cargue", "Transito", "Espera Planta", "Inicio Descarga", "Duracion Descarga"]].mean().round(1)
        st.dataframe(promedios.to_frame(name="Promedio (min)"))

        with st.expander("🔍 Ver detalle por viaje"):
            st.dataframe(df_resultado[["consecutivo", "placa", "Duracion Cargue", "Transito", "Espera Planta", "Inicio Descarga", "Duracion Descarga"]], use_container_width=True)

# ======= TAB 5: Exportar =======
with tabs[5]:
    conn = connect_db()
    d1 = pd.read_sql_query("SELECT * FROM descargas", conn)
    d2 = pd.read_sql_query("SELECT * FROM jornadas", conn)
    d3 = pd.read_sql_query("SELECT * FROM viajes", conn)
    try:
        d4 = pd.read_sql_query("SELECT * FROM temperaturas", conn)
    except:
        d4 = pd.DataFrame()
    conn.close()

    filename = f"bitacora_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(filename) as writer:
        d1.to_excel(writer, sheet_name="Descargas", index=False)
        d2.to_excel(writer, sheet_name="Jornadas", index=False)
        d3.to_excel(writer, sheet_name="Viajes", index=False)
        d4.to_excel(writer, sheet_name="Temperaturas", index=False)
    with open(filename, "rb") as f:
        st.download_button("📥 Descargar Excel", f, file_name=filename)

