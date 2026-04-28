# PotroBus - Sistema de Rastreo de Autobús Escolar

PotroBus es un sistema de seguimiento en tiempo real para autobuses escolares.  
Incluye backend API REST, panel web administrativo y aplicación móvil Android.

---

## Estructura

- `backend/` → API REST en Python/Flask con JWT, MySQL, Socket.io y WebSocket protegido.
- `web-admin/` → Panel administrador web (login, registro, mapa, gestión de rutas).

---

## Características principales

- **Autenticación segura** (registro e inicio de sesión con contraseñas hasheadas y JWT).
- **Panel administrador** con mapa de Live GPS de autobuses.
- **API REST** para gestionar unidades, rutas y posiciones GPS.
- **WebSocket** para recibir posiciones en tiempo real protegidas por token.

---

## Levantar proyecto

1. **Backend**  
   ```bash
   cd backend
   source venv/bin/activate        # o venv\Scripts\activate en Windows
   pip install -r requirements.txt
   python app.py
   ```
   Servidor: `http://127.0.0.1:5500`

2. **Web Admin**  
   ```bash
   cd web-admin
   python -m http.server 8000
   ```
   Luego abrir en el navegador:
   - `http://localhost:8000/login.html` (inicio de sesión)
   - `http://localhost:8000/registro.html` (registro de usuario)
   - `http://localhost:8000/index.html` (panel principal, solo accesible con sesión iniciada).

---

## API (endpoints)

### Salud del servicio
- `GET /api/health` → Estado del servidor.

### Autenticación
- `POST /login` → Iniciar sesión; devuelve `access_token` JWT.
- `POST /register` (implementado en tu backend) → Registrar usuario.

### Autobuses
- `GET /api/buses` → Lista de unidades.
- `POST /api/buses` → Crear autobús.
- `PUT /api/buses/<id_unidad>` → Actualizar autobús.
- `DELETE /api/buses/<id_unidad>` → Desactivar autobús.
- `GET /api/buses/<id_unidad>` → Detalle de unidad.
- `GET /api/buses/<id_unidad>/estado` → Estado de servicio (en ruta o no).

### GPS / Rastreo
- `POST /api/gps/position` → Guardar posición de un recorrido.
- `GET /api/buses/<id_unidad>/positions` → Historial de posiciones.
- `GET /api/buses/<id_unidad>/positions/latest` → Última posición.
- `GET /api/buses/<id_unidad>/recorrido-activo` → Recorrido activo de la unidad.

---

## Web Admin (pantallas)

- `login.html` → Pantalla de inicio de sesión (utiliza token JWT para acceder al panel).
- `registro.html` → Pantalla de registro de usuarios.
- `index.html` → Panel principal con mapa de posiciones en tiempo real (protegido por token JWT).

---

## Tecnologías clave

- Backend: Python, Flask, PyJWT, MySQL, Socket.io.
- Frontend web: HTML5, CSS3, JavaScript, Leaflet (mapas).
- (Proximamente) Aplicación móvil: Android Studio (Kotlin/Java).