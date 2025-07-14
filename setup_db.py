
import sqlite3

conn = sqlite3.connect("bitacora_descarga.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS descargas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT UNIQUE,
    barco TEXT,
    lote TEXT,
    fecha TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS jornadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave_descarga TEXT,
    fecha TEXT,
    hora_inicio TEXT,
    hora_fin TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS viajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave_descarga TEXT,
    id_jornada INTEGER,
    consecutivo TEXT,
    placa TEXT,
    estado TEXT,
    hora_inicio_cargue TEXT,
    hora_fin_cargue TEXT,
    hora_inicio_transito TEXT,
    hora_llegada_planta TEXT,
    hora_ingreso_planta TEXT,
    hora_inicio_descarga TEXT,
    hora_fin_descarga TEXT
)
''')

cursor.execute('''
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
''')

conn.commit()
conn.close()

print("Base de datos 'bitacora_descarga.db' creada correctamente.")
