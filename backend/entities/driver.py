from persistence.db import get_connection
import hashlib

class Driver:

    def __init__(self, id_chofer: int, nombre: str, apellido: str, telefono: str, activo: bool):
        self.id_chofer = id_chofer
        self.nombre = nombre
        self.apellido = apellido
        self.telefono = telefono
        self.activo = activo

    @staticmethod
    def get_all():
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.*, u.numero_economico
                FROM chofer c
                LEFT JOIN unidad u ON c.id_unidad = u.id_unidad
            """)
            return cursor.fetchall()
        except Exception as ex:
            print(f"Error get_all choferes: {ex}")
            return []
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def get_by_id(id_chofer):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.*, u.numero_economico
                FROM chofer c
                LEFT JOIN unidad u ON c.id_unidad = u.id_unidad
                WHERE c.id_chofer = %s
            """, (id_chofer,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error get_by_id chofer: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def verify_login(correo, password):
        """
        Verifica credenciales del chofer para login desde la app Kotlin.
        Devuelve el chofer (dict) si son validas, None si no.
        """
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute("""
                SELECT c.id_chofer, c.nombre, c.apellido, c.id_unidad,
                       u.numero_economico, u.placa
                FROM chofer c
                LEFT JOIN unidad u ON c.id_unidad = u.id_unidad
                WHERE c.correo = %s AND c.password = %s AND c.activo = TRUE
            """, (correo, pwd_hash))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error verify_login chofer: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def create(nombre, apellido, telefono, id_unidad=None, correo=None, password=None):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            pwd_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
            cursor.execute("""
                INSERT INTO chofer (nombre, apellido, telefono, activo, id_unidad, correo, password)
                VALUES (%s, %s, %s, TRUE, %s, %s, %s)
            """, (nombre, apellido, telefono, id_unidad, correo, pwd_hash))
            connection.commit()
            print(f"CHOFER CREADO: {cursor.rowcount} filas afectadas")
            return cursor.lastrowid
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL create chofer: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def update(id_chofer, nombre, apellido, telefono, activo, id_unidad=None, correo=None, password=None):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            if password:
                pwd_hash = hashlib.sha256(password.encode()).hexdigest()
                cursor.execute("""
                    UPDATE chofer
                    SET nombre = %s, apellido = %s, telefono = %s, activo = %s,
                        id_unidad = %s, correo = %s, password = %s
                    WHERE id_chofer = %s
                """, (nombre, apellido, telefono, activo, id_unidad, correo, pwd_hash, id_chofer))
            else:
                cursor.execute("""
                    UPDATE chofer
                    SET nombre = %s, apellido = %s, telefono = %s, activo = %s,
                        id_unidad = %s, correo = %s
                    WHERE id_chofer = %s
                """, (nombre, apellido, telefono, activo, id_unidad, correo, id_chofer))
            connection.commit()
            print(f"CHOFER ACTUALIZADO: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL update chofer: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def set_status(id_chofer, activo):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("UPDATE chofer SET activo = %s WHERE id_chofer = %s", (activo, id_chofer))
            connection.commit()
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"Error set_status (Driver): {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def delete(id_chofer):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("UPDATE chofer SET activo = FALSE WHERE id_chofer = %s", (id_chofer,))
            connection.commit()
            print(f"CHOFER DESACTIVADO: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL delete chofer: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()