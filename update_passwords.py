"""Update user passwords with known values for testing"""
import pymysql
from argon2 import PasswordHasher

ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)

# Hash passwords
pwd_admin = ph.hash("admin123")  # Chacabuco
pwd_admin_cn = ph.hash("admincn123")  # Central Norte

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='camet_global',
    charset='utf8mb4'
)

cur = conn.cursor()

# Update passwords
cur.execute('UPDATE user SET password = %s WHERE username = %s', (pwd_admin, 'admin'))
cur.execute('UPDATE user SET password = %s WHERE username = %s', (pwd_admin_cn, 'admin_cn'))

conn.commit()

print('✓ Passwords updated:')
print('  admin: admin123')
print('  admin_cn: admincn123')

conn.close()
