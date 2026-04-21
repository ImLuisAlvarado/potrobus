from persistence.db import get_connection

class Location:
    def __init__(self, id_recorrido: int, latitud: float, longitud: float):
        self.id_recorrido = id_recorrido
        self.latitud = latitud
        self.longitud = longitud


    def save(id_recorrido, lat, lng):
        connection = None
        cursor = None
        try:
            print(f"Intentando guardar: id={id_recorrido}, {lat}, {lng}")
            connection = get_connection()
            cursor = connection.cursor()
            
            affected = cursor.execute("""
                INSERT INTO ubicacion (id_recorrido, latitud, longitud, fecha_captura)
                VALUES (%s, %s, %s, NOW())
            """, (id_recorrido, lat, lng))
            
            connection.commit()
            print(f"GUARDADO: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0  # True SOLO si insertó
            
        except Exception as ex:
            if connection:
                connection.rollback()
            print(f"ERROR SQL: {ex}")
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


    def get_history(id_unidad):  # ← CORREGIR AQUÍ
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.latitud AS lat, u.longitud AS lng, u.fecha_captura
                FROM ubicacion u
                JOIN recorrido r ON u.id_recorrido = r.id_recorrido
                JOIN turno     t ON r.id_turno     = t.id_turno
                WHERE t.id_unidad = %s
                ORDER BY u.fecha_captura ASC
            """, (id_unidad,))
            return cursor.fetchall()
        except Exception as ex:
            print(f"Error historial: {ex}")
            return []
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


    def get_latest(id_unidad):  # ← Si existe, corrige igual
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.latitud AS lat, u.longitud AS lng, u.fecha_captura
                FROM ubicacion u
                JOIN recorrido r ON u.id_recorrido = r.id_recorrido
                JOIN turno     t ON r.id_turno     = t.id_turno
                WHERE t.id_unidad = %s
                ORDER BY u.fecha_captura DESC
                LIMIT 1
            """, (id_unidad,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error latest: {ex}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


    def get_active_recorrido(id_unidad):
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT r.id_recorrido, r.hora_inicio, r.estado
                FROM recorrido r
                JOIN turno t ON r.id_turno = t.id_turno
                WHERE t.id_unidad = %s
                AND r.estado = 'activo'
                ORDER BY r.hora_inicio DESC
                LIMIT 1
            """, (id_unidad,))
            return cursor.fetchone()  # devuelve un diccionario con el recorrido activo
        except Exception as ex:
            print(ex)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

