"""
Script de Administración de Usuarios
Crea, actualiza y gestiona usuarios en la base de datos con contraseñas hasheadas
"""

import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv
from getpass import getpass
import secrets
import string

load_dotenv()

# Configuración de BD
AUTH_DB_CONFIG = {
    # 'host': os.getenv('AUTH_MYSQL_HOST', 'localhost'),
    'host': 'camet.com.ar',
    'port': int(os.getenv('AUTH_MYSQL_PORT', 3306)),
    'user': os.getenv('AUTH_MYSQL_USER'),
    'password': os.getenv('AUTH_MYSQL_PASSWORD'),
    'database': os.getenv('AUTH_MYSQL_DB', 'cametcom_usuarios'),
    'connect_timeout': 60,
}


def generate_random_password(length=12):
    """
    Generar contraseña aleatoria segura
    
    Args:
        length: Longitud de la contraseña (default: 12)
    
    Returns:
        str: Contraseña aleatoria con mayúsculas, minúsculas, números y símbolos
    """
    # Caracteres permitidos: letras mayúsculas, minúsculas, números y algunos símbolos
    chars = string.ascii_letters + string.digits + '@#$%&*'
    
    # Generar contraseña aleatoria
    password = ''.join(secrets.choice(chars) for _ in range(length))
    
    return password


def hash_password(password):
    """Hashea una contraseña con bcrypt"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_user(username, password, privilege='cliente', name_business='Chacabuco'):
    """
    Crea un nuevo usuario en la base de datos
    
    Args:
        username (str): Nombre de usuario único
        password (str): Contraseña en texto plano (se hasheará automáticamente)
        privilege (str): Privilegio del usuario ('administrador' o 'cliente')
        name_business (str): Nombre de la empresa ('Camet' o 'Chacabuco')
    """
    # Validar privilegio y empresa
    valid_privileges = ['administrador', 'cliente']
    valid_businesses = ['Camet', 'Chacabuco', 'CentralNorte', 'Solimeno']
    
    if privilege not in valid_privileges:
        print(f"✗ Error: Privilegio inválido. Debe ser 'administrador' o 'cliente'")
        return False
    
    if name_business not in valid_businesses:
        print(f"✗ Error: Empresa inválida. Debe ser 'Camet' o 'Chacabuco'")
        return False
    
    # Validar regla de negocio: Administrador solo para Camet
    if privilege == 'administrador' and name_business != 'Camet':
        print(f"✗ Error: Los administradores solo pueden estar asociados a 'Camet'")
        return False
    
    try:
        conn = mysql.connector.connect(**AUTH_DB_CONFIG)
        cursor = conn.cursor()
        
        # Hashear contraseña
        password_hash = hash_password(password)
        
        # Insertar usuario con todas las columnas
        query = """
            INSERT INTO usuarios (username, password, privilege, name_business)
            VALUES (%s, %s, %s, %s)
        """
        
        cursor.execute(query, (username, password_hash, privilege, name_business))
        conn.commit()
        
        print(f"✓ Usuario '{username}' creado exitosamente")
        print(f"  Privilegio: {privilege}")
        print(f"  Empresa: {name_business}")
        print(f"  Hash generado: {password_hash[:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.IntegrityError:
        print(f"✗ Error: El usuario '{username}' ya existe")
        return False
    except Exception as e:
        print(f"✗ Error creando usuario: {e}")
        return False


def update_password(username, new_password):
    """
    Actualiza la contraseña de un usuario existente
    
    Args:
        username (str): Nombre de usuario
        new_password (str): Nueva contraseña en texto plano
    """
    try:
        conn = mysql.connector.connect(**AUTH_DB_CONFIG)
        cursor = conn.cursor()
        
        # Hashear nueva contraseña
        password_hash = hash_password(new_password)
        
        # Actualizar (solo password, sin updated_at)
        query = """
            UPDATE usuarios 
            SET password = %s
            WHERE username = %s
        """
        
        cursor.execute(query, (password_hash, username))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"✓ Contraseña de '{username}' actualizada exitosamente")
            return True
        else:
            print(f"✗ Usuario '{username}' no encontrado")
            return False
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ Error actualizando contraseña: {e}")
        return False


def list_users():
    """
    Lista todos los usuarios en la base de datos con sus privilegios y empresas
    """
    try:
        conn = mysql.connector.connect(**AUTH_DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT user_id, username, privilege, name_business
            FROM usuarios
            ORDER BY name_business, privilege, username
        """
        
        cursor.execute(query)
        users = cursor.fetchall()
        
        if not users:
            print("No hay usuarios en la base de datos")
            return
        
        print("\n" + "=" * 80)
        print("USUARIOS REGISTRADOS")
        print("=" * 80)
        
        for user in users:
            print(f"\n  ID: {user['user_id']}")
            print(f"  Usuario: {user['username']}")
            print(f"  Privilegio: {user['privilege']}")
            print(f"  Empresa: {user['name_business']}")
        
        print("\n" + "=" * 80)
        print(f"Total: {len(users)} usuarios")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ Error listando usuarios: {e}")


