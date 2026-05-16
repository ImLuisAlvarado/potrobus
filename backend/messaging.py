import pika
import json
import threading
from kafka import KafkaProducer

_socketio = None
_kafka_producer = None
_kafka_producer_lock = threading.Lock()


def get_rabbitmq_connection():
    """
    Establece y devuelve una conexión síncrona con el servidor de RabbitMQ.

    Returns:
        pika.BlockingConnection: Objeto de conexión configurado con las 
        credenciales y parámetros del servidor.
    """
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
    Publica un mensaje de notificación estructurado en la cola de RabbitMQ.

    Args:
        tipo (str): Categoría de la notificación ('salida', 'llegada', 'parada', 'retraso').
        mensaje (str): Contenido textual del aviso.
        id_unidad (int/str, optional): Identificador único del vehículo asociado. Defaults to None.

    Returns:
        bool: True si el mensaje se publicó correctamente, False en caso de error.
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
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        print(f"NOTIFICACION → RabbitMQ: [{tipo}] {mensaje}")
        return True
    except Exception as ex:
        print(f"ERROR RabbitMQ publish: {ex}")
        return False


def set_socketio(sio):
    """
    Asigna de forma global la instancia de Socket.IO para la retransmisión de eventos.

    Args:
        sio: Instancia del servidor o cliente Socket.IO activa.
    """
    global _socketio
    _socketio = sio


def consume_notificaciones():
    """
    Escucha de forma continua la cola de RabbitMQ, procesa las notificaciones entrantes
    y las redirige en tiempo real a través de Socket.IO.
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


def get_kafka_producer():
    """
    Garantiza la creación segura (Thread-Safe) y el retorno de una única instancia 
    del productor de Kafka (Patrón Singleton).

    Returns:
        KafkaProducer: Instancia del productor de Kafka, o None si falla la inicialización.
    """
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
    """
    Envía un paquete de coordenadas geográficas en tiempo real al topic de Kafka correspondiente.

    Args:
        lat (float): Latitud geográfica.
        lng (float): Longitud geográfica.
        bus_id (str/int): Identificador lógico de la ruta o autobús.
        id_unidad (str/int): Identificador de la unidad física del vehículo.

    Returns:
        bool: True si los datos de geolocalización fueron enviados con éxito, False en caso contrario.
    """
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
    """
    Inicializa los procesos de escucha de mensajería asíncrona.
    
    Lanza el consumidor de RabbitMQ en un hilo secundario (daemon) para no bloquear 
    la ejecución del hilo principal de la aplicación.
    """
    threading.Thread(target=consume_notificaciones, daemon=True).start()
    print("Consumidor RabbitMQ iniciado.")