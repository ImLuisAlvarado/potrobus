import pika
import json
import threading
from kafka import KafkaProducer

_socketio = None
_kafka_producer = None
_kafka_producer_lock = threading.Lock()

# ----------------------------------------------------------------
# RabbitMQ — Notificaciones (salidas, llegadas, retrasos)
# ----------------------------------------------------------------

def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host='localhost',
            port=5672,
            credentials=pika.PlainCredentials('admin', 'admin123'),
            heartbeat=60,
            blocked_connection_timeout=30
        )
    )

def publish_notificacion(tipo, mensaje, id_unidad=None):
    """
    Publica una notificacion en RabbitMQ.
    tipo: 'salida' | 'llegada' | 'parada' | 'retraso'
    """
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue='notificaciones', durable=True)

        data = {
            "tipo":      tipo,
            "mensaje":   mensaje,
            "id_unidad": id_unidad
        }

        channel.basic_publish(
            exchange='',
            routing_key='notificaciones',
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2)  # persistente
        )
        connection.close()
        print(f"NOTIFICACION → RabbitMQ: [{tipo}] {mensaje}")
        return True
    except Exception as ex:
        print(f"ERROR RabbitMQ publish: {ex}")
        return False


def set_socketio(sio):
    global _socketio
    _socketio = sio


def consume_notificaciones():
    """
    Consumidor RabbitMQ: lee la queue 'notificaciones' y las
    emite al dashboard y app de estudiantes via Socket.IO.
    """
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue='notificaciones', durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                print(f"NOTIFICACION ← RabbitMQ: [{data.get('tipo')}] {data.get('mensaje')}")
                if _socketio:
                    _socketio.emit('notificacion', data)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as ex:
                print(f"ERROR procesando notificacion: {ex}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_consume(queue='notificaciones', on_message_callback=callback)
        print("Consumidor RabbitMQ listo, esperando notificaciones...")
        channel.start_consuming()
    except Exception as ex:
        print(f"ERROR consumidor RabbitMQ: {ex}")


# ----------------------------------------------------------------
# Kafka — Stream de coordenadas GPS
# ----------------------------------------------------------------

def get_kafka_producer():
    """Singleton: crea el producer una sola vez y lo reutiliza."""
    global _kafka_producer
    with _kafka_producer_lock:
        if _kafka_producer is None:
            try:
                _kafka_producer = KafkaProducer(
                    bootstrap_servers='localhost:9092',
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    api_version=(2, 5, 0),
                    retries=3
                )
                print("Kafka producer inicializado.")
            except Exception as ex:
                print(f"ERROR inicializando Kafka producer: {ex}")
        return _kafka_producer


def publish_gps_kafka(lat, lng, bus_id, id_unidad):
    """Publica coordenadas GPS en el topic gps-coordinates de Kafka."""
    try:
        producer = get_kafka_producer()
        if producer is None:
            return False
        data = {
            "lat":       lat,
            "lng":       lng,
            "bus_id":    bus_id,
            "id_unidad": id_unidad
        }
        producer.send('gps-coordinates', value=data)
        producer.flush()
        return True
    except Exception as ex:
        print(f"ERROR Kafka producer send: {ex}")
        return False


def start_messaging_consumers():
    """Inicia el consumidor RabbitMQ en un hilo daemon."""
    threading.Thread(target=consume_notificaciones, daemon=True).start()
    print("Consumidor RabbitMQ iniciado.")