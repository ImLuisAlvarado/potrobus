from persistence.db import get_connection

class Route:

    def __init__(self, id_ruta: int, nombre: str, descripcion: str, origen: str, destino: str):
        self.id_ruta = id_ruta
        self.nombre = nombre
        self.descripcion = descripcion
        self.origen = origen
        self.destino = destino

    def get_all():
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ruta")
            return cursor.fetchall()
        except Exception as ex:
            print(f"Error get_all rutas: {ex}")
            return []
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def get_by_id(id_ruta):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ruta WHERE id_ruta = %s", (id_ruta,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error get_by_id ruta: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def create(nombre, descripcion, origen, destino):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO ruta (nombre, descripcion, origen, destino)
                VALUES (%s, %s, %s, %s)
            """, (nombre, descripcion, origen, destino))
            connection.commit()
            print(f"RUTA CREADA: {cursor.rowcount} filas afectadas")
            return cursor.lastrowid
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def update(id_ruta, nombre, descripcion, origen, destino):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE ruta
                SET nombre = %s, descripcion = %s, origen = %s, destino = %s
                WHERE id_ruta = %s
            """, (nombre, descripcion, origen, destino, id_ruta))
            connection.commit()
            print(f"RUTA ACTUALIZADA: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def delete(id_ruta):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            # Hard delete — ruta no tiene historial crítico como unidad
            cursor.execute("DELETE FROM ruta WHERE id_ruta = %s", (id_ruta,))
            connection.commit()
            print(f"RUTA ELIMINADA: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    

    def get_paradas(id_ruta):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM parada 
                WHERE id_ruta = %s 
                ORDER BY orden_parada ASC
            """, (id_ruta,))
            return cursor.fetchall()
        except Exception as ex:
            print(f"Error get_paradas: {ex}")
            return []
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def add_parada(id_ruta, nombre, latitud, longitud, orden):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO parada (id_ruta, nombre, latitud, longitud, orden_parada)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_ruta, nombre, latitud, longitud, orden))
            connection.commit()
            print(f"PARADA AGREGADA: {cursor.rowcount} filas afectadas")
            return cursor.lastrowid
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def get_by_unidad(id_unidad):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT r.*
                FROM ruta r
                INNER JOIN unidad u ON u.id_ruta = r.id_ruta
                WHERE u.id_unidad = %s
            """, (id_unidad,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error get_by_unidad: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()