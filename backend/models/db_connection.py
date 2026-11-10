import os
import sys
from pymongo import MongoClient

# Asegurar importación de config independientemente del punto de entrada
try:
    from config import MONGO_URI, DB_NAME
except ImportError:
    from backend.config import MONGO_URI, DB_NAME

_client = None
_db = None

def get_client() -> MongoClient:
    """Retorna la instancia global del cliente MongoClient."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client

def get_db():
    """Retorna la base de datos de MongoDB configurada en DB_NAME."""
    global _db
    if _db is None:
        client = get_client()
        _db = client[DB_NAME]
    return _db

# Nombres de las colecciones oficiales del sistema
COLLECTIONS = {
    "lecturas": "lecturas",
    "bitacoras": "bitacoras",
    "predicciones": "predicciones",
    "clasificaciones": "clasificaciones",
    "cargas": "cargas",
    "eventos_seguridad": "eventos_seguridad",
}

def get_collection(name: str):
    """Obtiene una colección por su nombre."""
    db = get_db()
    return db[name]

# Funciones de conveniencia para acceder a cada colección
def get_lecturas_col():
    return get_collection(COLLECTIONS["lecturas"])

def get_bitacoras_col():
    return get_collection(COLLECTIONS["bitacoras"])

def get_predicciones_col():
    return get_collection(COLLECTIONS["predicciones"])

def get_clasificaciones_col():
    return get_collection(COLLECTIONS["clasificaciones"])

def get_cargas_col():
    return get_collection(COLLECTIONS["cargas"])

def get_eventos_seguridad_col():
    return get_collection(COLLECTIONS["eventos_seguridad"])
