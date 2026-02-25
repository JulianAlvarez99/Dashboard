import pymysql
import argparse
import random
from datetime import datetime, timedelta

def load_detections(db_name, line_name, num_detections=1000, num_downtimes=10):
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database=db_name,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with conn.cursor() as cur:
            # 1. Obtener line_id a partir del line_name
            cur.execute("SELECT line_id FROM PRODUCTION_LINE WHERE line_code = %s OR line_name = %s", (line_name, line_name))
            line_row = cur.fetchone()
            if not line_row:
                print(f"Error: Line '{line_name}' not found in database {db_name}.")
                return
            line_id = line_row['line_id']

            # 2. Obtener areas y productos de la base de datos para simular datos reales
            cur.execute("SELECT area_id FROM AREA WHERE line_id = %s", (line_id,))
            areas = [row['area_id'] for row in cur.fetchall()]
            if not areas:
                print(f"Error: No areas found for line '{line_name}'.")
                return

            cur.execute("SELECT product_id FROM PRODUCT LIMIT 10")
            products = [row['product_id'] for row in cur.fetchall()]
            if not products:
                print(f"Error: No products found in database.")
                return

            # Nombres de tabla basados en el requerimiento del usuario (detection_line_{nombre_linea})
            table_detection = f"detection_line_{line_name.lower().replace(' ', '_')}"
            table_downtime = f"downtime_events_{line_name.lower().replace(' ', '_')}"

            # Ensure tables exist (optional, assuming they are created by another process or creating them if missing based on template)
            try:
                cur.execute(f"SELECT 1 FROM {table_detection} LIMIT 1")
            except pymysql.MySQLError:
                print(f"Creating table {table_detection} from template...")
                cur.execute(f"CREATE TABLE {table_detection} LIKE DETECTION_LINE_TEMPLATE")

            try:
                cur.execute(f"SELECT 1 FROM {table_downtime} LIMIT 1")
            except pymysql.MySQLError:
                print(f"Creating table {table_downtime} from template...")
                cur.execute(f"CREATE TABLE {table_downtime} LIKE DOWNTIME_EVENTS_TEMPLATE")

            conn.commit()

            print(f"Generating {num_detections} detections for {table_detection}...")
            
            # Generar datos de detección
            start_date = datetime.now() - timedelta(days=7)
            detections = []
            current_time = start_date
            
            for _ in range(num_detections):
                # Simular 10-20 segundos entre detecciones
                current_time += timedelta(seconds=random.randint(10, 20))
                area_id = random.choice(areas)
                product_id = random.choice(products)
                detections.append((current_time.strftime('%Y-%m-%d %H:%M:%S'), area_id, product_id))

            # Insert en batches
            insert_query = f"""
                INSERT INTO {table_detection} (detected_at, area_id, product_id) 
                VALUES (%s, %s, %s)
            """
            cur.executemany(insert_query, detections)
            conn.commit()
            print(f"✅ {num_detections} detections loaded into {table_detection}.")

            # Generar datos de downtime
            print(f"Generating {num_downtimes} downtimes for {table_downtime}...")
            downtimes = []
            for _ in range(num_downtimes):
                dt_start = start_date + timedelta(days=random.uniform(0, 6))
                # Duracion entre 5 y 120 minutos
                duration_secs = random.randint(300, 7200)
                dt_end = dt_start + timedelta(seconds=duration_secs)
                
                # Transformar duracion a hh:mm:ss
                hoursStr = f"{duration_secs // 3600:02d}"
                minutesStr = f"{(duration_secs % 3600) // 60:02d}"
                secondsStr = f"{duration_secs % 60:02d}"
                duration_time = f"{hoursStr}:{minutesStr}:{secondsStr}"
                
                # Mock last detection_id and reason
                last_detection_id = random.randint(1, num_detections)
                reason_code = random.choice([101, 102, 201, 301, 404])
                reason = "Simulated downtime reason " + str(reason_code)

                downtimes.append((
                    last_detection_id, 
                    dt_start.strftime('%Y-%m-%d %H:%M:%S'), 
                    dt_end.strftime('%Y-%m-%d %H:%M:%S'), 
                    duration_time, 
                    reason_code, 
                    reason
                ))

            insert_dt_query = f"""
                INSERT INTO {table_downtime} 
                (last_detection_id, start_time, end_time, duration, reason_code, reason)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.executemany(insert_dt_query, downtimes)
            conn.commit()
            print(f"✅ {num_downtimes} downtimes loaded into {table_downtime}.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed detection and downtime tables.")
    parser.add_argument("--db", required=True, help="Database name (e.g., cliente_chacabuco)")
    parser.add_argument("--line", required=True, help="Line name or code (e.g., L1)")
    parser.add_argument("--n-det", type=int, default=1000, help="Number of detections to generate")
    parser.add_argument("--n-dt", type=int, default=10, help="Number of downtimes to generate")
    
    args = parser.parse_args()
    
    load_detections(args.db, args.line, args.n_det, args.n_dt)
#python scripts/load_detections.py --db cliente_chacabuco --line L1 