def interactive_menu():
    """Menú interactivo para gestión de usuarios"""
    while True:
        print("\n" + "=" * 80)
        print("GESTIÓN DE USUARIOS - Dashboard Chacabuco")
        print("=" * 80)
        print("\n1. Crear nuevo usuario")
        print("2. Actualizar contraseña")
        print("3. Listar usuarios")
        print("4. Generar hash de contraseña (solo mostrar)")
        print("0. Salir")
        
        choice = input("\nSelecciona una opción: ").strip()
        
        if choice == '1':
            print("\n--- CREAR NUEVO USUARIO ---")
            username = input("Usuario: ").strip()
            
            print("\nPrivilegio:")
            print("  1. Cliente")
            print("  2. Administrador")
            priv_choice = input("Selecciona (1-2): ").strip()
            privilege = 'cliente' if priv_choice == '1' else 'administrador'
            
            print("\nEmpresa:")
            print("  1. Chacabuco")
            print("  2. Camet")
            biz_choice = input("Selecciona (1-2): ").strip()
            name_business = 'Chacabuco' if biz_choice == '1' else 'Camet'
            
            # Opción de generar contraseña aleatoria o ingresar manualmente
            print("\nContraseña:")
            print("  1. Ingresar manualmente")
            print("  2. Generar aleatoriamente")
            pwd_choice = input("Selecciona (1-2): ").strip()
            
            if pwd_choice == '2':
                # Generar contraseña aleatoria
                password = generate_random_password(12)
                print(f"\n✓ Contraseña generada: {password}")
                print("  ⚠️  IMPORTANTE: Guarda esta contraseña, se mostrará solo una vez")
                input("\nPresiona ENTER cuando hayas guardado la contraseña...")
            else:
                # Ingresar manualmente con opción de ver la contraseña
                print("\n¿Deseas ver la contraseña mientras la escribes? (s/n): ", end='')
                show_pwd = input().strip().lower() == 's'
                
                if show_pwd:
                    password = input("Contraseña: ").strip()
                    password_confirm = input("Confirmar contraseña: ").strip()
                else:
                    password = getpass("Contraseña: ")
                    password_confirm = getpass("Confirmar contraseña: ")
                
                if password != password_confirm:
                    print("✗ Las contraseñas no coinciden")
                    continue
            
            create_user(username, password, privilege, name_business)
        
        elif choice == '2':
            print("\n--- ACTUALIZAR CONTRASEÑA ---")
            username = input("Usuario: ").strip()
            
            # Opción de generar contraseña aleatoria o ingresar manualmente
            print("\nNueva contraseña:")
            print("  1. Ingresar manualmente")
            print("  2. Generar aleatoriamente")
            pwd_choice = input("Selecciona (1-2): ").strip()
            
            if pwd_choice == '2':
                # Generar contraseña aleatoria
                new_password = generate_random_password(12)
                print(f"\n✓ Contraseña generada: {new_password}")
                print("  ⚠️  IMPORTANTE: Guarda esta contraseña, se mostrará solo una vez")
                input("\nPresiona ENTER cuando hayas guardado la contraseña...")
            else:
                # Ingresar manualmente con opción de ver la contraseña
                print("\n¿Deseas ver la contraseña mientras la escribes? (s/n): ", end='')
                show_pwd = input().strip().lower() == 's'
                
                if show_pwd:
                    new_password = input("Nueva contraseña: ").strip()
                    password_confirm = input("Confirmar nueva contraseña: ").strip()
                else:
                    new_password = getpass("Nueva contraseña: ")
                    password_confirm = getpass("Confirmar nueva contraseña: ")
                
                if new_password != password_confirm:
                    print("✗ Las contraseñas no coinciden")
                    continue
            
            update_password(username, new_password)
        
        elif choice == '3':
            list_users()
        
        elif choice == '4':
            print("\n--- GENERAR HASH ---")
            print("\nOpciones:")
            print("  1. Ingresar contraseña manualmente")
            print("  2. Generar contraseña aleatoria")
            hash_choice = input("Selecciona (1-2): ").strip()
            
            if hash_choice == '2':
                password = generate_random_password(12)
                print(f"\n✓ Contraseña generada: {password}")
            else:
                print("\n¿Deseas ver la contraseña mientras la escribes? (s/n): ", end='')
                show_pwd = input().strip().lower() == 's'
                
                if show_pwd:
                    password = input("Contraseña: ").strip()
                else:
                    password = getpass("Contraseña: ")
            
            hashed = hash_password(password)
            print(f"\nHash generado:\n{hashed}")
            print("\nPuedes insertar esto manualmente en la BD con:")
            print(f"INSERT INTO usuarios (username, password) VALUES ('tu_usuario', '{hashed}');")
        
        elif choice == '0':
            print("\n¡Hasta luego!")
            break
        
        else:
            print("✗ Opción inválida")


