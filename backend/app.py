from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from messaging import publish_notificacion, publish_gps_kafka, start_messaging_consumers, set_socketio
from kafka_consumer import start_kafka_consumer, analizar_coordenada, get_paradas_visitadas
import jwt
import random
import logging
import threading
import time
from entities.location import Location
from entities.bus import Bus
from entities.user import User
from entities.route import Route
from entities.driver import Driver
from tokenManager import create_token, token_required
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)

logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('pika').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)
logging.getLogger('socketio').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.INFO)

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)
set_socketio(socketio)

MODO_SIMULACION = False


@app.route("/api/health")
def health():
    """
    Verifica el estado de salud y disponibilidad del servicio backend.

    Returns:
        Response: Objeto JSON con el estado 'ok' y el nombre del servicio.
    """
    return jsonify({"status": "ok", "service": "potrobus-backend"})


@app.route('/login', methods=['POST'])
def login():
    """
    Autentica a un usuario administrador o estudiante mediante sus credenciales.

    Returns:
        tuple: (JSON con el token de acceso y datos del usuario, 200) si es exitoso,
               (JSON con mensaje de error, 401) si las credenciales son incorrectas.
    """
    data = request.json
    usuario = User.verify_login(data['correo'], data['password'])
    
    if usuario:
        token = create_token(usuario)
        return {
            "message": "Login exitoso",
            "access_token": token,
            "user": usuario
        }, 200
    
    return {"message": "Credenciales inválidas"}, 401


@app.route('/api/register', methods=['POST'])
def register():
    """
    Registra un nuevo usuario en la plataforma.

    Returns:
        tuple: (JSON de confirmación, 201) si se crea con éxito,
               (JSON de error, 400) si faltan datos requeridos,
               (JSON de error, 409) si el correo ya está registrado,
               (JSON de error, 500) ante fallos internos de la base de datos.
    """
    data = request.json
    if not data or not data.get('correo') or not data.get('password'):
        return jsonify({"error": "faltan campos"}), 400
    
    result = User.create(
        data.get('nombre', ''),
        data.get('apellido', ''),
        data.get('correo'),
        data.get('password'),
        data.get('rol', 'estudiante')
    )

    if result["success"]:
        return jsonify({"msg": "usuario registrado"}), 201
    elif result["error"] == "correo_duplicado":
        return jsonify({"error": "El correo ya está registrado"}), 409
    else:
        return jsonify({"error": "no se pudo registrar"}), 500


@app.route('/api/test-auth', methods=['GET'])
@token_required
def test_auth(current_user):
    """
    Endpoint protegido para validar la vigencia y decodificación del JSON Web Token.

    Args:
        current_user (dict): Datos del usuario actual inyectados por el decorador de auth.

    Returns:
        tuple: (JSON con la confirmación de acceso y la identidad decodificada, 200).
    """
    return jsonify({
        "message": "Acceso autorizado",
        "datos_usuario": current_user
    }), 200


@app.route("/api/buses", methods=["GET"])
def list_buses():
    """
    Retorna el listado completo de unidades vehiculares dadas de alta.

    Returns:
        Response: Lista en formato JSON con todas las unidades registradas.
    """
    data = Bus.get_all()
    return jsonify(data)


@app.route("/api/buses/activos", methods=["GET"])
def list_buses_activos():
    """
    Filtra y retorna únicamente las unidades vehiculares habilitadas.

    Returns:
        Response: Lista en formato JSON de autobuses que tienen el estado activo.
    """
    data = Bus.get_all()
    activos = [bus for bus in data if bus.get("activo")]
    return jsonify(activos)


