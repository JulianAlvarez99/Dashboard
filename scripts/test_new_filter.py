"""
Integration test: adding a new filter.

Tests the full lifecycle of a filter class from auto-discovery through
validation and SQL clause generation — without needing a real DB or cache.

Adapt by swapping CLASS_NAME / PARAM_NAME / VALID_VALUE / INVALID_VALUE.

Steps
-----
A  camel_to_snake        PriorityFilter → priority_filter
B  class auto-discovery  importlib resolves the class correctly
C  class attributes      filter_type, param_name, placeholder, etc.
D  FilterConfig build    DB mock row + class attrs merge correctly
E  get_options()         static options list returned
F  validate()            valid value ✅ | invalid value ✗ | None (optional) ✅
G  get_default()         returns configured default
H  to_sql_clause()       produces correct (fragment, params) tuple
I  to_dict()             full serialization includes options list
"""

import importlib
import sys
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ─────────────────────────────────────────────────────────────────────────────
#  Test parameters — change these when testing a different filter
# ─────────────────────────────────────────────────────────────────────────────
CLASS_NAME    = "PriorityFilter"   # CamelCase class name
PARAM_NAME    = "priority"         # expected param_name class attribute
FILTER_TYPE   = "dropdown"         # expected filter_type class attribute
VALID_VALUE   = "high"             # a value that should pass validate()
INVALID_VALUE = "critical"         # a value that should fail validate()
DEFAULT_VALUE = None               # expected get_default() return value
SQL_VALUE     = "medium"           # value for to_sql_clause() test
MOCK_FILTER_ID = 42                # fake DB filter_id for FilterConfig

# ─────────────────────────────────────────────────────────────────────────────
PASS = "\u2705"
FAIL = "\u274c"
results = []


