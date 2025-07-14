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



# ======= TAB 2: Jornadas =======
with tabs[1]:
        st.subheader("Jornadas")
        conn = connect_db()
        descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
        conn.close()

        if not descargas.empty:
            clave_sel = st.selectbox("Selecciona descarga", descargas["clave"].tolist(), key="clave_descarga_jornada")

        if st.button("🟢 Iniciar jornada para descarga", key="iniciar_jornada_btn"):
    # Verificar si ya hay una jornada abierta para esta descarga
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jornadas WHERE clave_descarga = %s AND hora_fin IS NULL", (clave_sel,))
            abierta = cursor.fetchone()[0]

            if abierta > 0:
                conn.close()
                st.warning("⚠️ Ya existe una jornada abierta para esta descarga. Finalízala antes de iniciar una nueva.")
            else:
            
                hora_inicio = datetime.now().strftime("%H:%M:%S")
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
            st.rerun()

        
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
                    cursor.execute("UPDATE jornadas SET hora_fin = %s WHERE id = %s", (hora_fin, int(jornada_id)))
                    conn.commit()
                    conn.close()
                    st.success("✅ Jornada finalizada.")
                    st.rerun()

            else:
                st.info("ℹ️ No hay jornadas abiertas para esta descarga.")
        else:
            st.warning("No hay descargas registradas.")