@app.route("/api/buses", methods=["POST"])
def create_bus():
    """
    Crea un nuevo registro de autobús en el sistema.

    Returns:
        tuple: (JSON con el ID asignado a la unidad, 201) si fue creada,
               (JSON de error, 400) si faltan datos obligatorios,
               (JSON de error, 500) si no se pudo persistir en base de datos.
    """
    data = request.json
    if not data or not data.get("numero_economico") or not data.get("placa"):
        return jsonify({"error": "faltan campos requeridos"}), 400

    new_id = Bus.create(
        data.get("numero_economico"),
        data.get("modelo", ""),
        data.get("placa")
    )
    if new_id:
        return jsonify({"msg": "unidad creada", "id_unidad": new_id}), 201
    return jsonify({"error": "no se pudo crear"}), 500


@app.route("/api/buses/<int:id_unidad>", methods=["PUT"])
def update_bus(id_unidad):
    """
    Actualiza la información técnica de una unidad vehicular existente.

    Args:
        id_unidad (int): Identificador numérico de la unidad a modificar.

    Returns:
        tuple: (JSON de confirmación, 200) si se modificaron datos,
               (JSON de error, 400) si el cuerpo de la petición está vacío,
               (JSON de error, 404) si la unidad no existe o no hubo cambios.
    """
    data = request.json
    if not data:
        return jsonify({"error": "sin datos"}), 400
    
    ok = Bus.update(
        id_unidad,
        data.get("numero_economico"),
        data.get("modelo", ""),
        data.get("placa"),
        data.get("activo", True)
    )
    if ok:
        return jsonify({"msg": "unidad actualizada"})
    return jsonify({"error": "no encontrada o sin cambios"}), 404


@app.route("/api/buses/<int:id_unidad>/status", methods=["PATCH"])
def toggle_bus_status(id_unidad):
    """
    Modifica parcialmente el estado operativo (activo/inactivo) de un autobús.

    Args:
        id_unidad (int): Identificador de la unidad.

    Returns:
        tuple: (JSON con el nuevo estado del vehículo, 200),
               (JSON de error, 400) si falta el parámetro booleano de estado,
               (JSON de error, 404) si no se localiza la unidad.
    """
    data = request.json
    nuevo_estado = data.get("activo")

    if nuevo_estado is None:
        return jsonify({"error": "Falta el campo 'activo'"}), 400

    ok = Bus.set_status(id_unidad, nuevo_estado)

    if ok:
        estado_str = "activado" if nuevo_estado else "desactivado"
        return jsonify({"msg": f"Unidad {estado_str} con éxito"}), 200
    return jsonify({"error": "No se pudo actualizar el estado o unidad no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>", methods=["DELETE"])
def delete_bus(id_unidad):
    """
    Desactiva de forma lógica un autobús del sistema (baja operativa).

    Args:
        id_unidad (int): Identificador de la unidad a desactivar.

    Returns:
        tuple: (JSON con confirmación de desactivación, 200),
               (JSON de error, 404) si no se encontró el registro.
    """
    ok = Bus.delete(id_unidad)
    if ok:
        return jsonify({"msg": "unidad desactivada"})
    return jsonify({"error": "no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>", methods=["GET"])
def get_bus(id_unidad):
    """
    Obtiene los detalles informativos de un autobús específico mediante su ID.

    Args:
        id_unidad (int): Identificador único de la unidad.

    Returns:
        Response: JSON con los datos del autobús (200) o un error (404) si no existe.
    """
    data = Bus.get_by_id(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"error": "unidad no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>/estado", methods=["GET"])
def get_estado_bus(id_unidad):
    """
    Consulta si una unidad en particular está ejecutando una ruta activa actualmente.

    Args:
        id_unidad (int): Identificador de la unidad.

    Returns:
        Response: JSON estructurado detallando la información de la unidad,
                  un booleano indicando si brinda servicio y los datos geográficos actuales.
    """
    bus = Bus.get_by_id(id_unidad)
    if not bus:
        return jsonify({"error": "unidad no encontrada"}), 404
    
    recorrido = Location.get_active_recorrido(id_unidad)
    return jsonify({
        "unidad": bus,
        "en_servicio": recorrido is not None,
        "recorrido_activo": recorrido
    })


@app.route("/api/buses/<int:id_unidad>/positions", methods=["GET"])
def get_bus_positions(id_unidad):
    """
    Recupera el registro histórico de telemetría de ubicaciones de un autobús.

    Args:
        id_unidad (int): Identificador de la unidad.

    Returns:
        Response: JSON con el arreglo de coordenadas históricas (200) o mensaje vacío (404).
    """
    data = Location.get_history(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"msg": "sin datos"}), 404


@app.route("/api/buses/<int:id_unidad>/positions/latest", methods=["GET"])
def get_latest_position(id_unidad):
    """
    Obtiene la última coordenada conocida y estampilla de tiempo de un autobús.

    Args:
        id_unidad (int): Identificador de la unidad.

    Returns:
        Response: JSON con latitud, longitud y timestamp (200) o error controlado (404).
    """
    data = Location.get_latest(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"error": "sin_posicion"}), 404


