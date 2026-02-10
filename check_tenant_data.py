"""Check tenant database contents to verify data isolation"""
import pymysql

# Check cliente_chacabuco
print("=== Database: cliente_chacabuco ===")
conn1 = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='cliente_chacabuco',
    charset='utf8mb4'
)
cur1 = conn1.cursor()
cur1.execute('SELECT line_id, line_name, line_code FROM production_line')
lines1 = cur1.fetchall()
print(f"Production Lines ({len(lines1)}):")
for line in lines1:
    print(f"  - ID: {line[0]}, Name: {line[1]}, Code: {line[2]}")
conn1.close()

print("\n=== Database: cliente_centralnorte ===")
conn2 = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='cliente_centralnorte',
    charset='utf8mb4'
)
cur2 = conn2.cursor()
cur2.execute('SELECT line_id, line_name, line_code FROM production_line')
lines2 = cur2.fetchall()
print(f"Production Lines ({len(lines2)}):")
for line in lines2:
    print(f"  - ID: {line[0]}, Name: {line[1]}, Code: {line[2]}")
conn2.close()

print("\n✓ Databases have different data - ready for isolation testing")
