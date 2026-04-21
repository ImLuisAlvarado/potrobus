from flask import Flask, jsonify, request
from flask_cors import CORS
from entities.location import Location
from entities.bus import Bus

app = Flask(__name__)
CORS(app)

"""Ruta de prueba para verificar que la conexión está 'sana'
Devuelve un JSON con el estado del servicio."""
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "potrobus-backend"})


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

if __name__ == "__main__":
    app.run(debug=True)