import flet as ft
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "bitacora_descarga.db"

def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ---------------- Tab 1 ----------------
def crear_descarga_tab(page: ft.Page):
    mensaje = ft.Text()
    barco = ft.TextField(label="Nombre del Barco")
    lote = ft.TextField(label="Lote")

    fecha_picker = ft.DatePicker()  



    def crear_descarga(e):
        if not barco.value or not lote.value:
            mensaje.value = "⚠️ Debe ingresar el nombre del barco y el lote."
            mensaje.color = ft.colors.RED
        else:
            fecha = fecha_picker.value or datetime.today()
            clave = f"{barco.value.upper()}-{fecha.strftime('%Y%m%d')}-{lote.value}"
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS descargas (
                    clave TEXT PRIMARY KEY,
                    barco TEXT,
                    lote TEXT,
                    fecha TEXT
                )
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO descargas (clave, barco, lote, fecha) VALUES (?, ?, ?, ?)
            """, (clave, barco.value, lote.value, str(fecha)))
            conn.commit()
            conn.close()
            mensaje.value = f"✅ Descarga registrada con clave: {clave}"
            mensaje.color = ft.Colors.GREEN
        page.update()

    return ft.Column([
    ft.Text("Registrar nueva descarga", size=20, weight="bold"),
    barco,
    lote,
    fecha_picker,  # <-- Aquí directamente
    ft.ElevatedButton("Crear descarga", on_click=crear_descarga),
    mensaje
])


# ---------------- Tab 2 ----------------
def jornadas_tab(page: ft.Page):
    mensaje = ft.Text()
    conn = connect_db()
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if descargas.empty:
        return ft.Text("⚠️ No hay descargas registradas.")

    claves = descargas["clave"].tolist()
    clave_dropdown = ft.Dropdown(label="Selecciona descarga", options=[ft.dropdown.Option(c) for c in claves])
    tabla_jornadas = ft.DataTable(columns=[
        ft.DataColumn(label=ft.Text("ID")),
        ft.DataColumn(label=ft.Text("Clave descarga")),
        ft.DataColumn(label=ft.Text("Fecha")),
        ft.DataColumn(label=ft.Text("Inicio")),
        ft.DataColumn(label=ft.Text("Fin")),
    ], rows=[])

    def cargar_jornadas(e=None):
        conn = connect_db()
        df = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = ?", conn, params=(clave_dropdown.value,))
        conn.close()
        filas = []
        for _, row in df.iterrows():
            filas.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(row["id"]))),
                ft.DataCell(ft.Text(row["clave_descarga"])),
                ft.DataCell(ft.Text(row["fecha"])),
                ft.DataCell(ft.Text(str(row["hora_inicio"]))),
                ft.DataCell(ft.Text(str(row["hora_fin"]))),
            ]))
        tabla_jornadas.rows = filas
        page.update()

    def iniciar_jornada(e):
        if not clave_dropdown.value:
            mensaje.value = "⚠️ Selecciona una descarga."
            return
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
                       (clave_dropdown.value, str(datetime.today().date()), hora_inicio))
        conn.commit()
        conn.close()
        mensaje.value = "✅ Jornada iniciada."
        cargar_jornadas()
        page.update()

    def finalizar_ultima_jornada(e):
        if not clave_dropdown.value:
            return
        conn = connect_db()
        cursor = conn.cursor()
        df = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = ? ORDER BY id DESC", conn, params=(clave_dropdown.value,))
        if df.empty:
            mensaje.value = "No hay jornadas para finalizar."
        else:
            ultima = df.iloc[0]
            if pd.isna(ultima["hora_fin"]):
                cursor.execute("UPDATE jornadas SET hora_fin = ? WHERE id = ?",
                               (datetime.now().strftime("%H:%M:%S"), ultima["id"]))
                conn.commit()
                mensaje.value = "✅ Jornada finalizada."
            else:
                mensaje.value = "ℹ️ La última jornada ya fue finalizada."
        conn.close()
        cargar_jornadas()
        page.update()

    return ft.Column([
        ft.Text("Gestión de Jornadas", size=20, weight="bold"),
        clave_dropdown,
        ft.Row([
            ft.ElevatedButton("Iniciar jornada", on_click=iniciar_jornada),
            ft.ElevatedButton("Finalizar última jornada", on_click=finalizar_ultima_jornada)
        ]),
        mensaje,
        ft.Text("Listado de jornadas:"),
        tabla_jornadas
    ])

# ------------------ VIAJES TAB ------------------
def viajes_tab(page: ft.Page):
    mensaje = ft.Text()
    conn = connect_db()
    jornadas = pd.read_sql_query("SELECT * FROM jornadas WHERE hora_fin IS NULL", conn)
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if jornadas.empty:
        return ft.Text("⚠️ No hay jornadas abiertas.")

    jornadas = jornadas.merge(descargas, left_on="clave_descarga", right_on="clave")

    jornadas["label"] = jornadas.apply(
        lambda row: f"{row['barco']} - Lote {row['lote']} ({row['fecha_y']}) [Jornada ID {row['id_x']}]",
        axis=1
    )

    dropdown_options = [ft.dropdown.Option(row["id_x"], row["label"]) for _, row in jornadas.iterrows()]
    jornada_dropdown = ft.Dropdown(label="Selecciona jornada", options=dropdown_options)
    placa_input = ft.TextField(label="Placa del vehículo")
    tabla_viajes = ft.DataTable(columns=[
        ft.DataColumn(label=ft.Text("ID")),
        ft.DataColumn(label=ft.Text("Placa")),
        ft.DataColumn(label=ft.Text("Estado")),
        ft.DataColumn(label=ft.Text("Inicio cargue")),
    ], rows=[])

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

    def crear_viaje(e):
        if not jornada_dropdown.value or not placa_input.value:
            mensaje.value = "⚠️ Selecciona jornada y placa."
            return
        jornada_id = int(jornada_dropdown.value)
        placa = placa_input.value.upper()

        if get_num_viajes_en_estado(jornada_id, "CARGUE") >= 2:
            mensaje.value = "🚧 Máximo 2 viajes en CARGUE."
            return
        if placa_ya_activa(jornada_id, placa):
            mensaje.value = "🚨 Placa ya tiene viaje activo."
            return

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS viajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave_descarga TEXT, id_jornada INTEGER, consecutivo TEXT,
                placa TEXT, estado TEXT,
                hora_inicio_cargue TEXT, hora_fin_cargue TEXT, hora_inicio_transito TEXT,
                hora_llegada_planta TEXT, hora_ingreso_planta TEXT,
                hora_inicio_descarga TEXT, hora_fin_descarga TEXT
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM viajes WHERE id_jornada = ?", (jornada_id,))
        count = cursor.fetchone()[0] + 1
        consecutivo = f"V{count:03d}"
        hora = datetime.now().strftime("%H:%M:%S")

        clave_descarga = jornadas[jornadas["id_x"] == jornada_id]["clave"].values[0]
        cursor.execute("""
            INSERT INTO viajes (clave_descarga, id_jornada, consecutivo, placa, estado, hora_inicio_cargue)
            VALUES (?, ?, ?, ?, 'CARGUE', ?)
        """, (clave_descarga, jornada_id, consecutivo, placa, hora))
        conn.commit()
        conn.close()
        mensaje.value = "✅ Viaje creado."
        cargar_viajes()
        page.update()

    def cargar_viajes(e=None):
        if not jornada_dropdown.value:
            return
        conn = connect_db()
        df = pd.read_sql_query("SELECT * FROM viajes WHERE id_jornada = ? AND estado != 'FINALIZADO'", conn, params=(jornada_dropdown.value,))
        conn.close()
        tabla_viajes.rows = []
        for _, row in df.iterrows():
            tabla_viajes.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(row["id"]))),
                ft.DataCell(ft.Text(row["placa"])),
                ft.DataCell(ft.Text(row["estado"])),
                ft.DataCell(ft.Text(row["hora_inicio_cargue"])),
            ]))
        page.update()

    return ft.Column([
        ft.Text("🚛 Gestión de Viajes", size=20, weight="bold"),
        jornada_dropdown,
        placa_input,
        ft.Row([
            ft.ElevatedButton("Crear nuevo viaje", on_click=crear_viaje),
            ft.ElevatedButton("Actualizar viajes", on_click=cargar_viajes)
        ]),
        mensaje,
        ft.Text("Viajes activos:"),
        tabla_viajes
    ])
# ------------------ TEMPERATURAS TAB ------------------
def temperaturas_tab(page: ft.Page):
    ESPECIES = ["YELLOWFIN", "BIGEYE", "SKIPJACK", "ALBACORA"]
    TALLAS = ["2-3", "3-4","4-5","5-7.5","7.5-10","10-16","16-20", "20-30", "30-40", "40-60", "60-80", "80-100", ">100","RC","RR"]

    mensaje = ft.Text()

    conn = connect_db()
    descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    conn.close()

    if descargas.empty:
        return ft.Text("⚠️ No hay descargas registradas.")

    claves = descargas["clave"].tolist()
    clave_dropdown = ft.Dropdown(label="Selecciona descarga", options=[ft.dropdown.Option(c) for c in claves])

    jornada_dropdown = ft.Dropdown(label="Selecciona jornada", options=[])

    def cargar_jornadas(e):
        conn = connect_db()
        jornadas = pd.read_sql_query("SELECT * FROM jornadas WHERE clave_descarga = ?", conn, params=(clave_dropdown.value,))
        conn.close()
        jornada_dropdown.options = [ft.dropdown.Option(str(j)) for j in jornadas["id"].tolist()]
        jornada_dropdown.value = jornada_dropdown.options[0].value if jornada_dropdown.options else None

        page.update()

    hora_picker = ft.TimePicker()
    especie_dd = ft.Dropdown(label="Especie", options=[ft.dropdown.Option(e) for e in ESPECIES])
    talla_dd = ft.Dropdown(label="Talla", options=[ft.dropdown.Option(t) for t in TALLAS])
    lugar_radio = ft.RadioGroup(content=ft.Row([
        ft.Radio(value="Puerto", label="Puerto"),
        ft.Radio(value="Planta", label="Planta"),
    ]))
    bodega = ft.TextField(label="Bodega")
    temperatura = ft.TextField(label="Temperatura °C", keyboard_type=ft.KeyboardType.NUMBER)

    tabla_temp = ft.DataTable(columns=[
        ft.DataColumn(label=ft.Text("Hora")),
        ft.DataColumn(label=ft.Text("Bodega")),
        ft.DataColumn(label=ft.Text("Especie")),
        ft.DataColumn(label=ft.Text("Talla")),
        ft.DataColumn(label=ft.Text("Temp")),
        ft.DataColumn(label=ft.Text("Lugar")),
    ], rows=[])

    def guardar_temp(e):
        if not clave_dropdown.value or not jornada_dropdown.value:
            mensaje.value = "⚠️ Debe seleccionar descarga y jornada."
            return
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
        hora_str = hora_picker.value.strftime("%H:%M:%S") if hora_picker.value else datetime.now().strftime("%H:%M:%S")
        cursor.execute("""
            INSERT INTO temperaturas 
            (hora_medicion, bodega, especie, talla, temperatura, lugar, clave_descarga, id_jornada)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hora_str, bodega.value, especie_dd.value, talla_dd.value,
            float(temperatura.value), lugar_radio.value, clave_dropdown.value, int(jornada_dropdown.value)
        ))
        conn.commit()
        conn.close()
        mensaje.value = "✅ Temperatura registrada."
        cargar_registros()
        page.update()

    def cargar_registros(e=None):
        if not clave_dropdown.value:
            return
        conn = connect_db()
        df = pd.read_sql_query("SELECT * FROM temperaturas WHERE clave_descarga = ?", conn, params=(clave_dropdown.value,))
        conn.close()
        tabla_temp.rows = []
        for _, row in df.iterrows():
            tabla_temp.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(row["hora_medicion"])),
                ft.DataCell(ft.Text(row["bodega"])),
                ft.DataCell(ft.Text(row["especie"])),
                ft.DataCell(ft.Text(row["talla"])),
                ft.DataCell(ft.Text(str(row["temperatura"]))),
                ft.DataCell(ft.Text(row["lugar"])),
            ]))
        page.update()

    return ft.Column([
        ft.Text("🌡️ Registro de Temperaturas", size=20, weight="bold"),
        clave_dropdown,
        jornada_dropdown,
        ft.ElevatedButton("Cargar jornadas", on_click=cargar_jornadas),
        ft.ElevatedButton("Seleccionar hora", on_click=lambda _: hora_picker.pick_time()),
        hora_picker,
        bodega,
        especie_dd,
        talla_dd,
        temperatura,
        lugar_radio,
        ft.ElevatedButton("Guardar temperatura", on_click=guardar_temp),
        mensaje,
        ft.Text("📋 Registros guardados:"),
        tabla_temp
    ])
    
    # ------------------ RESUMEN TAB ------------------
