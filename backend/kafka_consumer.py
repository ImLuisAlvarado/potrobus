import json
import threading
import time
from kafka import KafkaConsumer
from messaging import publish_notificacion

# Coordenadas de referencia
EMPALME_LAT = 27.9530
EMPALME_LNG = -110.8080
ITSON_LAT   = 27.9675
ITSON_LNG   = -110.9185
RADIO_METROS = 300  # distancia para considerar que llegó a un punto

# Estado interno del bus
estado_bus = {
    "ultima_lat": None,
    "ultima_lng": None,
    "ultimo_movimiento": None,
    "salio_empalme": False,
    "llego_itson": False
}

def distancia_metros(lat1, lng1, lat2, lng2):
    """Calcula distancia aproximada en metros entre dos puntos"""
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def analizar_coordenada(lat, lng):
    """Analiza cada coordenada GPS y dispara notificaciones si corresponde"""
    ahora = time.time()

    # 1. ¿Bus parado más de 5 minutos?
    if estado_bus["ultima_lat"] is not None:
        dist = distancia_metros(lat, lng, estado_bus["ultima_lat"], estado_bus["ultima_lng"])
        if dist < 20:  # menos de 20 metros = está parado
            if estado_bus["ultimo_movimiento"]:
                parado_segundos = ahora - estado_bus["ultimo_movimiento"]
                if parado_segundos > 20:  # cambiar a 300 para producción (5 minutos), de momento son 20 segundos para pruebas
                    publish_notificacion(
                        tipo="retraso",
                        mensaje=f"El bus lleva {int(parado_segundos/60)} minutos detenido",
                        id_recorrido=1
                    )
        else:
            estado_bus["ultimo_movimiento"] = ahora
    else:
        estado_bus["ultimo_movimiento"] = ahora

    # 2. ¿Bus salió de Empalme?
    if not estado_bus["salio_empalme"]:
        dist_empalme = distancia_metros(lat, lng, EMPALME_LAT, EMPALME_LNG)
        if dist_empalme < RADIO_METROS:
            estado_bus["salio_empalme"] = True
            publish_notificacion(
                tipo="salida",
                mensaje="El bus salió de Empalme, en camino a ITSON Guaymas",
                id_recorrido=1
            )

    # 3. ¿Bus llegó a ITSON?
    if not estado_bus["llego_itson"]:
        dist_itson = distancia_metros(lat, lng, ITSON_LAT, ITSON_LNG)
        if dist_itson < RADIO_METROS:
            estado_bus["llego_itson"] = True
            publish_notificacion(
                tipo="llegada",
                mensaje="El bus llegó a ITSON Guaymas",
                id_recorrido=1
            )

    # Actualizar última posición conocida
    estado_bus["ultima_lat"] = lat
    estado_bus["ultima_lng"] = lng


    if estado_bus["salio_empalme"] and estado_bus["llego_itson"]:
        print("Ruta completada, reseteando estado para próximo ciclo...")
        estado_bus["salio_empalme"] = False
        estado_bus["llego_itson"] = False
        estado_bus["ultimo_movimiento"] = None

def start_kafka_consumer():
    """Consumidor que lee el topic gps-coordinates y analiza cada punto"""
    def run():
        try:
            print("Iniciando consumidor Kafka...")
            consumer = KafkaConsumer(
                'gps-coordinates',
                bootstrap_servers='localhost:9092',
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                auto_offset_reset='earliest',
                group_id='potrobus-consumer-2',
                api_version=(2, 5, 0)
            )
            print("Consumidor Kafka listo, esperando coordenadas...")
            for message in consumer:
                data = message.value
                #print(f"KAFKA RECIBIÓ: {data}") #debug
                lat = data.get("lat")
                lng = data.get("lng")
                if lat and lng:
                    analizar_coordenada(lat, lng)
        except Exception as ex:
            print(f"ERROR consumidor Kafka: {ex}")

    threading.Thread(target=run, daemon=True).start()