# ======= TAB 3: Viajes =======
with tabs[2]:
    st.subheader("Gestión de viajes")
    
    # Conectar a la base de datos
    conn = connect_db()
    jornadas_abiertas = pd.read_sql_query("SELECT * FROM jornadas WHERE hora_fin IS NULL", conn)
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if jornadas_abiertas.empty:
        st.info("ℹ️ No hay jornadas abiertas actualmente.")
    else:
        # Renombrar columnas para evitar conflictos en el merge
        descargas = descargas.rename(columns={
            "barco": "barco_descarga",
            "lote": "lote_descarga",
            "fecha": "fecha_descarga"
        })

        jornadas_abiertas = jornadas_abiertas.rename(columns={"id": "id_jornada"})

        # Merge de jornadas abiertas con info de descarga
        jornadas_detalle = jornadas_abiertas.merge(
            descargas, left_on="clave_descarga", right_on="clave"
        )

        # Crear columna combinada para mostrar en el selectbox
        jornadas_detalle["label"] = jornadas_detalle.apply(
            lambda row: f"{row['barco_descarga']} - Lote {row['lote_descarga']} ({row['fecha_descarga']}) [Jornada ID {row['id_jornada']}]",
            axis=1
        )

        # Selector de jornada
        seleccion = st.selectbox("Selecciona una jornada abierta (por barco/lote)", jornadas_detalle["label"])
        jornada_info = jornadas_detalle[jornadas_detalle["label"] == seleccion].iloc[0]
        jornada_id = jornada_info["id_jornada"]
        clave_desc = jornada_info["clave_descarga"]

        # Funciones auxiliares
        def get_num_viajes_en_estado(jornada_id, estado):
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = %s AND estado = %s", (int(jornada_id), estado))
            count = cursor.fetchone()[0]
            conn.close()
            return count

        def placa_ya_activa(jornada_id, placa):
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = %s AND placa = %s AND estado != 'FINALIZADO'", (int(jornada_id), placa))
            exists = cursor.fetchone()[0] > 0
            conn.close()
            return exists

        # Crear nuevo viaje
        if get_num_viajes_en_estado(jornada_id, "CARGUE") < 2:
            placa = st.text_input("Placa del vehículo")
            if st.button("Crear nuevo viaje"):
                if not placa:
                    st.warning("⚠️ Debe ingresar la placa del vehículo.")
                elif placa_ya_activa(jornada_id, placa):
                    st.error("🚫 Este vehículo ya tiene un viaje activo.")
                else:
                    conn = connect_db()
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS viajes (
                            id SERIAL PRIMARY KEY, clave_descarga TEXT, id_jornada INTEGER, consecutivo TEXT,
                            placa TEXT, estado TEXT,
                            hora_inicio_cargue TEXT, hora_fin_cargue TEXT, hora_inicio_transito TEXT,
                            hora_llegada_planta TEXT, hora_ingreso_planta TEXT, hora_inicio_descarga TEXT, hora_fin_descarga TEXT)
                    """)
                    cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = %s", (int(jornada_id),))
                    count = cursor.fetchone()[0] + 1
                    consecutivo = f"V{count:03d}"
                    hora_inicio = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("""
                        INSERT INTO viajes (clave_descarga, id_jornada, consecutivo, placa, estado, hora_inicio_cargue)
                        VALUES (%s, %s, %s, %s, 'CARGUE', %s)
                    """, (clave_desc, int(jornada_id), consecutivo, placa, hora_inicio))
                    conn.commit()
                    conn.close()
                    st.success("✅ Viaje creado.")
                    st.rerun()
        else:
            st.warning("🚧 Solo se permiten 2 viajes en estado CARGUE simultáneamente.")

        # Mostrar viajes activos
        conn = connect_db()
        df = pd.read_sql_query("SELECT * FROM viajes WHERE id_jornada = %s AND estado != 'FINALIZADO'", conn, params=(int(jornada_id),))
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
                    st.rerun()

            elif row['estado'] == "TRANSITO":
                if col1.button("🏁 Llegada Planta", key=f"t_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_llegada_planta = %s WHERE id = %s", ("EN ESPERA", hora, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()

            elif row['estado'] == "EN ESPERA":
                if col1.button("🏭 Ingreso Planta", key=f"e_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_ingreso_planta = %s WHERE id = %s", ("DESCARGA", hora, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()

            elif row['estado'] == "DESCARGA":
                if col1.button("🚚 Inicio Descarga", key=f"id_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_inicio_descarga = %s WHERE id = %s", ("EN DESCARGA", hora, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()

            elif row['estado'] == "EN DESCARGA":
                if col1.button("📦 Fin Descarga", key=f"fd_{row['id']}"):
                    conn = connect_db()
                    cursor = conn.cursor()
                    hora = datetime.now().strftime("%H:%M:%S")
                    cursor.execute("UPDATE viajes SET estado = %s, hora_fin_descarga = %s WHERE id = %s", ("FINALIZADO", hora, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()

        st.markdown("### 🚚 Viajes activos")
        st.dataframe(df, use_container_width=True)


        
        
with tabs[3]:
    st.subheader("🌡️ Registro de Temperaturas")

    # Listas para seleccionar especie y talla
    ESPECIES = ["YELLOWFIN", "BIGEYE", "SKIPJACK", "ALBACORA"]
    TALLAS = ["2-3", "3-4", "4-5", "5-7.5", "7.5-10", "10-16", "16-20", 
              "20-30", "30-40", "40-60", "60-80", "80-100", ">100", "RC", "RR"]

    # Obtener descargas
    conn = connect_db()
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if descargas.empty:
        st.warning("⚠️ No hay descargas registradas.")
    else:
        # Selección de descarga
        clave_sel = st.selectbox("Selecciona la descarga", descargas["clave"].tolist())

        # Obtener jornadas relacionadas
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

            # Guardar registro
            if st.button("💾 Guardar temperatura"):
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS temperaturas (
                        id SERIAL PRIMARY KEY,
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    hora.strftime("%H:%M:%S"), bodega, especie, talla,
                    temperatura, lugar, clave_sel, jornada_id
                ))
                conn.commit()
                conn.close()
                st.success("✅ Registro guardado exitosamente.")
                st.rerun()

            # Mostrar registros anteriores
            conn = connect_db()
            df_temp = pd.read_sql_query("SELECT * FROM temperaturas WHERE clave_descarga = %s", conn, params=(clave_sel,))
            conn.close()

            if not df_temp.empty:
                st.markdown("### 📋 Registros guardados")
                st.dataframe(df_temp, use_container_width=True)

       

# ======= TAB 4: Resumen =======
with tabs[4]:
    st.subheader("📊 Resumen de Operaciones")

    # Obtener los viajes finalizados con jornadas y descargas
    df = resumen_viajes_por_fecha()

    if df.empty:
        st.info("No hay viajes finalizados para mostrar.")
    else:
        # Filtro por barco
        barcos = df["barco"].unique()
        barco_sel = st.selectbox("Selecciona un barco", sorted(barcos))
        df_barco = df[df["barco"] == barco_sel]

        # Filtro por fecha
        fechas = df_barco["fecha"].unique()
        fecha_sel = st.selectbox("Selecciona una fecha", sorted(fechas, reverse=True))
        df_fecha = df_barco[df_barco["fecha"] == fecha_sel]

        # Filtro por lote
        lotes = df_fecha["lote"].unique()
        lote_sel = st.selectbox("Selecciona un lote", sorted(lotes))
        df_filtrado = df_fecha[df_fecha["lote"] == lote_sel]

        # Calcular diferencias de tiempo
        df_resultado = calcular_diferencias(df_filtrado)

        st.metric("🧾 Total de viajes", len(df_resultado))

        # Viajes por vehículo
        viajes_por_vehiculo = df_resultado.groupby("placa").size().reset_index(name="# Viajes")
        st.markdown("### 🚛 Viajes por vehículo")
        st.dataframe(viajes_por_vehiculo, use_container_width=True)

        # Promedios de tiempos
        st.markdown("### ⏱️ Tiempos promedio por eslabón (minutos)")
        cols_tiempos = ["Duracion Cargue", "Transito", "Espera Planta", "Inicio Descarga", "Duracion Descarga"]
        promedios = df_resultado[cols_tiempos].mean().round(1)
        st.dataframe(promedios.to_frame(name="Promedio (min)"), use_container_width=True)

        # Detalle por viaje
        with st.expander("🔍 Ver detalle por viaje"):
            detalle = df_resultado[["consecutivo", "placa"] + cols_tiempos]
            st.dataframe(detalle, use_container_width=True)

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
