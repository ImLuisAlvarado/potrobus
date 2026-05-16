"""
Módulo de procesamiento de telemetría y geofencing.

Analiza las coordenadas GPS provenientes de un topic de Kafka en tiempo real
para calcular retrasos mediante la fórmula de Haversine y alertar sobre
las proximidades a las paradas establecidas en el sistema.
"""

import json
import threading
import time
from math import radians, sin, cos, sqrt, atan2
from kafka import KafkaConsumer
from messaging import publish_notificacion
from persistence.db import get_connection

RADIO_PARADA_METROS = 150
RADIO_RETRASO_METROS = 20
TIEMPO_RETRASO_SEG = 60

_estado_buses = {}
_estado_lock = threading.Lock()

def get_paradas_visitadas(id_unidad):
    """
    Devuelve los identificadores de las paradas ya visitadas por una unidad.

    Args:
        id_unidad (int/str): Identificador único de la unidad de transporte.

    Returns:
        set: Conjunto con los IDs de las paradas visitadas y ya notificadas.
    """
    with _estado_lock:
        return set(_estado_buses.get(id_unidad, {}).get("paradas_visitadas", set()))

def _get_estado(id_unidad):
    """
    Obtiene o inicializa de forma segura el estado en memoria de una unidad.

    Args:
        id_unidad (int/str): Identificador único de la unidad de transporte.

    Returns:
        dict: Estructura con la telemetría y el historial reciente de la unidad.
    """
    with _estado_lock:
        if id_unidad not in _estado_buses:
            _estado_buses[id_unidad] = {
                "ultima_lat": None,
                "ultima_lng": None,
                "ultimo_movimiento": None,
                "paradas_visitadas": set()
            }
        return _estado_buses[id_unidad]

def distancia_metros(lat1, lng1, lat2, lng2):
    """
    Calcula la distancia ortodrómica entre dos puntos en la Tierra.

    Implementa la fórmula de Haversine para determinar los metros de separación.

    Args:
        lat1 (float): Latitud del primer punto.
        lng1 (float): Longitud del primer punto.
        lat2 (float): Latitud del segundo punto.
        lng2 (float): Longitud del segundo punto.

    Returns:
        float: Distancia aproximada en metros.
    """
    R = 6371000
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def cargar_paradas_ruta(id_unidad):
    """
    Carga las paradas de la ruta asignada a la unidad desde la base de datos.

    Args:
        id_unidad (int/str): Identificador único de la unidad.

    Returns:
        list: Lista de diccionarios que representan las paradas en orden ascendente.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.id_parada, p.nombre, p.latitud, p.longitud, p.orden_parada
            FROM parada p
            WHERE p.id_ruta = 1
            ORDER BY p.orden_parada ASC
        """)
        return cursor.fetchall()
    except Exception as ex:
        print(f"ERROR cargando paradas: {ex}")
        return []
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

def analizar_coordenada(lat, lng, id_unidad=1):
    """
    Evalúa la posición actual de una unidad para detectar paradas o retrasos.

    Calcula el desplazamiento con respecto al último registro. Si la unidad
    permanece fija más tiempo del límite, envía una alerta. Adicionalmente,
    verifica proximidad a puntos de interés para registrar llegadas o salidas.

    Args:
        lat (float): Latitud reportada por el dispositivo GPS.
        lng (float): Longitud reportada por el dispositivo GPS.
        id_unidad (int/str, opcional): ID de la unidad. Por defecto es 1.
    """
    ahora = time.time()
    estado = _get_estado(id_unidad)
    paradas = cargar_paradas_ruta(id_unidad)

    if estado["ultima_lat"] is not None:
        dist_movida = distancia_metros(
            lat, lng,
            estado["ultima_lat"], estado["ultima_lng"]
        )

        if dist_movida < RADIO_RETRASO_METROS:
            if estado["ultimo_movimiento"] is not None:
                parado_seg = ahora - estado["ultimo_movimiento"]
                if parado_seg >= TIEMPO_RETRASO_SEG:
                    minutos = int(parado_seg / 60)
                    publish_notificacion(
                        tipo="retraso",
                        mensaje=f"El bus lleva {minutos} minuto{'s' if minutos != 1 else ''} detenido",
                        id_unidad=id_unidad
                    )
                    estado["ultimo_movimiento"] = ahora
        else:
            estado["ultimo_movimiento"] = ahora
    else:
        estado["ultimo_movimiento"] = ahora

    for parada in paradas:
        id_parada = parada["id_parada"]

        if id_parada in estado["paradas_visitadas"]:
            continue

        dist = distancia_metros(
            lat, lng,
            float(parada["latitud"]), float(parada["longitud"])
        )

        if dist <= RADIO_PARADA_METROS:
            es_primera = len(estado["paradas_visitadas"]) == 0
            es_ultima = parada["orden_parada"] == max(p["orden_parada"] for p in paradas)

            if es_primera:
                tipo = "salida"
                mensaje = f"El bus salió de {parada['nombre']}"
            elif es_ultima:
                tipo = "llegada"
                mensaje = f"El bus llegó a {parada['nombre']}"
                estado["paradas_visitadas"] = set()
                estado["ultimo_movimiento"] = None
            else:
                tipo = "parada"
                mensaje = f"El bus está llegando a {parada['nombre']}"

            publish_notificacion(tipo=tipo, mensaje=mensaje, id_unidad=id_unidad)
            estado["paradas_visitadas"].add(id_parada)
            print(f"PARADA DETECTADA: unidad={id_unidad} → {parada['nombre']} ({dist:.0f}m)")
            break

    estado["ultima_lat"] = lat
    estado["ultima_lng"] = lng

def start_kafka_consumer():
    """
    Inicia un hilo secundario encargado de escuchar eventos GPS desde Kafka.

    Mantiene una conexión persistente al cluster de mensajería y redirige
    las cargas útiles recibidas directamente a los motores de análisis. Implementa
    una estrategia de reintento exponencial pasivo en caso de desconexión.
    """
    def run():
        intentos = 0
        while True:
            try:
                print("Iniciando consumidor Kafka...")
                consumer = KafkaConsumer(
                    'gps-coordinates',
                    bootstrap_servers='localhost:9092',
                    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                    auto_offset_reset='latest',
                    group_id='potrobus-gps-consumer',
                    api_version=(2, 5, 0)
                )
                intentos = 0
                print("Consumidor Kafka listo, esperando coordenadas GPS...")

                for message in consumer:
                    data = message.value
                    lat = data.get("lat")
                    lng = data.get("lng")
                    id_unidad = data.get("id_unidad", 1)

                    if lat is not None and lng is not None:
                        analizar_coordenada(lat, lng, id_unidad=id_unidad)

            except Exception as ex:
                intentos += 1
                espera = min(30, 5 * intentos)
                print(f"ERROR consumidor Kafka (intento {intentos}): {ex}")
                print(f"Reintentando en {espera}s...")
                time.sleep(espera)

    threading.Thread(target=run, daemon=True).start()