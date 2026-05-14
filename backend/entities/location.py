from persistence.db import get_connection

class Location:
    def __init__(self, id_unidad: int, latitud: float, longitud: float):
        self.id_unidad = id_unidad
        self.latitud = latitud
        self.longitud = longitud

    @staticmethod
    def save(id_unidad, lat, lng):
        connection = None
        cursor = None
        try:
            print(f"Guardando GPS: unidad={id_unidad}, lat={lat}, lng={lng}")
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO ubicacion (id_unidad, latitud, longitud, fecha_captura)
                VALUES (%s, %s, %s, NOW())
            """, (id_unidad, lat, lng))
            connection.commit()
            print(f"GPS GUARDADO: {cursor.rowcount} fila(s)")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL save: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def get_latest(id_unidad):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT latitud AS lat, longitud AS lng, fecha_captura AS timestamp
                FROM ubicacion
                WHERE id_unidad = %s
                ORDER BY fecha_captura DESC
                LIMIT 1
            """, (id_unidad,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"ERROR SQL get_latest: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def get_history(id_unidad, limit=200):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT latitud AS lat, longitud AS lng, fecha_captura AS timestamp
                FROM ubicacion
                WHERE id_unidad = %s
                ORDER BY fecha_captura DESC
                LIMIT %s
            """, (id_unidad, limit))
            return cursor.fetchall()
        except Exception as ex:
            print(f"ERROR SQL get_history: {ex}")
            return []
        finally:
            if cursor: cursor.close()
            if connection: connection.close()