import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def connect_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def clear_test_data():
    try:
        conn = connect_db()
        cursor = conn.cursor()

        # Puedes personalizar los criterios de prueba según tus datos (ejemplo: por barco o fecha)
        # Aquí se eliminan descargas de prueba con barcos que contengan 'TEST' o fecha anterior a hoy
        cursor.execute("DELETE FROM temperaturas WHERE clave_descarga LIKE '%TEST%'")
        cursor.execute("DELETE FROM viajes WHERE clave_descarga LIKE '%TEST%'")
        cursor.execute("DELETE FROM jornadas WHERE clave_descarga LIKE '%TEST%'")
        cursor.execute("DELETE FROM descargas WHERE barco LIKE '%TEST%'")

        conn.commit()
        conn.close()
        print("✅ Datos de prueba eliminados exitosamente.")
    except Exception as e:
        print("❌ Error al limpiar los datos de prueba:", e)

if __name__ == "__main__":
    clear_test_data()
