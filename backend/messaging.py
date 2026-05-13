import pika
import json
import threading
from kafka import KafkaProducer, KafkaConsumer

_socketio = None

# RabbitMQ se usa para NOTIFICACIONES (salidas, retrasos)

def get_rabbitmq_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host='localhost',
            credentials=pika.PlainCredentials('admin', 'admin123')
        )
    )

def publish_notificacion(tipo, mensaje, id_recorrido=None):
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue='notificaciones', durable=True)
        
        data = {
            "tipo": tipo,           
            "mensaje": mensaje,     
            "id_recorrido": id_recorrido
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='notificaciones',
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2)  # mensaje persistente
        )
        #print(f"NOTIFICACION ENVIADA: {tipo} - {mensaje}")
        connection.close()
        return True
    except Exception as ex:
        print(f"ERROR RabbitMQ: {ex}")
        return False


def set_socketio(sio):
    global _socketio
    _socketio = sio

def consume_notificaciones():
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue='notificaciones', durable=True)

        def callback(ch, method, properties, body):
            data = json.loads(body)
            print(f"NOTIFICACION RECIBIDA: {data['tipo']} - {data['mensaje']}")
            # Emitir al panel web via Socket.io
            if _socketio:
                _socketio.emit('notificacion', data)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='notificaciones', on_message_callback=callback)
        print("Esperando notificaciones RabbitMQ...")
        channel.start_consuming()
    except Exception as ex:
        print(f"ERROR consumidor RabbitMQ: {ex}")


# Kafka se usa para el STREAM de coordenadas GPS

def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        api_version=(2, 5, 0)
    )

def publish_gps_kafka(lat, lng, bus_id, id_recorrido):
    try:
        producer = get_kafka_producer()
        data = {
            "lat": lat,
            "lng": lng,
            "bus_id": bus_id,
            "id_recorrido": id_recorrido
        }
        producer.send('gps-coordinates', value=data)
        producer.flush()
        #print(f"GPS KAFKA ENVIADO: {lat}, {lng}")
        return True
    except Exception as ex:
        print(f"ERROR Kafka producer: {ex}")
        return False


def start_messaging_consumers():
    threading.Thread(target=consume_notificaciones, daemon=True).start()
    #print("Consumidores de mensajería iniciados")