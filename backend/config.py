import os
from pathlib import Path
from dotenv import load_dotenv

# Apuntar a la raíz del proyecto (sube 2 niveles desde backend/config.py)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Cargar el archivo .env si existe en la raíz
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Lectura de la cadena de conexión a MongoDB
MONGO_URI = os.getenv("MONGO_URI")

# Lee DB_NAME o usa MONGO_DB_NAME como respaldo (así funciona con tu .env actual)
DB_NAME = os.getenv("DB_NAME") or os.getenv("MONGO_DB_NAME")

# Validaciones de seguridad
if not MONGO_URI:
    raise ValueError("La variable de entorno 'MONGO_URI' no está configurada en el archivo .env")

if not DB_NAME:
    raise ValueError("No se encontró 'DB_NAME' ni 'MONGO_DB_NAME' configurada en el archivo .env")

# Configuración del servidor Flask
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t", "yes")