def resumen_tab(page: ft.Page):
    conn = connect_db()
    
    # Cargar datos base
    df_descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
    df_jornadas = pd.read_sql_query("SELECT * FROM jornadas", conn)
    df_viajes = pd.read_sql_query("SELECT * FROM viajes", conn)
    df_temp = pd.read_sql_query("SELECT * FROM temperaturas", conn)
    conn.close()

    total_descargas = len(df_descargas)
    total_jornadas = len(df_jornadas)
    total_viajes = len(df_viajes)
    total_temperaturas = len(df_temp)

    # Resumen por descarga
    resumen = df_descargas.copy()
    resumen["jornadas"] = resumen["clave"].apply(lambda k: df_jornadas[df_jornadas["clave_descarga"] == k].shape[0])
    resumen["viajes"] = resumen["clave"].apply(lambda k: df_viajes[df_viajes["clave_descarga"] == k].shape[0])
    resumen["temperaturas"] = resumen["clave"].apply(lambda k: df_temp[df_temp["clave_descarga"] == k].shape[0])

    tabla_resumen = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("Barco")),
            ft.DataColumn(label=ft.Text("Lote")),
            ft.DataColumn(label=ft.Text("Fecha")),
            ft.DataColumn(label=ft.Text("Jornadas")),
            ft.DataColumn(label=ft.Text("Viajes")),
            ft.DataColumn(label=ft.Text("Temp.")),
        ],
        rows=[
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(row["barco"])),
                ft.DataCell(ft.Text(row["lote"])),
                ft.DataCell(ft.Text(row["fecha"])),
                ft.DataCell(ft.Text(str(row["jornadas"]))),
                ft.DataCell(ft.Text(str(row["viajes"]))),
                ft.DataCell(ft.Text(str(row["temperaturas"]))),
            ])
            for _, row in resumen.iterrows()
        ]
    )

    return ft.Column([
        ft.Text("📊 Resumen General de Operaciones", size=20, weight="bold"),
        ft.Row([
            ft.Text(f"🚢 Total Descargas: {total_descargas}"),
            ft.Text(f"⏱️ Jornadas: {total_jornadas}"),
            ft.Text(f"🚛 Viajes: {total_viajes}"),
            ft.Text(f"🌡️ Registros de Temperatura: {total_temperaturas}"),
        ], spacing=30),
        ft.Divider(),
        ft.Text("📋 Resumen por Descarga", size=16, weight="bold"),
        tabla_resumen
    ])