if __name__ == '__main__':
    import sys
    
    print("=" * 80)
    print("ADMINISTRACIÓN DE USUARIOS - Dashboard Chacabuco")
    print("=" * 80)
    
    # Verificar configuración
    if not AUTH_DB_CONFIG.get('user') or not AUTH_DB_CONFIG.get('password'):
        print("\n⚠️  ADVERTENCIA: Falta configuración de base de datos")
        print("Por favor configura las variables de entorno en .env:")
        print("  - AUTH_MYSQL_USER")
        print("  - AUTH_MYSQL_PASSWORD")
        print("  - AUTH_MYSQL_DB")
        sys.exit(1)
    
    # Si se pasan argumentos por línea de comando
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'create' and len(sys.argv) >= 4:
            username = sys.argv[2]
            password = sys.argv[3]
            privilege = sys.argv[4] if len(sys.argv) > 4 else 'cliente'
            name_business = sys.argv[5] if len(sys.argv) > 5 else 'Chacabuco'
            create_user(username, password, privilege, name_business)
        
        elif command == 'hash' and len(sys.argv) >= 3:
            password = sys.argv[2]
            hashed = hash_password(password)
            print(f"\nHash: {hashed}")
        
        elif command == 'list':
            list_users()
        
        else:
            print("\nUso:")
            print("  python manage_users.py create <usuario> <contraseña> [privilegio] [empresa]")
            print("  python manage_users.py hash <contraseña>")
            print("  python manage_users.py list")
            print("  python manage_users.py  (menú interactivo)")
            print("\nEjemplo:")
            print("  python manage_users.py create juan pass123 cliente Chacabuco")
            print("  python manage_users.py create admin pass456 administrador Camet")
    
    else:
        # Menú interactivo
        interactive_menu()
