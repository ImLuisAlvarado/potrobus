from persistence.db import get_connection

class Driver:

    def __init__(self, id_chofer: int, nombre: str, apellido: str, telefono: str, activo: bool):
        self.id_chofer = id_chofer
        self.nombre = nombre
        self.apellido = apellido
        self.telefono = telefono
        self.activo = activo

    def get_all():
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM chofer")
            return cursor.fetchall()
        except Exception as ex:
            print(f"Error get_all choferes: {ex}")
            return []
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def get_by_id(id_chofer):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM chofer WHERE id_chofer = %s", (id_chofer,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error get_by_id chofer: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def create(nombre, apellido, telefono):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO chofer (nombre, apellido, telefono, activo)
                VALUES (%s, %s, %s, TRUE)
            """, (nombre, apellido, telefono))
            connection.commit()
            print(f"CHOFER CREADO: {cursor.rowcount} filas afectadas")
            return cursor.lastrowid
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    def update(id_chofer, nombre, apellido, telefono, activo):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE chofer
                SET nombre = %s, apellido = %s, telefono = %s, activo = %s
                WHERE id_chofer = %s
            """, (nombre, apellido, telefono, activo, id_chofer))
            connection.commit()
            print(f"CHOFER ACTUALIZADO: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
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
            cursor.execute("""
                           UPDATE chofer SET activo = %s WHERE id_chofer = %s
                           """, (activo, id_chofer))  
            connection.commit()
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"Error set_status (Driver): {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

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
            print(f"ERROR SQL: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()