def check(label: str, ok: bool, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    msg = f"  {label:<28}: {detail}"
    print(f"{icon} {msg}")
    results.append(ok)


print(f"\n{'='*60}")
print(f"  Filter integration test: {CLASS_NAME}")
print(f"{'='*60}\n")

# ─────────────────────────────────────────────────────────────────────────────
#  A — camel_to_snake
# ─────────────────────────────────────────────────────────────────────────────
from new_app.utils.naming import camel_to_snake

snake = camel_to_snake(CLASS_NAME)
expected_snake = "priority_filter"
check(
    "A camel_to_snake",
    snake == expected_snake,
    f"{CLASS_NAME} → {snake}",
)

# ─────────────────────────────────────────────────────────────────────────────
#  B — auto-discovery via importlib
# ─────────────────────────────────────────────────────────────────────────────
from new_app.services.filters.base import BaseFilter

module_path = f"new_app.services.filters.types.{snake}"
try:
    mod = importlib.import_module(module_path)
    FilterClass = getattr(mod, CLASS_NAME, None)
    is_subclass = FilterClass is not None and issubclass(FilterClass, BaseFilter)
    check(
        "B class auto-discovery",
        is_subclass,
        f"{module_path}.{CLASS_NAME}",
    )
except ImportError as exc:
    check("B class auto-discovery", False, str(exc))
    FilterClass = None

# ─────────────────────────────────────────────────────────────────────────────
#  C — class attributes
# ─────────────────────────────────────────────────────────────────────────────
if FilterClass:
    attr_ok = (
        getattr(FilterClass, "filter_type", None) == FILTER_TYPE
        and getattr(FilterClass, "param_name", None) == PARAM_NAME
    )
    check(
        "C class attributes",
        attr_ok,
        f"filter_type={FilterClass.filter_type!r}  "
        f"param_name={FilterClass.param_name!r}  "
        f"placeholder={FilterClass.placeholder!r}",
    )
else:
    check("C class attributes", False, "class not resolved")

# ─────────────────────────────────────────────────────────────────────────────
#  D — FilterConfig construction (simulates FilterEngine logic)
# ─────────────────────────────────────────────────────────────────────────────
from new_app.services.filters.base import FilterConfig

if FilterClass:
    mock_row = {
        "filter_id": MOCK_FILTER_ID,
        "filter_name": CLASS_NAME,
        "display_order": 5,
        "description": "Test filter",
    }
    config = FilterConfig(
        filter_id=mock_row["filter_id"],
        class_name=mock_row["filter_name"],
        filter_type=FilterClass.filter_type,
        param_name=FilterClass.param_name,
        display_order=mock_row.get("display_order", 0),
        description=mock_row.get("description", ""),
        placeholder=FilterClass.placeholder,
        default_value=FilterClass.default_value,
        required=FilterClass.required,
        options_source=FilterClass.options_source,
        depends_on=FilterClass.depends_on,
        ui_config=dict(FilterClass.ui_config),
    )
    config_ok = (
        config.filter_id == MOCK_FILTER_ID
        and config.class_name == CLASS_NAME
        and config.param_name == PARAM_NAME
    )
    check(
        "D FilterConfig build",
        config_ok,
        f"filter_id={config.filter_id}  class_name={config.class_name!r}",
    )
    instance = FilterClass(config)
else:
    check("D FilterConfig build", False, "class not resolved")
    instance = None

# ─────────────────────────────────────────────────────────────────────────────
#  E — get_options()
# ─────────────────────────────────────────────────────────────────────────────
if instance:
    options = instance.get_options()
    option_values = [o.value for o in options]
    options_ok = len(options) > 0
    check(
        "E get_options()",
        options_ok,
        f"{len(options)} options: {option_values}",
    )
else:
    check("E get_options()", False, "no instance")

# ─────────────────────────────────────────────────────────────────────────────
#  F — validate()
# ─────────────────────────────────────────────────────────────────────────────
if instance:
    valid_result   = instance.validate(VALID_VALUE)
    invalid_result = instance.validate(INVALID_VALUE)
    none_result    = instance.validate(None)  # required=False → should pass

    validate_ok = valid_result and not invalid_result and none_result
    check(
        "F validate()",
        validate_ok,
        f"{VALID_VALUE!r}→{valid_result}  "
        f"{INVALID_VALUE!r}→{invalid_result}  "
        f"None→{none_result}",
    )
else:
    check("F validate()", False, "no instance")

# ─────────────────────────────────────────────────────────────────────────────
#  G — get_default()
# ─────────────────────────────────────────────────────────────────────────────
if instance:
    default = instance.get_default()
    default_ok = default == DEFAULT_VALUE
    check(
        "G get_default()",
        default_ok,
        f"returned {default!r}  expected {DEFAULT_VALUE!r}",
    )
else:
    check("G get_default()", False, "no instance")

# ─────────────────────────────────────────────────────────────────────────────
#  H — to_sql_clause()
# ─────────────────────────────────────────────────────────────────────────────
if instance:
    result = instance.to_sql_clause(SQL_VALUE)
    sql_ok = (
        result is not None
        and isinstance(result, tuple)
        and len(result) == 2
        and PARAM_NAME in result[0]
        and result[1].get(PARAM_NAME) == SQL_VALUE
    )
    check(
        "H to_sql_clause()",
        sql_ok,
        f"fragment={result[0]!r}  params={result[1]}" if result else "returned None",
    )
    # None value → should return None (no WHERE clause contribution)
    null_result = instance.to_sql_clause(None)
    check(
        "H to_sql_clause(None)",
        null_result is None,
        f"returned {null_result!r}",
    )
else:
    check("H to_sql_clause()", False, "no instance")
    check("H to_sql_clause(None)", False, "no instance")

# ─────────────────────────────────────────────────────────────────────────────
#  I — to_dict()
# ─────────────────────────────────────────────────────────────────────────────
if instance:
    serialized = instance.to_dict()
    dict_ok = (
        isinstance(serialized, dict)
        and serialized.get("param_name") == PARAM_NAME
        and serialized.get("filter_type") == FILTER_TYPE
        and isinstance(serialized.get("options"), list)
        and len(serialized["options"]) > 0
        and "value" in serialized["options"][0]
        and "label" in serialized["options"][0]
    )
    check(
        "I to_dict()",
        dict_ok,
        f"keys={list(serialized.keys())}  "
        f"options[0]={serialized['options'][0] if serialized.get('options') else 'n/a'}",
    )
else:
    check("I to_dict()", False, "no instance")

# ─────────────────────────────────────────────────────────────────────────────
#  Summary
# ─────────────────────────────────────────────────────────────────────────────
print()
passed = sum(results)
total = len(results)
if all(results):
    print(f"{'ALL STEPS PASSED':^60}")
else:
    print(f"  {passed}/{total} steps passed — see {FAIL} above for details")
print(f"{'='*60}\n")
