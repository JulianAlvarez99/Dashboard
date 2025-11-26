import mysql.connector
import bcrypt
from flask_login import UserMixin
from config import Config

class User(UserMixin):
    """Clase de Usuario compatible con Flask-Login"""
    def __init__(self, user_id, username, privilege, name_business):
        self.id = user_id # Flask-Login requiere un atributo 'id'
        self.username = username
        self.privilege = privilege
        self.name_business = name_business

class AuthManager:
    """Maneja la verificación de credenciales y recuperación de usuarios"""
    
    @staticmethod
    def get_db_connection():
        try:
            return mysql.connector.connect(**Config.AUTH_DB_CONFIG)
        except Exception as e:
            print(f"Error conectando a Auth DB: {e}")
            return None

    @staticmethod
    def get_user_by_id(user_id):
        """Recupera un usuario por ID (para manejo de sesión)"""
        conn = AuthManager.get_db_connection()
        if not conn: return None
        
        try:
            cursor = conn.cursor(dictionary=True)
            # Prevenir SQL Injection usando parámetros
            cursor.execute("SELECT user_id, username, privilege, name_business FROM usuarios WHERE user_id = %s", (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                return User(
                    user_id=str(user_data['user_id']),
                    username=user_data['username'],
                    privilege=user_data['privilege'],
                    name_business=user_data['name_business']
                )
            return None
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    @staticmethod
    def verify_user(username, password_candidate):
        """
        Verifica credenciales contra la base de datos.
        Retorna objeto User si es válido, None si no.
        """
        conn = AuthManager.get_db_connection()
        if not conn: return None
        
        try:
            cursor = conn.cursor(dictionary=True)
            # SQL Injection prevenido por el uso de tuplas en execute
            cursor.execute("SELECT user_id, username, password, privilege, name_business FROM usuarios WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            
            if user_data:
                # La contraseña en BD viene como string, bcrypt necesita bytes
                stored_hash = user_data['password'].encode('utf-8')
                candidate_bytes = password_candidate.encode('utf-8')
                
                if bcrypt.checkpw(candidate_bytes, stored_hash):
                    return User(
                        user_id=str(user_data['user_id']),
                        username=user_data['username'],
                        privilege=user_data['privilege'],
                        name_business=user_data['name_business']
                    )
            return None
        except Exception as e:
            print(f"Error en verificación: {e}")
            return None
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()