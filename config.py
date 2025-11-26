import os
from dotenv import load_dotenv
import pymysql
from sqlalchemy import create_engine
import urllib.parse # <--- 1. IMPORTAR ESTO

# Carga variables del archivo .env si existe
load_dotenv()

class Config:
    # Detectamos el entorno basado en una variable, si no existe asumimos LOCAL
    ENV = os.getenv('APP_ENV', 'local')

    # --- SEGURIDAD DE FLASK (CRÍTICO PARA SESIONES) ---
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', '')
    
    # Configuración de Cookies de Sesión (OWASP)
    SESSION_COOKIE_HTTPONLY = True  # Previene acceso a cookies vía JavaScript (XSS)
    SESSION_COOKIE_SAMESITE = 'Lax' # Previene CSRF en la mayoría de los casos
    # En producción con HTTPS, esto debe ser True
    SESSION_COOKIE_SECURE = ENV == 'production' 
    PERMANENT_SESSION_LIFETIME = 900 # 15 minutos de sesión 
    
    DB_HOST = os.getenv('MYSQL_HOST')
    DB_USER = os.getenv('MYSQL_USER')
    DB_PASS = os.getenv('MYSQL_PASSWORD')
    DB_NAME = os.getenv('MYSQL_DB')
    
    # --- 2. CODIFICAR LA CONTRASEÑA PARA LA URL ---
    # Esto convierte 'camet%2025' en 'camet%252025' para que SQLAlchemy entienda el literal
    encoded_password = urllib.parse.quote_plus(DB_PASS) if DB_PASS else ""

    # Cadena de conexión segura
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}/{DB_NAME}"

    # Configuración específica de las líneas
    LINES_CONFIG = {
        'linea_1': {'table': 'linea_1', 'entry_area': 12, 'exit_area': 11, 'label': 'Línea 1'},
        'linea_2': {'table': 'linea_2', 'entry_area': 23, 'exit_area': 24, 'label': 'Línea 2'},
        'linea_3': {'table': 'linea_3_semolin', 'entry_area': 1, 'exit_area': 2, 'label': 'Línea 3 Semolín'} 
    }

    # --- BASE DE DATOS DE AUTENTICACIÓN (USUARIOS) ---
    AUTH_DB_CONFIG = {
        'host': os.getenv('AUTH_MYSQL_HOST'),
        'port': int(os.getenv('AUTH_MYSQL_PORT', 3306)),
        'user': os.getenv('AUTH_MYSQL_USER'),
        'password': os.getenv('AUTH_MYSQL_PASSWORD'),
        'database': os.getenv('AUTH_MYSQL_DB')
    }


def get_db_connection():
    try:
        return pymysql.connect(
            host=Config.DB_HOST, user=Config.DB_USER, password=Config.DB_PASS, # Aquí usamos la pass original, pymysql no necesita encoding
            database=Config.DB_NAME, cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        print(f"Error raw connection: {e}")
        return None
    
def get_db_engine():
    try:
        # pool_recycle evita que la conexión se cierre por inactividad en Cpanel
        return create_engine(Config.SQLALCHEMY_DATABASE_URI, pool_recycle=280)
    except Exception as e:
        print(f"Error creando engine: {e}")
        return None