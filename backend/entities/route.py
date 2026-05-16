from persistence.db import get_connection

class Route:
    """
    Representa una ruta de transporte y gestiona sus operaciones CRUD y relaciones
    con la base de datos.
    """

    def __init__(self, id_ruta: int, nombre: str, descripcion: str, origen: str, destino: str):
        """
        Inicializa una nueva instancia de la clase Route.

        Args:
            id_ruta (int): Identificador único de la ruta.
            nombre (str): Nombre comercial o identificativo de la ruta.
            descripcion (str): Detalle o información adicional sobre el trayecto.
            origen (str): Punto de partida de la ruta.
            destino (str): Punto final de la ruta.
        """
        self.id_ruta = id_ruta
        self.nombre = nombre
        self.descripcion = descripcion
        self.origen = origen
        self.destino = destino

    @staticmethod
    def get_all():
        """
        Obtiene todas las rutas registradas en la base de datos.

        Returns:
            list: Una lista de diccionarios con los datos de cada ruta, 
                  o una lista vacía si ocurre un error.
        """
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

    @staticmethod
    def get_by_id(id_ruta):
        """
        Busca una ruta específica mediante su identificador.

        Args:
            id_ruta (int): ID de la ruta a buscar.

        Returns:
            dict: Los datos de la ruta encontrada, o None si no existe o hay un error.
        """
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

    @staticmethod
    def create(nombre, descripcion, origen, destino):
        """
        Crea e inserta una nueva ruta en la base de datos.

        Args:
            nombre (str): Nombre de la ruta.
            descripcion (str): Descripción de la ruta.
            origen (str): Punto de origen.
            destino (str): Punto de destino.

        Returns:
            int: El ID de la nueva ruta creada, o None si la operación falla.
        """
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

    @staticmethod
    def update(id_ruta, nombre, descripcion, origen, destino):
        """
        Actualiza los datos de una ruta existente.

        Args:
            id_ruta (int): ID de la ruta a modificar.
            nombre (str): Nuevo nombre de la ruta.
            descripcion (str): Nueva descripción.
            origen (str): Nuevo origen.
            destino (str): Nuevo destino.

        Returns:
            bool: True si la ruta fue actualizada con éxito, False en caso contrario.
        """
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

    @staticmethod
    def delete(id_ruta):
        """
        Elimina de forma permanente una ruta de la base de datos.

        Args:
            id_ruta (int): ID de la ruta a eliminar.

        Returns:
            bool: True si la ruta fue eliminada, False si no se afectaron filas o hubo error.
        """
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
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

    @staticmethod
    def get_by_unidad(id_unidad):
        """
        Obtiene la ruta asignada a una unidad de transporte específica.

        Args:
            id_unidad (int): ID de la unidad.

        Returns:
            dict: Los datos de la ruta asignada, o None si ocurre un error.
        """
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ruta WHERE id_ruta = 1")
            return cursor.fetchone()
        except Exception as ex:
            print(f"Error get_by_unidad: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def get_paradas(id_ruta):
        """
        Obtiene la lista de paradas asociadas a una ruta, ordenadas ascendentemente.

        Args:
            id_ruta (int): ID de la ruta de la cual se quieren consultar las paradas.

        Returns:
            list: Lista de diccionarios con las paradas de la ruta, 
                  o una lista vacía si no hay registros o hay un error.
        """
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

    @staticmethod
    def add_parada(id_ruta, nombre, latitud, longitud, orden):
        """
        Registra y asocia una nueva parada a una ruta específica.

        Args:
            id_ruta (int): ID de la ruta a la que pertenecerá la parada.
            nombre (str): Nombre o punto de referencia de la parada.
            latitud (float/str): Coordenada de latitud de la ubicación.
            longitud (float/str): Coordenada de longitud de la ubicación.
            orden (int): Posición o secuencia de la parada dentro del trayecto.

        Returns:
            int: El ID de la nueva parada creada, o None si ocurre un error.
        """
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