# ------------------ EXPORTAR TAB ------------------
def exportar_tab(page: ft.Page):
    mensaje = ft.Text()

    def exportar_datos(e):
        try:
            conn = connect_db()
            df_descargas = pd.read_sql_query("SELECT * FROM descargas", conn)
            df_jornadas = pd.read_sql_query("SELECT * FROM jornadas", conn)
            df_viajes = pd.read_sql_query("SELECT * FROM viajes", conn)
            df_temperaturas = pd.read_sql_query("SELECT * FROM temperaturas", conn)
            conn.close()

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            filename = f"bitacora_export_{timestamp}.xlsx"

            with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
                df_descargas.to_excel(writer, sheet_name="Descargas", index=False)
                df_jornadas.to_excel(writer, sheet_name="Jornadas", index=False)
                df_viajes.to_excel(writer, sheet_name="Viajes", index=False)
                df_temperaturas.to_excel(writer, sheet_name="Temperaturas", index=False)

            mensaje.value = f"✅ Datos exportados a '{filename}'."
            mensaje.color = ft.colors.GREEN
        except Exception as ex:
            mensaje.value = f"❌ Error al exportar: {ex}"
            mensaje.color = ft.colors.RED
        page.update()

    return ft.Column([
        ft.Text("📤 Exportar Datos a Excel", size=20, weight="bold"),
        ft.ElevatedButton("Exportar a Excel", on_click=exportar_datos),
        mensaje
    ])


