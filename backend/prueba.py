from entities.user import User

"""Es una clase para realizar pruebas de registro de nuevos usarios con contraseña hasheada.
    Solo hace falta correr el programa para probarlo."""
success = User.create(
    nombre="Prueba", 
    apellido="Usuario", 
    correo="test@itson.edu.mx", 
    password="mi_password_segura", 
    rol="estudiante"
)

if success:
    print("Usuario registrado exitosamente.")