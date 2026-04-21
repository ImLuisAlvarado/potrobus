from persistence.db import get_connection

class Bus:

    def __init__(self, id_unidad: int, numero_economico: str, modelo: str, placa: str, activo: bool):
        self.id_unidad = id_unidad
        self.numero_economico = numero_economico
        self.modelo = modelo
        self.placa = placa
        self.activo = activo

    def get_all():
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM unidad")
            return cursor.fetchall()
        except Exception as ex:
            print(f"Error get_all: {ex}")
            return []
        finally:
            if cursor: 
                cursor.close()
            if connection: 
                connection.close()

    def get_by_id(id_unidad):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM unidad WHERE id_unidad = %s", (id_unidad,))
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error get_by_id: {ex}")
            return None
        finally:
            if cursor: 
                cursor.close()
            if connection: 
                connection.close()

    def create(numero_economico, modelo, placa):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO unidad (numero_economico, modelo, placa, activo)
                VALUES (%s, %s, %s, TRUE)
            """, (numero_economico, modelo, placa))
            connection.commit()
            print(f"GUARDADO: {cursor.rowcount} filas afectadas")
            return cursor.lastrowid
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return None
        finally:
            if cursor: 
                cursor.close()
            if connection: 
                connection.close()

    def update(id_unidad, numero_economico, modelo, placa, activo):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE unidad
                SET numero_economico = %s, modelo = %s, placa = %s, activo = %s
                WHERE id_unidad = %s
            """, (numero_economico, modelo, placa, activo, id_unidad))
            connection.commit()
            print(f"ACTUALIZADO: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return False
        finally:
            if cursor: 
                cursor.close()
            if connection: 
                connection.close()

    def delete(id_unidad):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("UPDATE unidad SET activo = FALSE WHERE id_unidad = %s", (id_unidad,))
            connection.commit()
            print(f"DESACTIVADO: {cursor.rowcount} filas afectadas")
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"ERROR SQL: {ex}")
            return False
        finally:
            if cursor: 
                cursor.close()
            if connection: 
                connection.close()