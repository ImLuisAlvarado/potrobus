from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room
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
from datetime import datetime, timezone, timedelta

load_dotenv()
logging.basicConfig(level=logging.WARNING)

# Silenciar librerias verbosas manteniendo solo logs de la app
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

MODO_SIMULACION = False # Cambiar a False para producción con GPS real


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
@token_required
def list_buses(current_user):
    data = Bus.get_all()
    return jsonify(data)



@app.route("/api/buses/activos", methods=["GET"])
@token_required
def list_buses_activos(current_user):

    data = Bus.get_all()

    activos = [
        bus for bus in data
        if int(bus.get("activo", 0)) == 1
    ]

    buses_en_servicio = []

    for bus in activos:

        ultima = Location.get_latest(bus["id_unidad"])

        if not ultima:
            continue

        timestamp = ultima.get("timestamp")

        if not timestamp:
            continue

        try:

            # timestamp desde MySQL
            if isinstance(timestamp, datetime):
                ts = timestamp
            else:
                ts = datetime.fromisoformat(str(timestamp))

            # IMPORTANTE:
            # usar misma zona horaria local
            ahora = datetime.now()

            diferencia = abs((ahora - ts).total_seconds())

            print("\n===================")
            print("BUS:", bus["id_unidad"])
            print("AHORA:", ahora)
            print("TIMESTAMP:", ts)
            print("SEGUNDOS DIF:", diferencia)

            # 5 minutos = 300 segundos
            if diferencia < 300:
                print("AGREGADO")
                buses_en_servicio.append(bus)
            else:
                print("NO AGREGADO")

        except Exception as e:
            print("ERROR:", e)

    print("FINAL:", buses_en_servicio)

    return jsonify(buses_en_servicio)



@app.route("/api/buses", methods=["POST"])
@token_required
def create_bus(current_user):
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
@token_required
def update_bus(current_user, id_unidad):
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
@token_required
def toggle_bus_status(current_user, id_unidad):
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
@token_required
def delete_bus(current_user, id_unidad):
    ok = Bus.delete(id_unidad)
    if ok:
        return jsonify({"msg": "unidad desactivada"})
    return jsonify({"error": "no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>", methods=["GET"])
@token_required
def get_bus(current_user, id_unidad):
    data = Bus.get_by_id(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"error": "unidad no encontrada"}), 404


@app.route("/api/buses/<int:id_unidad>/estado", methods=["GET"])
@token_required
def get_estado_bus(current_user, id_unidad):
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
@token_required
def get_bus_positions(current_user, id_unidad):
    data = Location.get_history(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"msg": "sin datos"}), 404


@app.route("/api/buses/<int:id_unidad>/positions/latest", methods=["GET"])
@token_required
def get_latest_position(current_user, id_unidad):
    data = Location.get_latest(id_unidad)
    if data:
        return jsonify(data)
    return jsonify({"error": "sin_posicion"}), 404


@app.route("/api/buses/<int:id_unidad>/ruta", methods=["GET"])
def get_ruta_by_unidad(id_unidad):
    ruta = Route.get_by_unidad(id_unidad)
    if not ruta:
        return jsonify({"error": "sin ruta asignada para esta unidad"}), 404
    paradas = Route.get_paradas(ruta["id_ruta"])
    return jsonify({**ruta, "paradas": paradas})

@app.route("/api/gps/position", methods=["POST"])
@token_required
def ingest_position(current_user):
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

    socketio.emit('gps_live', {
        "lat":       lat,
        "lng":       lng,
        "id_unidad": id_unidad,
        "bus_id":    bus_id,
        "timestamp": timestamp
    }, room=f"unidad_{id_unidad}")

    publish_gps_kafka(lat, lng, bus_id=bus_id, id_unidad=id_unidad)
    return jsonify({"msg": "posición guardada"}), 201


@app.route("/api/rutas", methods=["GET"])
@token_required
def list_rutas(current_user):
    data = Route.get_all()
    return jsonify(data)

@app.route("/api/rutas/<int:id_ruta>", methods=["GET"])
@token_required
def get_ruta(current_user, id_ruta):
    data = Route.get_by_id(id_ruta)
    if data:
        return jsonify(data)
    return jsonify({"error": "ruta no encontrada"}), 404

@app.route("/api/rutas", methods=["POST"])
@token_required
def create_ruta(current_user):
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
@token_required
def update_ruta(current_user, id_ruta):
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
@token_required
def delete_ruta(current_user, id_ruta):
    ok = Route.delete(id_ruta)
    if ok:
        return jsonify({"msg": "ruta eliminada"})
    return jsonify({"error": "no encontrada"}), 404

@app.route("/api/buses/<int:id_unidad>/paradas-pendientes", methods=["GET"])
def get_paradas_pendientes(id_unidad):
    """
    Devuelve las paradas de la ruta con estado visitado/pendiente
    para una unidad especifica, basado en el estado del kafka_consumer.
    """
    paradas = Route.get_paradas(1)  # Ruta ITSON — ampliar cuando haya multiples rutas
    visitadas = get_paradas_visitadas(id_unidad)

    for p in paradas:
        p["visitada"] = p["id_parada"] in visitadas

    return jsonify(paradas)


@app.route("/api/rutas/<int:id_ruta>/paradas", methods=["GET"])
@token_required
def get_paradas(current_user, id_ruta):
    data = Route.get_paradas(id_ruta)
    return jsonify(data)

@app.route("/api/rutas/<int:id_ruta>/paradas", methods=["POST"])
@token_required
def add_parada(current_user, id_ruta):
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
@token_required
def list_choferes(current_user):
    data = Driver.get_all()
    return jsonify(data)

@app.route("/api/choferes/<int:id_chofer>", methods=["GET"])
@token_required
def get_chofer(current_user, id_chofer):
    data = Driver.get_by_id(id_chofer)
    if data:
        return jsonify(data)
    return jsonify({"error": "chofer no encontrado"}), 404

@app.route("/api/choferes", methods=["POST"])
@token_required
def create_chofer(current_user):
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
@token_required
def update_chofer(current_user, id_chofer):
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
@token_required
def toggle_chofer_status(current_user, id_chofer):
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
@token_required
def delete_chofer(current_user, id_chofer):
    ok = Driver.delete(id_chofer)
    if ok:
        return jsonify({"msg": "chofer desactivado"})
    return jsonify({"error": "no encontrado"}), 404


@app.route("/api/notificaciones", methods=["POST"])
@token_required
def send_notificacion(current_user):
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
        if id_unidad := request.args.get('id_unidad'):
            join_room(f"unidad_{id_unidad}")
            print(f"Cliente unido al room unidad_{id_unidad}")
        return True
    except Exception as e:
        print(f"Conexión rechazada: {e}")
        return False
    

@socketio.on('watch_unidad')
def handle_watch(data):
    if id_unidad := data.get('id_unidad'):
        join_room(f"unidad_{id_unidad}")

@socketio.on('unwatch_unidad')
def handle_unwatch(data):
    if id_unidad := data.get('id_unidad'):
        leave_room(f"unidad_{id_unidad}")


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
        socketio.emit('gps_live', data, room=f"unidad_{data['id_unidad']}")
        print("¡Se emitió la señal gps_live!")

        ID_UNIDAD_SIM = 1  # unidad simulada
        Location.save(id_unidad=ID_UNIDAD_SIM, lat=lat, lng=lng)
        print("Ubicación guardada en la base de datos")

        publish_gps_kafka(lat, lng, bus_id="ABC-123", id_unidad=ID_UNIDAD_SIM)
        analizar_coordenada(lat, lng, id_unidad=ID_UNIDAD_SIM)

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