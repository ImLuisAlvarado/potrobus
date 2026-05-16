import jwt
import datetime
from functools import wraps
from flask import request, jsonify

import os
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("¡Error! La variable de entorno SECRET_KEY no está definida ;)")

"""Método para crear tokens cada que un usuario inicia sesión."""
def create_token(user_data):
    payload = {
        'user_id': user_data['id_usuario'],
        'correo': user_data['correo'],
        'rol': user_data['rol'],
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

"""Método que funciona como 'decorador' (yo tampoco entendía lo que era pero es útil) así
    blindamos más facilmente las rutas"""
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token or not token.startswith("Bearer "):
            return jsonify({'message': 'Token faltante'}), 401
            
        try:
            token_clean = token.split(" ")[1]
            data = jwt.decode(token_clean, SECRET_KEY, algorithms=["HS256"])
            current_user = data
        except Exception:
            return jsonify({'message': 'Token inválido'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated