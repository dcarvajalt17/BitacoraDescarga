import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ==== CSS para botón flotante ====
st.markdown("""
<style>
.fab {
    position: fixed;
    bottom: 30px;
    right: 30px;
    background-color: #0e1117;
    color: white;
    border-radius: 50%;
    padding: 16px 20px;
    font-size: 24px;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
    cursor: pointer;
    z-index: 9999;
    text-align: center;
}
.fab:hover {
    background-color: #202431;
}
</style>
<a href="#registrar-descarga" class="fab">＋</a>
""", unsafe_allow_html=True)

def connect_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def resumen_viajes_por_fecha():
    conn = connect_db()
    df_jornadas = pd.read_sql_query("SELECT * FROM jornadas", conn)
    df_viajes = pd.read_sql_query("SELECT * FROM viajes", conn)
    df_descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()
    df = df_viajes.merge(df_jornadas, left_on="id_jornada", right_on="id", suffixes=("_viaje", "_jornada"))
    if "clave_descarga" not in df.columns:
        posibles = [col for col in df.columns if "clave_descarga" in col]
        if posibles:
            df.rename(columns={posibles[0]: "clave_descarga"}, inplace=True)
    df = df.merge(df_descargas, left_on="clave_descarga", right_on="clave", suffixes=("", "_descarga"))
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

# ==== TABS ====
tabs = st.tabs(["🔧 Crear Descarga", "�헕️ Jornadas", "🚛 Viajes", "🌡️ Temperaturas", "📊 Resumen", "📄 Exportar"])

