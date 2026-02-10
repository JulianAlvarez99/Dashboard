"""Check user-tenant-database mapping"""
import pymysql
import json

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='camet_global',
    charset='utf8mb4'
)

cur = conn.cursor()
cur.execute('''
    SELECT u.user_id, u.username, u.tenant_id, t.company_name, t.config_tenant
    FROM user u
    JOIN tenant t ON u.tenant_id = t.tenant_id
''')

rows = cur.fetchall()

print('\n=== User-Tenant Mapping ===')
for r in rows:
    config = json.loads(r[4])
    print(f'''
User ID:    {r[0]}
Username:   {r[1]}
Tenant ID:  {r[2]}
Company:    {r[3]}
Database:   {config.get('db_name')}
''')

conn.close()
