import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('FLASK_SECRET_KEY',  'x'*32)
os.environ.setdefault('SECRET_KEY',        'x'*32)
os.environ.setdefault('API_INTERNAL_KEY',  'x'*32)
os.environ.setdefault('JWT_SECRET_KEY',    'x'*32)

import pandas as pd
from new_app.services.widgets.engine import WidgetEngine
from new_app.services.widgets.base import WidgetContext

engine = WidgetEngine()

# A: camel_to_snake
module_name = engine._class_to_module('KpiRejectedRate')
print(f'  A camel_to_snake  : KpiRejectedRate -> {module_name}')
assert module_name == 'kpi_rejected_rate'

# B: class resolution (auto-discovery)
cls = engine._resolve_class('KpiRejectedRate')
assert cls is not None, 'Class not found! Check filename matches snake_case.'
print(f'  B class resolved  : {cls.__module__}.{cls.__name__}')

# C: process() with sample data (3 reject / 5 total = 60%)
df = pd.DataFrame({'area_type': ['output', 'reject', 'output', 'reject', 'reject']})
ctx = WidgetContext(
    widget_id=99,
    widget_name='KpiRejectedRate',
    display_name='Tasa de Rechazo (%)',
    data=df,
    config={'decimal_places': 1},
)
result = cls(ctx).process()
d = result.to_dict()
print(f'  C process() result: {d}')
assert d['data']['value'] == 60.0
assert d['data']['unit']  == '%'
assert d['widget_type']   == 'kpi'

# D: layout entry
from new_app.config.widget_layout import WIDGET_LAYOUT
entry = WIDGET_LAYOUT.get('KpiRejectedRate')
assert entry is not None, 'KpiRejectedRate missing from WIDGET_LAYOUT!'
print(f'  D layout entry    : {entry}')

# E: edge case — empty df
ctx_empty = WidgetContext(widget_id=99, widget_name='KpiRejectedRate',
                          display_name='', data=pd.DataFrame())
r_empty = cls(ctx_empty).process()
assert r_empty.data['value'] == 0.0
print(f'  E empty-df guard  : value={r_empty.data["value"]} OK')

# F: validate_layout_consistency passes
from new_app.config.widget_layout import validate_layout_consistency
warnings = validate_layout_consistency()
print(f'  F layout validate : OK ({len(warnings)} warning(s))')

print()
print('  ALL STEPS PASSED')