# ---------------- MAIN ----------------
def main(page: ft.Page):
    page.title = "🚢 Bitácora de Descarga de Barco"
    page.horizontal_alignment = "start"
    content_area = ft.Container(expand=True, padding=10)

    nav = ft.NavigationRail(
    selected_index=0,
    label_type=ft.NavigationRailLabelType.ALL,
    destinations=[
        ft.NavigationRailDestination(icon="add", label="Crear Descarga"),
        ft.NavigationRailDestination(icon="timeline", label="Jornadas"),
        ft.NavigationRailDestination(icon="local_shipping", label="Viajes"),
        ft.NavigationRailDestination(icon="thermostat", label="Temperaturas"),
        ft.NavigationRailDestination(icon="analytics", label="Resumen"),
        ft.NavigationRailDestination(icon="upload", label="Exportar"),
    ],
    on_change=lambda e: change_tab(e.control.selected_index)
)


    def change_tab(index):
        content_area.content = {
            0: crear_descarga_tab(page),
            1: jornadas_tab(page),
            2: viajes_tab(page),
            3: temperaturas_tab(page),
            4: resumen_tab(page),
            5: exportar_tab(page),
        }.get(index, ft.Text("Sección no disponible"))
        page.update()

    change_tab(0)
    page.add(ft.Row([nav, content_area], expand=True))

ft.app(target=main)



