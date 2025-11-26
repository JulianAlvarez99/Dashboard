"""
Sistema de Logging de Seguridad para Dashboard Chacabuco
Registra eventos de autenticación, consultas y eventos de seguridad
Cumple con OWASP Logging and Monitoring Best Practices
"""

import mysql.connector
from datetime import datetime
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configurar logging local para debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración de MySQL para logging
LOGGING_DB_CONFIG = {
    'host': os.getenv('LOG_MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('LOG_MYSQL_PORT', 3306)),
    'user': os.getenv('LOG_MYSQL_USER', 'cametcom'),
    'password': os.getenv('LOG_MYSQL_PASSWORD'),
    'database': os.getenv('LOG_MYSQL_DB', 'cametcom_usuarios'),
    'connect_timeout': 60,
}

# COMENTADO - Tabla security_events no existe aún
# Tipos de eventos de seguridad
# class SecurityEvent:
#     LOGIN_SUCCESS = 'LOGIN_SUCCESS'
#     LOGIN_FAILURE = 'LOGIN_FAILURE'
#     LOGOUT = 'LOGOUT'
#     SESSION_EXPIRED = 'SESSION_EXPIRED'
#     QUERY_EXECUTED = 'QUERY_EXECUTED'
#     UNAUTHORIZED_ACCESS = 'UNAUTHORIZED_ACCESS'
#     RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
#     SUSPICIOUS_ACTIVITY = 'SUSPICIOUS_ACTIVITY'
#     PASSWORD_CHANGE = 'PASSWORD_CHANGE'
#     ACCOUNT_LOCKED = 'ACCOUNT_LOCKED'


def get_db_connection():
    """Crea conexión a la base de datos de logging"""
    try:
        return mysql.connector.connect(**LOGGING_DB_CONFIG)
    except Exception as e:
        logger.error(f"Error conectando a DB de logging: {e}")
        return None


def create_logging_tables():
    """
    Crea/actualiza las tablas necesarias para el logging de seguridad
    
    NOTA: Esta función está COMENTADA porque solo tenemos permisos SELECT e INSERT.
    Las tablas deben ser creadas manualmente por el administrador de la BD.
    
    SQL para crear las tablas manualmente:
    
    -- Tabla de usuarios
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        email VARCHAR(255),
        full_name VARCHAR(255),
        is_active BOOLEAN DEFAULT TRUE,
        failed_login_attempts INT DEFAULT 0,
        locked_until DATETIME NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_username (username),
        INDEX idx_is_active (is_active)
    );
    
    -- Tabla para registrar inicios de sesión
    CREATE TABLE IF NOT EXISTS user_logins (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        login_timestamp DATETIME NOT NULL,
        ip_address VARCHAR(45),
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_username (username),
        INDEX idx_timestamp (login_timestamp),
        INDEX idx_ip (ip_address)
    );
    
    -- Tabla para registrar consultas
    CREATE TABLE IF NOT EXISTS user_queries (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        query_timestamp DATETIME NOT NULL,
        sql_query TEXT,
        query_parameters TEXT,
        start_date DATE,
        end_date DATE,
        start_time TIME,
        end_time TIME,
        linea VARCHAR(50),
        interval_type VARCHAR(20),
        ip_address VARCHAR(45),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_username (username),
        INDEX idx_timestamp (query_timestamp),
        INDEX idx_linea (linea)
    );
    
    -- Tabla para eventos de seguridad
    CREATE TABLE IF NOT EXISTS security_events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_type VARCHAR(50) NOT NULL,
        username VARCHAR(255),
        ip_address VARCHAR(45),
        user_agent TEXT,
        event_timestamp DATETIME NOT NULL,
        severity VARCHAR(20),
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_event_type (event_type),
        INDEX idx_username (username),
        INDEX idx_timestamp (event_timestamp),
        INDEX idx_severity (severity)
    );
    """
    
    logger.warning("⚠️ create_logging_tables() está deshabilitada (solo permisos SELECT/INSERT)")
    logger.info("Las tablas deben ser creadas manualmente por el DBA")
    return True
    
    # CÓDIGO COMENTADO - Solo con permisos CREATE TABLE
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # ... queries CREATE TABLE aquí ...
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("✓ Tablas creadas correctamente")
        return True
        
    except Exception as e:
        logger.error(f"Error creando tablas: {str(e)}")
        return False
    """


def log_login_attempt(username, success, ip_address=None, user_agent=None, failure_reason=None):
    """
    Registra un intento de login (exitoso o fallido)
    
    NOTA: La tabla user_logins real NO tiene columnas 'success' ni 'failure_reason'.
    Solo registra logins EXITOSOS. Los fallidos se registran en security_events.
    
    Args:
        username (str): Nombre de usuario
        success (bool): True si login exitoso, False si falló
        ip_address (str): IP del usuario
        user_agent (str): User agent del navegador
        failure_reason (str): Razón del fallo si aplica (se guarda en security_events)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        login_time = datetime.now()
        
        # Solo registrar en user_logins si el login fue EXITOSO
        if success:
            query = """
                INSERT INTO user_logins 
                (username, login_timestamp, ip_address, user_agent)
                VALUES (%s, %s, %s, %s)
            """
            params = (username, login_time, ip_address, user_agent)
            cursor.execute(query, params)
            conn.commit()
            logger.info(f"Login EXITOSO: {username} desde {ip_address} a las {login_time}")
        
        cursor.close()
        conn.close()
        
        # COMENTADO - Tabla security_events no existe aún
        # Registrar evento de seguridad (tanto éxito como fallo)
        # if not success:
        #     log_security_event(
        #         SecurityEvent.LOGIN_FAILURE,
        #         username=username,
        #         ip_address=ip_address,
        #         user_agent=user_agent,
        #         severity='WARNING',
        #         details=f"Intento de login fallido: {failure_reason}"
        #     )
        # else:
        #     log_security_event(
        #         SecurityEvent.LOGIN_SUCCESS,
        #         username=username,
        #         ip_address=ip_address,
        #         user_agent=user_agent,
        #         severity='INFO',
        #         details="Login exitoso"
        #     )
        
        return True
        
    except Exception as e:
        logger.error(f"Error registrando login attempt: {str(e)}")
        return False


def log_query(username, sql_query=None, query_params=None, 
              start_date=None, end_date=None, start_time=None, end_time=None,
              linea=None, interval_type=None, ip_address=None):
    """
    Registra una consulta realizada por el usuario
    
    NOTA: Schema actualizado según tabla real user_queries:
    - Columnas: username, query_timestamp, sql_query, query_parameters, 
                start_date, end_date, start_time, end_time, linea, interval_type, ip_address
    
    Args:
        username (str): Usuario que ejecutó la query
        sql_query (str): Query SQL ejecutada (opcional)
        query_params (dict): Parámetros de la consulta
        start_date (str/date): Fecha inicio
        end_date (str/date): Fecha fin
        start_time (str/time): Hora inicio
        end_time (str/time): Hora fin
        linea (str): Línea consultada
        interval_type (str): Tipo de intervalo (hour, day, etc)
        ip_address (str): IP del usuario
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        query = """
            INSERT INTO user_queries (
                username, query_timestamp, sql_query, query_parameters,
                start_date, end_date, start_time, end_time, linea, interval_type, ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        query_time = datetime.now()
        
        # Convertir parámetros a JSON string (sin credenciales)
        if query_params:
            safe_params = {k: v for k, v in query_params.items() if k not in ['password', 'token', 'secret']}
            params_json = json.dumps(safe_params, ensure_ascii=False)
        else:
            params_json = '{}'
        
        # Si sql_query es None, usar string vacío
        if sql_query is None:
            sql_query = ''
        
        # Convertir fechas a objetos date
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                if isinstance(start_date, str):
                    start_date_obj = datetime.strptime(start_date.split(' ')[0], '%Y-%m-%d').date()
                else:
                    start_date_obj = start_date
            except:
                pass
        
        if end_date:
            try:
                if isinstance(end_date, str):
                    end_date_obj = datetime.strptime(end_date.split(' ')[0], '%Y-%m-%d').date()
                else:
                    end_date_obj = end_date
            except:
                pass
        
        # Convertir tiempos a objetos time
        start_time_obj = None
        end_time_obj = None
        
        if start_time:
            try:
                if isinstance(start_time, str):
                    start_time_obj = datetime.strptime(start_time, '%H:%M:%S').time()
                else:
                    start_time_obj = start_time
            except:
                try:
                    start_time_obj = datetime.strptime(start_time, '%H:%M').time()
                except:
                    pass
        
        if end_time:
            try:
                if isinstance(end_time, str):
                    end_time_obj = datetime.strptime(end_time, '%H:%M:%S').time()
                else:
                    end_time_obj = end_time
            except:
                try:
                    end_time_obj = datetime.strptime(end_time, '%H:%M').time()
                except:
                    pass
        
        params = (
            username, 
            query_time, 
            sql_query,
            params_json,
            start_date_obj, 
            end_date_obj,
            start_time_obj,
            end_time_obj,
            linea, 
            interval_type, 
            ip_address
        )
        
        # Debug: Mostrar parámetros antes de insertar
        logger.info(f"🔍 Insertando query - User: {username}, Linea: {linea}, IP: {ip_address}")
        logger.debug(f"Params: start_date={start_date_obj}, end_date={end_date_obj}, start_time={start_time_obj}, end_time={end_time_obj}")
        
        cursor.execute(query, params)
        conn.commit()
        
        logger.info(f"✅ Query registrada exitosamente - ID: {cursor.lastrowid}, Usuario: {username}, Linea: {linea}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error registrando query en user_queries: {str(e)}")
        logger.error(f"Params recibidos: username={username}, linea={linea}, start_date={start_date}, end_date={end_date}")
        return False


# COMENTADO - Tabla security_events no existe aún
# def log_security_event(event_type, username=None, ip_address=None, user_agent=None, 
#                        severity='INFO', details=None):
#     """
#     Registra un evento de seguridad genérico
#     
#     Args:
#         event_type (str): Tipo de evento (usar SecurityEvent constants)
#         username (str): Usuario relacionado
#         ip_address (str): IP del usuario
#         user_agent (str): User agent
#         severity (str): Severidad (INFO, WARNING, ERROR, CRITICAL)
#         details (str): Detalles adicionales
#     """
#     try:
#         conn = get_db_connection()
#         if not conn:
#             return False
#             
#         cursor = conn.cursor()
#         
#         query = """
#             INSERT INTO security_events 
#             (event_type, username, ip_address, user_agent, event_timestamp, severity, details)
#             VALUES (%s, %s, %s, %s, %s, %s, %s)
#         """
#         
#         event_time = datetime.now()
#         params = (event_type, username, ip_address, user_agent, event_time, severity, details)
#         
#         cursor.execute(query, params)
#         conn.commit()
#         cursor.close()
#         conn.close()
#         
#         logger.info(f"Evento de seguridad: {event_type} - {severity} - {username}")
#         return True
#         
#     except Exception as e:
#         logger.error(f"Error registrando evento de seguridad: {str(e)}")
#         return False


# COMENTADO - Tabla security_events no existe aún
# def get_failed_login_attempts(username, time_window_minutes=30):
#     """
#     Obtiene el número de intentos fallidos de login en una ventana de tiempo
#     
#     NOTA: Como user_logins solo registra logins exitosos, los intentos fallidos
#     se cuentan desde la tabla security_events con event_type = 'LOGIN_FAILURE'
#     
#     Args:
#         username (str): Usuario a verificar
#         time_window_minutes (int): Ventana de tiempo en minutos
#         
#     Returns:
#         int: Número de intentos fallidos
#     """
#     try:
#         conn = get_db_connection()
#         if not conn:
#             return 0
#             
#         cursor = conn.cursor()
#         
#         # Contar intentos fallidos desde security_events
#         query = """
#             SELECT COUNT(*) as attempts
#             FROM security_events
#             WHERE username = %s 
#             AND event_type = 'LOGIN_FAILURE'
#             AND event_timestamp >= DATE_SUB(NOW(), INTERVAL %s MINUTE)
#         """
#         
#         cursor.execute(query, (username, time_window_minutes))
#         result = cursor.fetchone()
#         cursor.close()
#         conn.close()
#         
#         return result[0] if result else 0
#         
#     except Exception as e:
#         logger.error(f"Error obteniendo intentos fallidos: {str(e)}")
#         return 0


def get_user_ip(request):
    """Obtiene la IP real del usuario considerando proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def get_user_agent(request):
    """Obtiene el User-Agent del navegador"""
    return request.headers.get('User-Agent', 'Unknown')


def reset_failed_attempts(username):
    """
    Resetea el contador de intentos fallidos de un usuario
    Útil para desbloquear cuentas manualmente
    
    Args:
        username (str): Usuario a desbloquear
        
    Returns:
        bool: True si se desbloqueó correctamente
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Resetear contador en la tabla usuarios (si existe la columna)
        # NOTA: Como solo tenemos permisos SELECT/INSERT, esto podría fallar
        # En ese caso, pedir al DBA que ejecute:
        # UPDATE usuarios SET failed_login_attempts = 0, locked_until = NULL WHERE username = 'usuario';
        
        try:
            query = """
                UPDATE usuarios 
                SET failed_login_attempts = 0, locked_until = NULL
                WHERE username = %s
            """
            cursor.execute(query, (username,))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"✓ Usuario '{username}' desbloqueado correctamente")
                return True
            else:
                logger.warning(f"Usuario '{username}' no encontrado")
                return False
                
        except mysql.connector.Error as e:
            logger.error(f"Error UPDATE (permisos?): {e}")
            logger.info(f"Pide al DBA ejecutar: UPDATE usuarios SET failed_login_attempts = 0, locked_until = NULL WHERE username = '{username}';")
            return False
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error reseteando intentos fallidos: {str(e)}")
        return False


# Inicializar tablas si se ejecuta directamente
if __name__ == "__main__":
    print("=" * 70)
    print("SISTEMA DE LOGGING DE SEGURIDAD")
    print("=" * 70)
    print("\n⚠️  NOTA: Solo tienes permisos SELECT e INSERT")
    print("Las tablas deben ser creadas manualmente por el DBA\n")
    print("SQL necesario para crear tablas:")
    print("-" * 70)
    create_logging_tables()  # Muestra el SQL necesario
    print("\n" + "=" * 70)
