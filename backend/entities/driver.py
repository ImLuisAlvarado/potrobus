from persistence.db import get_connection
import hashlib

class Driver:
    """Clase que representa a un chofer y gestiona sus operaciones CRUD

    y de autenticación en la base de datos.
    """

    def __init__(self, id_chofer: int, nombre: str, apellido: str, telefono: str, activo: bool):
        """Inicializa una nueva instancia de la clase Driver.

        Args:
            id_chofer (int): Identificador único del chofer.
            nombre (str): Nombre(s) del chofer.
            apellido (str): Apellido(s) del chofer.
            telefono (str): Número de teléfono de contacto.
            activo (bool): Estado operativo del chofer en el sistema.
        """
        self.id_chofer = id_chofer
        self.nombre = nombre
        self.apellido = apellido
        self.telefono = telefono
        self.activo = activo

    @staticmethod
    def get_all():
        """Obtiene la lista completa de choferes junto con el número económico de la unidad asignada.

        Returns:
            list: Una lista de diccionarios con la información detallada de los choferes,
            incluyendo datos de su unidad si tienen una asociada.
        """
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
        """Busca un chofer específico por su ID, recuperando también el número económico de su unidad.

        Args:
            id_chofer (int): Identificador único del chofer a buscar.

        Returns:
            dict: Un diccionario con los datos del chofer si se encuentra, u None si no existe o falla.
        """
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
        """Valida las credenciales de acceso de un chofer mediante correo electrónico y contraseña.

        La contraseña proporcionada es encriptada en SHA-256 para compararla con el hash almacenado.
        Solo permite el acceso a cuentas que tengan el estado activo como verdadero.

        Args:
            correo (str): Correo electrónico del chofer.
            password (str): Contraseña en texto plano a verificar.

        Returns:
            dict: Datos básicos del chofer y su unidad asignada si la autenticación es correcta,
            u None en caso de credenciales inválidas o error de conexión.
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
        """Registra un nuevo chofer en la base de datos con estado activo por defecto.

        Si se proporciona una contraseña, se almacena de forma segura utilizando un hash SHA-256.

        Args:
            nombre (str): Nombre del chofer.
            apellido (str): Apellido del chofer.
            telefono (str): Teléfono del chofer.
            id_unidad (int, optional): ID de la unidad de transporte asignada. Por defecto es None.
            correo (str, optional): Correo electrónico para el inicio de sesión. Por defecto es None.
            password (str, optional): Contraseña en texto plano para el inicio de sesión. Por defecto es None.

        Returns:
            int: El identificador único del nuevo registro generado (lastrowid), o None si falla.
        """
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
        """Actualiza la información de un chofer existente en el sistema.

        Evalúa si se envía una nueva contraseña para actualizar su hash; de lo contrario,
        mantiene intacta la contraseña existente en la base de datos.

        Args:
            id_chofer (int): ID del chofer a modificar.
            nombre (str): Nuevo o actual nombre.
            apellido (str): Nuevo o actual apellido.
            telefono (str): Nuevo o actual teléfono.
            activo (bool): Nuevo estado de actividad.
            id_unidad (int, optional): Nueva unidad asignada. Por defecto es None.
            correo (str, optional): Nuevo correo de acceso. Por defecto es None.
            password (str, optional): Nueva contraseña en texto plano si se desea cambiar. Por defecto es None.

        Returns:
            bool: True si el registro fue actualizado de manera exitosa, False en caso contrario.
        """
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
        """Actualiza exclusivamente el estado lógico de actividad de un chofer.

        Args:
            id_chofer (int): ID del chofer a modificar.
            activo (bool): Estado a asignar (True para habilitado, False para deshabilitado).

        Returns:
            bool: True si el cambio de estado se guardó correctamente, False de lo contrario.
        """
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
        """Realiza un borrado lógico del chofer, estableciendo su columna activo en FALSE.

        Args:
            id_chofer (int): ID del chofer a desactivar.

        Returns:
            bool: True si se ejecutó la desactivación correctamente, False si ocurrió un error.
        """
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