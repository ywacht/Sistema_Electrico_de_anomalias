import os
from pathlib import Path
from dotenv import load_dotenv

# Localizar y cargar el archivo .env desde el directorio de backend o raíz
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Lectura estricta desde variables de entorno - Nunca hardcodeado
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

if not MONGO_URI:
    raise ValueError("La variable de entorno 'MONGO_URI' no está configurada en .env")

if not DB_NAME:
    raise ValueError("La variable de entorno 'DB_NAME' no está configurada en .env")

# Configuración del servidor Flask
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t", "yes")