@app.route("/api/gps/position", methods=["POST"])
def ingest_position():
    """
    Punto de entrada de telemetría para la ingesta de coordenadas en tiempo real.
    Persiste en base de datos, envía a un clúster de Kafka para análisis de geocercas
    y retransmite vía WebSockets directos al mapa del frontend.

    Returns:
        tuple: (JSON de confirmación de guardado, 201) o (JSON con detalles de error, 400).
    """
    data = request.json
    if not data or data.get("id_unidad") is None or data.get("lat") is None or data.get("lng") is None:
        return jsonify({"error": "Faltan campos: id_unidad, lat, lng"}), 400

    id_unidad = data.get("id_unidad")
    lat       = data.get("lat")
    lng       = data.get("lng")
    bus_id    = data.get("bus_id", f"unidad-{id_unidad}")
    timestamp = data.get("timestamp", "")

    Location.save(id_unidad, lat, lng)

    publish_gps_kafka(lat, lng, bus_id=bus_id, id_unidad=id_unidad)

    socketio.emit('gps_live', {
        "lat":       lat,
        "lng":       lng,
        "id_unidad": id_unidad,
        "bus_id":    bus_id,
        "timestamp": timestamp
    })
    return jsonify({"msg": "posición guardada"}), 201


@app.route("/api/rutas", methods=["GET"])
def list_rutas():
    """
    Retorna los trayectos y rutas de transporte registradas en el sistema.

    Returns:
        Response: Lista en formato JSON de todas las rutas de transporte.
    """
    data = Route.get_all()
    return jsonify(data)


@app.route("/api/rutas/<int:id_ruta>", methods=["GET"])
def get_ruta(id_ruta):
    """
    Obtiene los parámetros y la descripción de una ruta por medio de su ID.

    Args:
        id_ruta (int): Identificador de la ruta solicitada.

    Returns:
        Response: JSON con los metadatos de la ruta (200) o un error de no encontrado (404).
    """
    data = Route.get_by_id(id_ruta)
    if data:
        return jsonify(data)
    return jsonify({"error": "ruta no encontrada"}), 404


@app.route("/api/rutas", methods=["POST"])
def create_ruta():
    """
    Registra una nueva ruta de transporte con sus respectivos puntos de origen y destino.

    Returns:
        tuple: (JSON con los detalles de la ruta creada, 201) o (JSON con error de campos, 400)
               o (JSON con error de base de datos, 500).
    """
    data = request.json
    if not data or not data.get("nombre") or not data.get("origen") or not data.get("destino"):
        return jsonify({"error": "faltan campos requeridos"}), 400
    new_id = Route.create(
        data.get("nombre"),
        data.get("descripcion", ""),
        data.get("origen"),
        data.get("destino")
    )
    if new_id:
        return jsonify({"msg": "ruta creada", "id_ruta": new_id}), 201
    return jsonify({"error": "no se pudo crear"}), 500


