from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
import jwt

# esta se importa solo para simulación
import random

import logging
import threading
import time
from entities.location import Location
from entities.bus import Bus
from entities.user import User
from tokenManager import create_token, token_required
import os
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.DEBUG)  

app = Flask(__name__)
CORS(app)

"""Ruta de prueba para verificar que la conexión está 'sana'
Devuelve un JSON con el estado del servicio."""
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "potrobus-backend"})


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    usuario = User.verify_login(data['correo'], data['password'])
    
    if usuario:
        token = create_token(usuario)
        
        return {"message": "Login exitoso",
                 "access_token": token,
                 "user": usuario
                 }, 200
    
    return {"message": "Credenciales inválidas"}, 401


#para pruebas de autenticación con token (usen postman)
@app.route('/api/test-auth', methods=['GET'])
@token_required
def test_auth(current_user):
    return jsonify({
        "message": "Acceso autorizado",
        "datos_usuario": current_user
    }), 200

"""Rutas para gestionar autobuses"""
@app.route("/api/buses", methods=["GET"])
def list_buses():
    # TODO: devolver lista de autobuses
    data = Bus.get_all()
    return jsonify(data)

@app.route("/api/buses", methods=["POST"])
def create_bus():
    # TODO: crear autobús
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


"""Rutas para gestionar rutas y posiciones GPS de los autobuses"""
@app.route("/api/buses/<int:id_unidad>/positions", methods=["GET"])
def get_bus_positions(id_unidad):
    # TODO: historial de posiciones
    data = Location.get_history(id_unidad)

    if data:
        return jsonify(data)
    else: 
        return jsonify({"msg": "sin datos"}), 404
    

@app.route("/api/buses/<int:id_unidad>/positions/latest", methods=["GET"])
def get_latest_position(id_unidad):
    data = Location.get_latest(id_unidad)

    if data:
        return jsonify(data)
    else:
        return jsonify({"error": "sin_posicion"}), 404


@app.route("/api/buses/<int:id_unidad>/recorrido-activo", methods=["GET"])
def get_recorrido_activo(id_unidad):
    data = Location.get_active_recorrido(id_unidad)
 
    if data:
        return jsonify(data)
    else:
        return jsonify({"error": "sin_recorrido_activo"}), 404


@app.route("/api/gps/position", methods=["POST"])
def ingest_position():
    # TODO: recibir lat/lng del bus
    data = request.json
    print("DATA RECIBIDA:", data) #debug
    if not data or data.get("id_recorrido") is None or data.get("lat") is None or data.get("lng") is None:
        return jsonify({"error": "no data"}), 400
    
    Location.save(data.get("id_recorrido"), data.get("lat"), data.get("lng"))
    return jsonify({"msg": "posición guardada"}), 201

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)


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
    except Exception as e:
        print(f"Conexión rechazada: {e}")


@socketio.on('test')
def handle_test(data):
    print(f'Frontend test: {data}')


def gps_simulador_simple():
    print("THREAD GPS SIMPLE INICIADO!")
    while True:
        lat = 27.9269 + random.uniform(-0.01, 0.01)
        lng = -110.8946 + random.uniform(-0.01, 0.01)
        data = {
            'lat': lat, 'lng': lng, 'bus_id': 'ABC-123',
            'velocidad': random.randint(20, 60),
            'timestamp': time.strftime('%H:%M:%S')
        }
        print(f"LIVE GPS: {lat:.4f}, {lng:.4f} km/h:{data['velocidad']} {data['timestamp']}")
        socketio.emit('gps_live', data)
        print("¡Se emitió la señal gps_live!")

        Location.save(id_recorrido=2, lat=lat, lng=lng) 
        print("Ubicación guardada en la base de datos")
        
        time.sleep(5)

threading.Thread(target=gps_simulador_simple, daemon=True).start()
print("THREAD GPS ACTIVO!")


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5500, use_reloader=False)