from persistence.db import get_connection

class Bus:
    """Clase que representa una unidad de transporte (Bus) y gestiona sus

    operaciones CRUD en la base de datos.
    """

    def __init__(self, id_unidad: int, numero_economico: str, modelo: str, placa: str, activo: bool):
        """Inicializa una nueva instancia de la clase Bus.

        Args:
            id_unidad (int): Identificador único de la unidad.
            numero_economico (str): Número económico asignado al bus.
            modelo (str): Modelo o año del vehículo.
            placa (str): Placa de circulación del bus.
            activo (bool): Estado operativo de la unidad (True/False).
        """
        self.id_unidad = id_unidad
        self.numero_economico = numero_economico
        self.modelo = modelo
        self.placa = placa
        self.activo = activo

    @staticmethod
    def get_all():
        """Obtiene todos los registros de la tabla unidad.

        Returns:
            list: Una lista de diccionarios con los datos de todas las unidades,
            o una lista vacía si ocurre un error.
        """
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

    @staticmethod
    def get_by_id(id_unidad):
        """Busca una unidad específica por su identificador único.

        Args:
            id_unidad (int): ID de la unidad a buscar.

        Returns:
            dict: Un diccionario con los datos de la unidad encontrada,
            o None si no se encuentra o hay un error.
        """
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

    @staticmethod
    def create(numero_economico, modelo, placa):
        """Registra una nueva unidad en la base de datos con estado activo por defecto.

        Args:
            numero_economico (str): Número económico de la nueva unidad.
            modelo (str): Modelo del bus.
            placa (str): Placa de circulación.

        Returns:
            int: El ID asignado al nuevo registro (lastrowid), o None si falla la inserción.
        """
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

    @staticmethod
    def update(id_unidad, numero_economico, modelo, placa, activo):
        """Actualiza todos los campos de una unidad existente.

        Args:
            id_unidad (int): ID de la unidad a modificar.
            numero_economico (str): Nuevo número económico.
            modelo (str): Nuevo modelo.
            placa (str): Nueva placa.
            activo (bool): Nuevo estado de actividad.

        Returns:
            bool: True si la unidad fue actualizada con éxito, False en caso contrario.
        """
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
    
    @staticmethod
    def set_status(id_unidad, activo):
        """Modifica únicamente el estado de activación de una unidad.

        Args:
            id_unidad (int): ID de la unidad a modificar.
            activo (bool): Nuevo estado (True para activo, False para inactivo).

        Returns:
            bool: True si el estado se actualizó correctamente, False en caso contrario.
        """
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE unidad
                SET activo = %s
                WHERE id_unidad = %s
            """, (activo, id_unidad))
            connection.commit()
            return cursor.rowcount > 0
        except Exception as ex:
            if connection: connection.rollback()
            print(f"Error set_status: {ex}")
            return False
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def delete(id_unidad):
        """Realiza un borrado lógico de la unidad, cambiando su estado a inactivo (FALSE).

        Args:
            id_unidad (int): ID de la unidad a desactivar.

        Returns:
            bool: True si se logró desactivar la unidad, False en caso contrario.
        """
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