# ==== ID para scroll desde botón flotante ====
with tabs[0]:
    st.subheader("Registrar nueva descarga")
    st.markdown('<div id="registrar-descarga"></div>', unsafe_allow_html=True)
    barco = st.text_input("Nombre del barco", key="barco_input")
    lote = st.text_input("Lote", key="lote_input")
    fecha = st.date_input("Fecha", value=datetime.today(), key="fecha_input")
    if st.button("Crear descarga", key="crear_descarga_btn"):
        if not barco or not lote:
            st.warning("⚠️ Debe ingresar el nombre del barco y el lote.")
        else:
            clave = f"{barco.upper()}-{fecha.strftime('%Y%m%d')}-{lote}"
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS descargas (clave TEXT PRIMARY KEY, barco TEXT, lote TEXT, fecha TEXT)")
            cursor.execute("""
                INSERT INTO descargas (clave, barco, lote, fecha)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (clave) DO NOTHING
            """, (clave, barco, lote, str(fecha)))
            conn.commit()
            conn.close()
            st.success(f"✅ Descarga registrada con clave: {clave}")

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
            cursor.execute("""
                                INSERT INTO descargas (clave, barco, lote, fecha)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (clave) DO NOTHING
                            """, (clave, barco, lote, str(fecha)))

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
            clave_sel = st.selectbox("Selecciona descarga", descargas["clave"].tolist(), key="clave_descarga_jornada")

        if st.button("Iniciar jornada para descarga", key="iniciar_jornada_btn"):
            hora_inicio = datetime.now().strftime("%H:%M:%S")
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jornadas (
                    id SERIAL PRIMARY KEY,
                    clave_descarga TEXT,
                    fecha TEXT,
                    hora_inicio TEXT,
                    hora_fin TEXT
                )
            """)
            cursor.execute("""
                INSERT INTO jornadas (clave_descarga, fecha, hora_inicio)
                VALUES (%s, %s, %s)
            """, (clave_sel, str(datetime.today().date()), hora_inicio))
            conn.commit()
            conn.close()
            st.success("✅ Jornada iniciada.")
            st.experimental_rerun()

        conn = connect_db()
        df_jornadas = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = %s ORDER BY id DESC", conn, params=(clave_sel,))
        conn.close()

        st.dataframe(df_jornadas)

        if not df_jornadas.empty:
            jornada_abierta = df_jornadas[df_jornadas["hora_fin"].isna()]
            if not jornada_abierta.empty:
                jornada_id = jornada_abierta.iloc[0]["id"]
                if st.button("🛑 Finalizar jornada actual", key="finalizar_jornada_btn"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora_fin = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE jornadas SET hora_fin = %s WHERE id = %s", (hora_fin, jornada_id))
                    conn.commit()
                    conn.close()
                    st.success("✅ Jornada finalizada.")
                    st.experimental_rerun()
            else:
                st.info("ℹ️ No hay jornadas abiertas para esta descarga.")
        else:
            st.warning("No hay descargas registradas.")

# ======= TAB 3: Viajes =======
with tabs[2]:
    st.subheader("Gestión de viajes")
    conn = connect_db()

    # Cargamos jornadas aún abiertas
    jornadas_abiertas = pd.read_sql_query("SELECT * FROM jornadas WHERE hora_fin IS NULL", conn)
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if not jornadas_abiertas.empty:
        # Unir jornadas abiertas con descargas para mostrar más información
        jornadas_detalle = jornadas_abiertas.merge(descargas, left_on="clave_descarga", right_on="clave")

        # Renombrar columnas para mayor claridad
        jornadas_detalle.rename(columns={
            "id": "id_jornada",
            "barco": "barco_descarga",
            "lote": "lote_descarga",
            "fecha": "fecha_descarga"
        }, inplace=True)

        # Crear columna para selector
        jornadas_detalle["label"] = jornadas_detalle.apply(
            lambda row: f"{row['barco_descarga']} - Lote {row['lote_descarga']} ({row['fecha_descarga']}) [Jornada ID {row['id_jornada']}]",
            axis=1
        )

        seleccion = st.selectbox("Selecciona una jornada abierta (por barco/lote)", jornadas_detalle["label"])
        jornada_id = jornadas_detalle[jornadas_detalle["label"] == seleccion]["id_jornada"].values[0]
        clave_desc = jornadas_detalle[jornadas_detalle["label"] == seleccion]["clave_descarga"].values[0]

        def get_num_viajes_en_estado(jornada_id, estado):
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = %s AND estado = %s", (jornada_id, estado))
            count = cursor.fetchone()[0]
            conn.close()
            return count

        def placa_ya_activa(jornada_id, placa):
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = %s AND placa = %s AND estado != 'FINALIZADO'", (jornada_id, placa))
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
                    cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = %s", (jornada_id,))
                    count = cursor.fetchone()[0] + 1
                    consecutivo = f"V{count:03d}"
                    hora_inicio = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("""
                        INSERT INTO viajes (clave_descarga, id_jornada, consecutivo, placa, estado, hora_inicio_cargue)
                        VALUES (%s, %s, %s, %s, 'CARGUE', %s)
                    """, (clave_desc, jornada_id, consecutivo, placa, hora_inicio))
                    conn.commit()
                    conn.close()
                    st.success("✅ Viaje creado.")
        else:
            st.warning("🚧 Solo se permiten 2 viajes en estado CARGUE simultáneamente.")

        # Mostrar viajes activos
        conn = connect_db()
        df = pd.read_sql_query("SELECT * FROM viajes WHERE id_jornada = %s AND estado != 'FINALIZADO'", conn, params=(jornada_id,))
        conn.close()

        for _, row in df.iterrows():
            st.markdown(f"---\n**{row['consecutivo']} - {row['placa']} - Estado: {row['estado']}**")
            col1, _ = st.columns(2)
            if row['estado'] == "CARGUE":
                if col1.button("✅ Fin Cargue", key=f"fc_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_fin_cargue = %s, hora_inicio_transito = %s WHERE id = %s", ("TRANSITO", hora, hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "TRANSITO":
                if col1.button("🏁 Llegada Planta", key=f"t_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_llegada_planta = %s WHERE id = %s", ("EN ESPERA", hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "EN ESPERA":
                if col1.button("🏭 Ingreso Planta", key=f"e_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_ingreso_planta = %s WHERE id = %s", ("DESCARGA", hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "DESCARGA":
                if col1.button("🚚 Inicio Descarga", key=f"id_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_inicio_descarga = %s WHERE id = %s", ("EN DESCARGA", hora, row['id']))
                    conn.commit()
                    conn.close()
            elif row['estado'] == "EN DESCARGA":
                if col1.button("📦 Fin Descarga", key=f"fd_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_fin_descarga = %s WHERE id = %s", ("FINALIZADO", hora, row['id']))
                    conn.commit()
                    conn.close()

        st.dataframe(df)

    else:
        st.info("No hay jornadas abiertas actualmente.")

        
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
        jornadas = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = %s", conn, params=(clave_sel,))
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (hora.strftime("%H:%M:%S"), bodega, especie, talla, temperatura, lugar, clave_sel, jornada_id))
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

if __name__ == "__main__":
    try:
        conn = connect_db()
        print("✅ Conexión exitosa a Supabase")
        conn.close()
    except Exception as e:
        print("❌ Error de conexión:", e)