@app.route("/api/rutas/<int:id_ruta>", methods=["PUT"])
def update_ruta(id_ruta):
    """
    Actualiza completamente la información estructural de una ruta existente.

    Args:
        id_ruta (int): Identificador de la ruta a modificar.

    Returns:
        tuple: (JSON con mensaje de éxito, 200), (JSON de error por falta de datos, 400)
               o (JSON de error por ruta no encontrada, 404).
    """
    data = request.json
    if not data:
        return jsonify({"error": "sin datos"}), 400
    ok = Route.update(
        id_ruta,
        data.get("nombre"),
        data.get("descripcion", ""),
        data.get("origen"),
        data.get("destino")
    )
    if ok:
        return jsonify({"msg": "ruta actualizada"})
    return jsonify({"error": "no encontrada o sin cambios"}), 404


@app.route("/api/rutas/<int:id_ruta>", methods=["DELETE"])
def delete_ruta(id_ruta):
    """
    Elimina físicamente una ruta del sistema de transporte.

    Args:
        id_ruta (int): Identificador de la ruta a eliminar.

    Returns:
        tuple: (JSON de confirmación, 200) o (JSON de error por ID inexistente, 404).
    """
    ok = Route.delete(id_ruta)
    if ok:
        return jsonify({"msg": "ruta eliminada"})
    return jsonify({"error": "no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>/paradas-pendientes", methods=["GET"])
def get_paradas_pendientes(id_unidad):
    """
    Calcula dinámicamente qué paradas han sido visitadas o quedan pendientes para
    una unidad en su trayecto activo actual, cruzando los datos geográficos mapeados de la ruta 
    con el estado de geocercas procesado en Kafka.

    Args:
        id_unidad (int): Identificador de la unidad en monitoreo.

    Returns:
        Response: JSON compuesto por la lista de paradas ordenadas junto con un estado booleano 'visitada'.
    """
    paradas = Route.get_paradas(1)
    visitadas = get_paradas_visitadas(id_unidad)

    for p in paradas:
        p["visitada"] = p["id_parada"] in visitadas

    return jsonify(paradas)


@app.route("/api/rutas/<int:id_ruta>/paradas", methods=["GET"])
def get_paradas(id_ruta):
    """
    Lista todos los puntos geográficos de parada que componen una ruta dada.

    Args:
        id_ruta (int): Identificador de la ruta.

    Returns:
        Response: JSON con la lista ordenada de estaciones o paradas asociadas.
    """
    data = Route.get_paradas(id_ruta)
    return jsonify(data)


@app.route("/api/rutas/<int:id_ruta>/paradas", methods=["POST"])
def add_parada(id_ruta):
    """
    Añade un nuevo punto geográfico oficial de parada o estación a una ruta de transporte.

    Args:
        id_ruta (int): Identificador de la ruta objetivo.

    Returns:
        tuple: (JSON con la confirmación de la parada añadida, 201), (JSON de error de entrada, 400)
               o (JSON indicando fallo de registro, 500).
    """
    data = request.json
    if not data or not data.get("nombre"):
        return jsonify({"error": "faltan campos requeridos"}), 400
    new_id = Route.add_parada(
        id_ruta,
        data.get("nombre"),
        data.get("latitud"),
        data.get("longitud"),
        data.get("orden", 1)
    )
    if new_id:
        return jsonify({"msg": "parada agregada", "id_parada": new_id}), 201
    return jsonify({"error": "no se pudo agregar"}), 500


@app.route("/api/choferes/login", methods=["POST"])
def login_chofer():
    """
    Autentica a un conductor o chofer en el sistema y verifica si cuenta con una 
    unidad vehicular asignada para iniciar el envío de telemetría.

    Returns:
        tuple: (JSON con el token JWT adaptado al rol 'chofer' y metadatos de su autobús, 200),
               (JSON de credenciales inválidas, 401) o (JSON si el conductor no tiene unidad asignada, 403).
    """
    data = request.json
    if not data or not data.get("correo") or not data.get("password"):
        return jsonify({"error": "Faltan correo o password"}), 400

    chofer = Driver.verify_login(data["correo"], data["password"])
    if not chofer:
        return jsonify({"error": "Credenciales inválidas o chofer inactivo"}), 401

    if not chofer.get("id_unidad"):
        return jsonify({"error": "El chofer no tiene unidad asignada"}), 403

    token = create_token({
        "id_usuario": chofer["id_chofer"],
        "correo":     chofer.get("correo", ""),
        "rol":        "chofer"
    })
    return jsonify({
        "access_token": token,
        "chofer": {
            "id_chofer":       chofer["id_chofer"],
            "nombre":          chofer["nombre"],
            "apellido":        chofer["apellido"],
            "id_unidad":       chofer["id_unidad"],
            "numero_economico": chofer.get("numero_economico"),
            "placa":           chofer.get("placa")
        }
    }), 200


@app.route("/api/choferes", methods=["GET"])
def list_choferes():
    """
    Obtiene el catálogo total de conductores en el sistema.

    Returns:
        Response: Lista JSON de conductores registrados.
    """
    data = Driver.get_all()
    return jsonify(data)


@app.route("/api/choferes/<int:id_chofer>", methods=["GET"])
def get_chofer(id_chofer):
    """
    Obtiene el expediente detallado de un conductor por medio de su ID.

    Args:
        id_chofer (int): Identificador del conductor.

    Returns:
        Response: JSON con los datos del chofer (200) o error de inexistencia (404).
    """
    data = Driver.get_by_id(id_chofer)
    if data:
        return jsonify(data)
    return jsonify({"error": "chofer no encontrado"}), 404


@app.route("/api/choferes", methods=["POST"])
def create_chofer():
    """
    Registra un nuevo conductor, vinculándole opcionalmente a un autobús y un número telefónico.

    Returns:
        tuple: (JSON con el ID del chofer creado, 201) o (JSON con error de validación, 400)
               o (JSON con error de guardado, 500).
    """
    data = request.json
    if not data or not data.get("nombre") or not data.get("apellido"):
        return jsonify({"error": "faltan campos requeridos"}), 400
    new_id = Driver.create(
        data.get("nombre"),
        data.get("apellido"),
        data.get("telefono", ""),
        data.get("id_unidad"),
        data.get("correo"),
        data.get("password")
    )
    if new_id:
        return jsonify({"msg": "chofer creado", "id_chofer": new_id}), 201
    return jsonify({"error": "no se pudo crear"}), 500


@app.route("/api/choferes/<int:id_chofer>", methods=["PUT"])
def update_chofer(id_chofer):
    """
    Modifica la información general de un conductor y permite la actualización de credenciales.

    Args:
        id_chofer (int): Identificador del conductor.

    Returns:
        tuple: (JSON de confirmación, 200), (JSON de error de payload, 400) o (JSON si no se alteró la fila, 404).
    """
    data = request.json
    if not data:
        return jsonify({"error": "sin datos"}), 400
    ok = Driver.update(
        id_chofer,
        data.get("nombre"),
        data.get("apellido"),
        data.get("telefono", ""),
        data.get("activo", True),
        data.get("id_unidad"),
        data.get("correo"),
        data.get("password")
    )
    if ok:
        return jsonify({"msg": "chofer actualizado"})
    return jsonify({"error": "no encontrado o sin cambios"}), 404


@app.route("/api/choferes/<int:id_chofer>/status", methods=["PATCH"])
def toggle_chofer_status(id_chofer):
    """
    Habilita o inhabilita el estatus de ingreso a la plataforma para un conductor.

    Args:
        id_chofer (int): Identificador del conductor.

    Returns:
        tuple: (JSON indicando el nuevo estado, 200), (JSON si falta el argumento activo, 400)
               o (JSON si ocurrió un fallo al modificar, 404).
    """
    data = request.json
    nuevo_estado = data.get("activo")

    if nuevo_estado is None:
        return jsonify({"error": "Falta el campo 'activo'"}), 400
    
    ok = Driver.set_status(id_chofer, nuevo_estado)

    if ok:
        estado_str = "activado" if nuevo_estado else "desactivado"
        return jsonify({"msg": f"Chofer {estado_str} con éxito"}), 200
    
    return jsonify({"error": "No se pudo actualizar el estado del chofer"}), 404


@app.route("/api/choferes/<int:id_chofer>", methods=["DELETE"])
def delete_chofer(id_chofer):
    """
    Remueve o inhabilita a un conductor de la base de datos operativa.

    Args:
        id_chofer (int): Identificador único del chofer.

    Returns:
        tuple: (JSON con la confirmación del borrado, 200) o (JSON con error, 404).
    """
    ok = Driver.delete(id_chofer)
    if ok:
        return jsonify({"msg": "chofer desactivado"})
    return jsonify({"error": "no encontrado"}), 404


@app.route("/api/notificaciones", methods=["POST"])
def send_notificacion():
    """
    Publica una alerta o aviso masivo hacia las colas de mensajería (RabbitMQ/Push) del sistema.

    Returns:
        tuple: (JSON con confirmación de envío, 201) o (JSON si faltan parámetros, 400)
               o (JSON si falló el broker de mensajería, 500).
    """
    data = request.json
    if not data or not data.get("tipo") or not data.get("mensaje"):
        return jsonify({"error": "faltan campos"}), 400

    ok = publish_notificacion(
        data.get("tipo"),
        data.get("mensaje"),
        data.get("id_recorrido")
    )
    if ok:
        return jsonify({"msg": "notificación enviada"}), 201
    return jsonify({"error": "no se pudo enviar"}), 500


@socketio.on('connect')
def handle_connect():
    """
    Valida e intercepta los intentos de conexión WebSocket del cliente del mapa o panel,
    extrayendo y decodificando el parámetro JWT de los argumentos de consulta.

    Returns:
        bool: True si la sesión WebSocket es autorizada, False si el token expiró,
              es inválido o está ausente.
    """
    try:
        token = request.args.get('token')

        if not token:
            return False

        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return True

        except jwt.ExpiredSignatureError:
            return False

        except jwt.InvalidTokenError:
            return False

    except Exception:
        return False


@socketio.on('test')
def handle_test(data):
    """
    Manejador de eventos para pruebas sencillas de comunicación dúplex WebSocket.

    Args:
        data (dict/str): Información de prueba enviada desde el frontend.
    """
    pass


def gps_simulador_simple():
    """
    Hilo secundario continuo (Daemon Thread) encargado de simular el movimiento físico de una unidad
    sobre coordenadas preestablecidas de la ruta de ITSON en ciclos infinitos. Realiza inserciones en
    la base de datos y emite actualizaciones en vivo mediante Kafka y WebSockets cada 5 segundos.
    """
    ruta = [
        (27.9530, -110.8080),
        (27.9540, -110.8200),
        (27.9560, -110.8400),
        (27.9560, -110.8400),
        (27.9560, -110.8400),
        (27.9560, -110.8400),
        (27.9560, -110.8400),
        (27.9580, -110.8600),
        (27.9600, -110.8800),
        (27.9630, -110.8950),
        (27.9650, -110.9050),
        (27.9675, -110.9185),
    ]

    i = 0

    while True:
        lat, lng = ruta[i % len(ruta)]
        data = {
            'lat': lat,
            'lng': lng,
            'bus_id': 'ABC-123',
            'id_unidad': 1,
            'velocidad': random.randint(40, 80),
            'timestamp': time.strftime('%H:%M:%S')
        }
        socketio.emit('gps_live', data)

        ID_UNIDAD_SIM = 1
        Location.save(id_unidad=ID_UNIDAD_SIM, lat=lat, lng=lng)

        publish_gps_kafka(lat, lng, bus_id="ABC-123", id_unidad=ID_UNIDAD_SIM)
        analizar_coordenada(lat, lng, id_unidad=ID_UNIDAD_SIM)

        i += 1
        time.sleep(5)


if MODO_SIMULACION:
    threading.Thread(target=gps_simulador_simple, daemon=True).start()

start_kafka_consumer()
start_messaging_consumers()


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5500, use_reloader=False)