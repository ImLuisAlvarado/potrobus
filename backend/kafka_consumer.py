import json
import threading
import time
from math import radians, sin, cos, sqrt, atan2
from kafka import KafkaConsumer
from messaging import publish_notificacion
from persistence.db import get_connection

# ----------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------

RADIO_PARADA_METROS  = 150   # distancia para considerar que el bus llegó a una parada
RADIO_RETRASO_METROS = 20    # distancia minima de movimiento para no considerarse detenido
TIEMPO_RETRASO_SEG   = 300   # segundos detenido antes de notificar retraso (5 min)

# ----------------------------------------------------------------
# Estado por unidad — soporta multiples buses simultaneamente
# ----------------------------------------------------------------

def get_paradas_visitadas(id_unidad):
    """Devuelve el set de id_parada ya visitadas por una unidad."""
    with _estado_lock:
        return set(_estado_buses.get(id_unidad, {}).get("paradas_visitadas", set()))

# { id_unidad: { ultima_lat, ultima_lng, ultimo_movimiento, paradas_visitadas } }
_estado_buses = {}
_estado_lock  = threading.Lock()

def _get_estado(id_unidad):
    """Obtiene o inicializa el estado de una unidad."""
    with _estado_lock:
        if id_unidad not in _estado_buses:
            _estado_buses[id_unidad] = {
                "ultima_lat":        None,
                "ultima_lng":        None,
                "ultimo_movimiento": None,
                "paradas_visitadas": set()   # ids de paradas ya notificadas
            }
        return _estado_buses[id_unidad]

# ----------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------

def distancia_metros(lat1, lng1, lat2, lng2):
    """Calcula distancia aproximada en metros entre dos coordenadas (Haversine)."""
    R = 6371000
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def cargar_paradas_ruta(id_unidad):
    """
    Carga las paradas de la ruta asignada a la unidad desde BD.
    Devuelve lista de dicts ordenada por orden_parada.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Busca la ruta a través de la unidad
        # De momento todas las unidades comparten la Ruta ITSON (id_ruta=1)
        # Cuando haya asignacion de ruta por unidad se puede ampliar esta query
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

# ----------------------------------------------------------------
# Logica de analisis GPS
# ----------------------------------------------------------------

def analizar_coordenada(lat, lng, id_unidad=1):
    """
    Analiza cada coordenada GPS recibida para una unidad especifica y
    dispara notificaciones via RabbitMQ cuando corresponde:
      - Llegada a una parada
      - Bus detenido mas de TIEMPO_RETRASO_SEG segundos
    """
    ahora  = time.time()
    estado = _get_estado(id_unidad)
    paradas = cargar_paradas_ruta(id_unidad)

    # 1. Detectar si el bus está detenido
    if estado["ultima_lat"] is not None:
        dist_movida = distancia_metros(
            lat, lng,
            estado["ultima_lat"], estado["ultima_lng"]
        )

        if dist_movida < RADIO_RETRASO_METROS:
            # No se movio — verificar cuánto tiempo lleva parado
            if estado["ultimo_movimiento"] is not None:
                parado_seg = ahora - estado["ultimo_movimiento"]
                if parado_seg >= TIEMPO_RETRASO_SEG:
                    minutos = int(parado_seg / 60)
                    publish_notificacion(
                        tipo="retraso",
                        mensaje=f"El bus lleva {minutos} minuto{'s' if minutos != 1 else ''} detenido",
                        id_unidad=id_unidad
                    )
                    # Reiniciar timer para no spamear la notificacion
                    estado["ultimo_movimiento"] = ahora
        else:
            # Se movio — actualizar timestamp de ultimo movimiento
            estado["ultimo_movimiento"] = ahora
    else:
        # Primera coordenada recibida de esta unidad
        estado["ultimo_movimiento"] = ahora

    # 2. Detectar llegada a paradas
    for parada in paradas:
        id_parada = parada["id_parada"]

        # Saltar paradas ya notificadas en este recorrido
        if id_parada in estado["paradas_visitadas"]:
            continue

        dist = distancia_metros(
            lat, lng,
            float(parada["latitud"]), float(parada["longitud"])
        )

        if dist <= RADIO_PARADA_METROS:
            es_primera = len(estado["paradas_visitadas"]) == 0
            es_ultima  = parada["orden_parada"] == max(p["orden_parada"] for p in paradas)

            if es_primera:
                tipo    = "salida"
                mensaje = f"El bus salió de {parada['nombre']}"
            elif es_ultima:
                tipo    = "llegada"
                mensaje = f"El bus llegó a {parada['nombre']}"
                # Resetear para el proximo recorrido
                estado["paradas_visitadas"] = set()
                estado["ultimo_movimiento"] = None
            else:
                tipo    = "parada"
                mensaje = f"El bus está llegando a {parada['nombre']}"

            publish_notificacion(tipo=tipo, mensaje=mensaje, id_unidad=id_unidad)
            estado["paradas_visitadas"].add(id_parada)
            print(f"PARADA DETECTADA: unidad={id_unidad} → {parada['nombre']} ({dist:.0f}m)")
            break  # una sola notificacion por coordenada

    # 3. Actualizar ultima posicion conocida
    estado["ultima_lat"] = lat
    estado["ultima_lng"] = lng

# ----------------------------------------------------------------
# Consumidor Kafka
# ----------------------------------------------------------------

def start_kafka_consumer():
    """
    Inicia el consumidor Kafka en un hilo daemon.
    Lee el topic 'gps-coordinates' y llama a analizar_coordenada
    por cada mensaje recibido.
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
                    auto_offset_reset='latest',   # solo coordenadas nuevas
                    group_id='potrobus-gps-consumer',
                    api_version=(2, 5, 0)
                )
                intentos = 0
                print("Consumidor Kafka listo, esperando coordenadas GPS...")

                for message in consumer:
                    data = message.value
                    lat       = data.get("lat")
                    lng       = data.get("lng")
                    id_unidad = data.get("id_unidad", 1)

                    if lat is not None and lng is not None:
                        analizar_coordenada(lat, lng, id_unidad=id_unidad)

            except Exception as ex:
                intentos += 1
                espera = min(30, 5 * intentos)  # backoff: 5s, 10s, 15s... max 30s
                print(f"ERROR consumidor Kafka (intento {intentos}): {ex}")
                print(f"Reintentando en {espera}s...")
                time.sleep(espera)

    threading.Thread(target=run, daemon=True).start()