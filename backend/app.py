from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from messaging import publish_notificacion, publish_gps_kafka, start_messaging_consumers, set_socketio
from kafka_consumer import start_kafka_consumer, analizar_coordenada
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
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
set_socketio(socketio)

MODO_SIMULACION = False


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "potrobus-backend"})


@app.route('/login', methods=['POST'])
def login():
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
    return jsonify({
        "message": "Acceso autorizado",
        "datos_usuario": current_user
    }), 200

@app.route("/api/buses", methods=["GET"])
def list_buses():
    data = Bus.get_all()
    return jsonify(data)

@app.route("/api/buses/activos", methods=["GET"])
def list_buses_activos():
    data = Bus.get_all()
    activos = [bus for bus in data if bus.get("activo")]
    return jsonify(activos)


@app.route("/api/buses", methods=["POST"])
def create_bus():
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
    ok = Bus.delete(id_unidad)
    if ok:
        return jsonify({"msg": "unidad desactivada"})
    return jsonify({"error": "no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>", methods=["GET"])
def get_bus(id_unidad):
    data = Bus.get_by_id(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"error": "unidad no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>/estado", methods=["GET"])
def get_estado_bus(id_unidad):
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
    data = Location.get_history(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"msg": "sin datos"}), 404


@app.route("/api/buses/<int:id_unidad>/positions/latest", methods=["GET"])
def get_latest_position(id_unidad):
    data = Location.get_latest(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"error": "sin_posicion"}), 404


# Endpoint /recorrido-activo eliminado - arquitectura simplificada sin tabla recorrido


@app.route("/api/gps/position", methods=["POST"])
def ingest_position():
    data = request.json
    print("GPS RECIBIDO:", data)
    if not data or data.get("id_unidad") is None or data.get("lat") is None or data.get("lng") is None:
        return jsonify({"error": "Faltan campos: id_unidad, lat, lng"}), 400

    id_unidad = data.get("id_unidad")
    lat       = data.get("lat")
    lng       = data.get("lng")
    bus_id    = data.get("bus_id", f"unidad-{id_unidad}")
    timestamp = data.get("timestamp", "")

    Location.save(id_unidad, lat, lng)

    publish_gps_kafka(lat, lng, bus_id=bus_id, id_recorrido=None)

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
    data = Route.get_all()
    return jsonify(data)

@app.route("/api/rutas/<int:id_ruta>", methods=["GET"])
def get_ruta(id_ruta):
    data = Route.get_by_id(id_ruta)
    if data:
        return jsonify(data)
    return jsonify({"error": "ruta no encontrada"}), 404

@app.route("/api/rutas", methods=["POST"])
def create_ruta():
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
    ok = Route.delete(id_ruta)
    if ok:
        return jsonify({"msg": "ruta eliminada"})
    return jsonify({"error": "no encontrada"}), 404

@app.route("/api/rutas/<int:id_ruta>/paradas", methods=["GET"])
def get_paradas(id_ruta):
    data = Route.get_paradas(id_ruta)
    return jsonify(data)

@app.route("/api/rutas/<int:id_ruta>/paradas", methods=["POST"])
def add_parada(id_ruta):
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
    data = request.json
    if not data or not data.get("correo") or not data.get("password"):
        return jsonify({"error": "Faltan correo o password"}), 400

    chofer = Driver.verify_login(data["correo"], data["password"])
    if not chofer:
        return jsonify({"error": "Credenciales inválidas o chofer inactivo"}), 401

    if not chofer.get("id_unidad"):
        return jsonify({"error": "El chofer no tiene unidad asignada"}), 403

    # create_token espera id_usuario, correo, rol — adaptamos chofer a ese formato
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
    data = Driver.get_all()
    return jsonify(data)

@app.route("/api/choferes/<int:id_chofer>", methods=["GET"])
def get_chofer(id_chofer):
    data = Driver.get_by_id(id_chofer)
    if data:
        return jsonify(data)
    return jsonify({"error": "chofer no encontrado"}), 404

@app.route("/api/choferes", methods=["POST"])
def create_chofer():
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
        data.get("password")   # None = no cambiar password
    )
    if ok:
        return jsonify({"msg": "chofer actualizado"})
    return jsonify({"error": "no encontrado o sin cambios"}), 404

@app.route("/api/choferes/<int:id_chofer>/status", methods=["PATCH"])
def toggle_chofer_status(id_chofer):
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
    ok = Driver.delete(id_chofer)
    if ok:
        return jsonify({"msg": "chofer desactivado"})
    return jsonify({"error": "no encontrado"}), 404


@app.route("/api/notificaciones", methods=["POST"])
def send_notificacion():
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
    try:
        token = request.args.get('token')

        if not token:
            print("Conexión rechazada: No se tiene acceso")
            return False

        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            print(f"Cliente conectado con identidad: {payload.get('sub')}")

        except jwt.ExpiredSignatureError:
            print("Token expirado")
            return False

        except jwt.InvalidTokenError:
            print("Token inválido")
            return False

        print('Cliente WebSocket conectado!')
        return True
    except Exception as e:
        print(f"Conexión rechazada: {e}")
        return False


@socketio.on('test')
def handle_test(data):
    print(f'Frontend test: {data}')


def gps_simulador_simple():
    print("THREAD GPS SIMPLE INICIADO!")

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
        print(f"LIVE GPS: {lat:.4f}, {lng:.4f} km/h:{data['velocidad']} {data['timestamp']}")
        socketio.emit('gps_live', data)
        print("¡Se emitió la señal gps_live!")

        Location.save(id_recorrido=1, lat=lat, lng=lng)
        print("Ubicación guardada en la base de datos")

        publish_gps_kafka(lat, lng, bus_id="ABC-123", id_recorrido=1)
        analizar_coordenada(lat, lng)

        i += 1
        time.sleep(5)


if MODO_SIMULACION:
    threading.Thread(target=gps_simulador_simple, daemon=True).start()
    print("THREAD GPS ACTIVO — MODO SIMULACIÓN")
else:
    print("MODO PRODUCCIÓN — esperando GPS real del conductor")

start_kafka_consumer()
start_messaging_consumers()


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5500, use_reloader=False)