import json
import os

# Archivo donde se guardará la configuración global
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'dashboard_settings.json')

# NUEVA ESTRUCTURA: Control granular por rol
DEFAULT_SETTINGS = {
    'card-evolution':    {'admin': True, 'client': True},
    'card-balance':      {'admin': True, 'client': True},
    'card-distribution': {'admin': True, 'client': True},
    'card-downtime':     {'admin': True, 'client': True} # Tabla detallada
}

class SettingsManager:
    @staticmethod
    def get_settings():
        """Lee la configuración actual. Si no existe o tiene formato viejo, devuelve default."""
        if not os.path.exists(SETTINGS_FILE):
            return DEFAULT_SETTINGS
        
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                
                # Validación simple: si el formato es viejo (booleanos planos), forzar default nuevo
                # Esto evita que la app rompa al migrar de la versión anterior a esta
                first_val = list(data.values())[0]
                if not isinstance(first_val, dict):
                    return DEFAULT_SETTINGS
                    
                return data
        except Exception as e:
            print(f"Error leyendo settings: {e}")
            return DEFAULT_SETTINGS

    @staticmethod
    def save_settings(new_settings):
        """Guarda la nueva configuración."""
        try:
            # Fusionar con defaults para asegurar estructura
            final_settings = DEFAULT_SETTINGS.copy()
            final_settings.update(new_settings)
            
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(final_settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error guardando settings: {e}")
            return False