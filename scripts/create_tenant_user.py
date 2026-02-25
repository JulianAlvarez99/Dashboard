import pymysql
import argparse
import json
import sys

try:
    from argon2 import PasswordHasher
except ImportError:
    print("Please install argon2-cffi: pip install argon2-cffi")
    sys.exit(1)

def create_tenant_and_user(company_name, db_name, username, email, raw_password, role="ADMIN"):
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='camet_global',
        charset='utf8mb4'
    )
    
    ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)
    
    try:
        cur = conn.cursor()
        
        # 1. Check if username or email already exists
        cur.execute("SELECT user_id FROM USER WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone():
            print(f"Error: Username '{username}' or email '{email}' already exists.")
            return

        # 2. Insert or find Tenant
        # To avoid duplicate tenants with exactly the same name for testing purposes
        cur.execute("SELECT tenant_id FROM TENANT WHERE company_name = %s", (company_name,))
        tenant_row = cur.fetchone()
        
        if tenant_row:
            tenant_id = tenant_row[0]
            print(f"ℹ️ Found existing tenant '{company_name}' with ID {tenant_id}")
        else:
            config_tenant = json.dumps({
                "db_name": db_name,
                "theme": "light",
                "max_users": 10
            })
            
            cur.execute(
                "INSERT INTO TENANT (company_name, config_tenant) VALUES (%s, %s)",
                (company_name, config_tenant)
            )
            tenant_id = cur.lastrowid
            print(f"✅ Created tenant '{company_name}' with ID {tenant_id}")
        
        # 3. Create User
        hashed_password = ph.hash(raw_password)
        permissions = json.dumps(["read", "write", "admin"])
        
        cur.execute("""
            INSERT INTO USER (tenant_id, username, email, password, role, permissions)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (tenant_id, username, email, hashed_password, role, permissions))
        
        user_id = cur.lastrowid
        print(f"✅ Created user '{username}' with ID {user_id} and role '{role}'")
        
        conn.commit()
        print("Done. Both tenant and user are ready.")
        
    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new tenant and user in the global database.")
    parser.add_argument("--company", required=True, help="Company Name")
    parser.add_argument("--db", required=True, help="Database Name mapped to this tenant")
    parser.add_argument("--user", required=True, help="Username")
    parser.add_argument("--email", required=True, help="Email address")
    parser.add_argument("--password", required=True, help="Password")
    parser.add_argument("--role", default="ADMIN", help="User role (e.g. ADMIN)")
    
    args = parser.parse_args()
    create_tenant_and_user(args.company, args.db, args.user, args.email, args.password, args.role)
#python scripts/create_tenant_user.py --company "Mi Nuevo Cliente" --db "cliente_nuevo" --user "admin_nuevo" --email "admin@misupercliente.com" --password "mipasswordSeguro123"
