from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from flask_login import login_required, current_user 
from db_manager import DataManager
from data_processor import DataProcessor
import security_logger

api_bp = Blueprint('api', __name__)
db_manager = DataManager()

def _adjust_visualization_range_by_shift(start_dt, end_dt, shift):
    """
    Ajusta los límites de visualización (start/end) para que los gráficos
    se centren en el horario del turno, SOLO si el rango seleccionado
    es de aproximadamente 1 día.
    """
    # Si el rango es mayor a 25 horas (multidía), no recortamos la visualización
    if (end_dt - start_dt).total_seconds() > 90000:
        return start_dt, end_dt

    # Definimos la fecha base (del start)
    base_date = start_dt.date()
    
    if shift == 'morning':
        # 06:00 a 14:00 del mismo día
        new_start = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=6)
        new_end = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=14)
    elif shift == 'afternoon':
        # 14:00 a 22:00 del mismo día
        new_start = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=14)
        new_end = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=22)
    elif shift == 'night':
        # 22:00 del día a 06:00 del día siguiente
        new_start = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=22)
        new_end = datetime.combine(base_date, datetime.min.time()) + timedelta(days=1, hours=6)
    else:
        return start_dt, end_dt

    return new_start, new_end

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    try:
        # 1. Recepción de Parámetros
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        interval = request.args.get('interval', '1h')
        lines_param = request.args.get('lines')
        product_id_param = request.args.get('product_id')
        shift_param = request.args.get('shift')
        
        # 2. Parseo de Fechas
        if end_str: end_date = datetime.fromisoformat(end_str)
        else: end_date = datetime.now()
        
        if start_str: start_date = datetime.fromisoformat(start_str)
        else: start_date = end_date - timedelta(hours=24)

        # --- AUDITORÍA DE SEGURIDAD (LOGGING) ---
        # Registramos qué está consultando el usuario
        security_logger.log_query(
            username=current_user.username,
            query_params=request.args.to_dict(), # Guardamos los filtros aplicados
            start_date=start_date,
            end_date=end_date,
            linea=lines_param if lines_param else "ALL",
            interval_type=interval,
            ip_address=security_logger.get_user_ip(request)
        )
        # ----------------------------------------
        
        # 3. Obtención de Datos Crudos (DB)
        selected_lines = lines_param.split(',') if lines_param and lines_param != 'ALL' else None
        df = db_manager.get_raw_production_data(start_date, end_date, selected_lines)
        
        # 4. Filtrado en Memoria (Producto y Turno)
        if not df.empty:
            if product_id_param and product_id_param != 'ALL':
                df = df[df['class_id'] == int(product_id_param)]
            
            if shift_param and shift_param != 'all':
                df = DataProcessor.filter_by_shift(df, shift_param)

        # 5. Ajuste de Rango para Visualización (Gráficos y Paradas)
        # Si se eligió un turno específico, ajustamos el eje X del gráfico para que haga "zoom"
        viz_start, viz_end = start_date, end_date
        if shift_param and shift_param != 'all':
            viz_start, viz_end = _adjust_visualization_range_by_shift(start_date, end_date, shift_param)

        # 6. Procesamiento de Negocio
        # Usamos las fechas ajustadas (viz_) para el cálculo de paradas en extremos y generación de charts
        downtime = DataProcessor.calculate_downtime(
            df, 
            threshold_seconds=300, 
            query_start=viz_start, 
            query_end=viz_end
        )
        
        kpis = DataProcessor.calculate_global_kpis(df, downtime)
        
        chart_prod = DataProcessor.get_product_chart_data(df, interval, viz_start, viz_end)
        chart_comp = DataProcessor.get_entry_exit_comparison(df, interval, viz_start, viz_end)
        products_dist = DataProcessor.get_product_distribution(df)

        # 7. Respuesta
        response = {
            'meta': { 'start': start_date.isoformat(), 'end': end_date.isoformat() },
            'kpis': kpis,
            'charts': { 'main': chart_prod, 'comparison': chart_comp },
            'downtime': {
                'events': downtime,
                'count': kpis['downtime_count'],
                'total_str': kpis['downtime_total_str']
            },
            'products': products_dist
        }
        return jsonify(response), 200

    except Exception as e:
        print(f"ERROR API: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Verifica el estado de la conexión a la base de datos."""
    return jsonify({'status': 'ok', 'env': db_manager.metadata_cache.get('classes', 'DB Error') and 'DB Connected'}), 200

@api_bp.route('/products_list', methods=['GET'])
def get_products_list():
    """Devuelve el listado de productos disponibles para los filtros."""
    try:
        classes = db_manager.metadata_cache.get('classes', {})
        product_list = []
        for class_id, data in classes.items():
            product_list.append({'id': class_id, 'name': data['class_name'], 'color': data['color']})
        product_list.sort(key=lambda x: x['name'])
        return jsonify(product_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500