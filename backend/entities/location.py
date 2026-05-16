from persistence.db import get_connection

class Location:
    """
    Representa y gestiona la información geográfica y el historial de ubicación
    de las unidades de transporte en la base de datos.
    """

    def __init__(self, id_unidad: int, latitud: float, longitud: float):
        """
        Inicializa una nueva instancia de la clase Location.

        Args:
            id_unidad (int): Identificador único de la unidad.
            latitud (float): Coordenada de latitud geográfica.
            longitud (float): Coordenada de longitud geográfica.
        """
        self.id_unidad = id_unidad
        self.latitud = latitud
        self.longitud = longitud

    @staticmethod
    def save(id_unidad: int, lat: float, lng: float) -> bool:
        """
        Registra una nueva coordenada geográfica para una unidad específica.

        Args:
            id_unidad (int): Identificador único de la unidad.
            lat (float): Coordenada de latitud.
            lng (float): Coordenada de longitud.

        Returns:
            bool: True si la ubicación se guardó correctamente, False en caso contrario.
        """
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO ubicacion (id_unidad, latitud, longitud, fecha_captura)
                VALUES (%s, %s, %s, NOW())
            """, (id_unidad, lat, lng))
            connection.commit()
            return cursor.rowcount > 0
        except Exception:
            if connection:
                connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def get_latest(id_unidad: int) -> dict | None:
        """
        Obtiene la última ubicación registrada de una unidad en particular.

        Args:
            id_unidad (int): Identificador único de la unidad.

        Returns:
            dict: Un diccionario con las claves 'lat', 'lng' y 'timestamp' si existe.
            None: Si no se encuentran registros o si ocurre un error.
        """
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
        except Exception:
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def get_history(id_unidad: int, limit: int = 200) -> list:
        """
        Recupera el historial de ubicaciones de una unidad ordenada de la más reciente
        a la más antigua.

        Args:
            id_unidad (int): Identificador único de la unidad.
            limit (int, opcional): Número máximo de registros a retornar. Por defecto es 200.

        Returns:
            list: Una lista de diccionarios, donde cada uno contiene 'lat', 'lng' y 'timestamp'.
                  Retorna una lista vacía si no hay registros o ante un error.
        """
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
        except Exception:
            return []
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()