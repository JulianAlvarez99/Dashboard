"""Verify user password hashes"""
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='camet_global',
    charset='utf8mb4'
)

cur = conn.cursor()
cur.execute('SELECT user_id, username, password FROM user')
rows = cur.fetchall()

print('\n=== User Passwords ===')
for r in rows:
    pwd_prefix = r[2][:30] if r[2] else 'NO PASSWORD'
    print(f'''
User ID:  {r[0]}
Username: {r[1]}
Password: {pwd_prefix}... (length: {len(r[2]) if r[2] else 0})
Hash Type: {'Argon2' if r[2] and r[2].startswith('$argon2') else 'Unknown'}
''')

conn.close()
