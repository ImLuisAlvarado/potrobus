from werkzeug.security import generate_password_hash, check_password_hash
from persistence.db import get_connection


"""Clase para el manejo de usuarios (registro, contraseñas protegidas, busqueda por correo, etc.)"""
class User:
    @staticmethod
    def create(nombre, apellido, correo, password, rol):

        hashed_pw = generate_password_hash(password)


        connection = None
        cursor = None
        try:
            print(f"Intentando guardar: {nombre, apellido, correo, rol}")
            connection = get_connection()
            cursor = connection.cursor()
            
            query = """
            INSERT INTO usuario (nombre, apellido, correo, password_hash, rol)
            VALUES (%s, %s, %s, %s, %s)
        """

            affected = cursor.execute(query, (nombre, apellido, correo, hashed_pw, rol))
            
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

    
    @staticmethod
    def get_by_email(correo):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            
            query = "SELECT * FROM usuario WHERE correo = %s"
            cursor.execute(query, (correo,))
            user = cursor.fetchone()
            
            return user
            
        except Exception as ex:
            print(f"ERROR DB: {ex}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

    @staticmethod
    def verify_login(correo, password):
        user = User.get_by_email(correo)
        
        if user and check_password_hash(user['password_hash'], password):
            user.pop('password_hash', None) 
            return user
            
        return None