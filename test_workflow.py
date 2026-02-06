"""
Full workflow diagnostic test.
Tests every step from cache loading → layout config → filter options → dashboard data.
Run this with: python test_workflow.py
"""

import asyncio
import json
import sys
from datetime import datetime, date

# =============================================================================
# Step 0: Configuration
# =============================================================================

def test_step_0_config():
    """Test configuration loading"""
    print("=" * 70)
    print("STEP 0: Configuration")
    print("=" * 70)
    
    from app.core.config import settings
    
    print(f"  APP_NAME:       {settings.APP_NAME}")
    print(f"  DEBUG:          {settings.DEBUG}")
    print(f"  API_BASE_URL:   {settings.API_BASE_URL}")
    print(f"  FLASK_PORT:     {settings.FLASK_PORT}")
    print(f"  GLOBAL_DB_HOST: {settings.GLOBAL_DB_HOST}")
    print(f"  GLOBAL_DB_NAME: {settings.GLOBAL_DB_NAME}")
    print(f"  TENANT_DB_HOST: {settings.TENANT_DB_HOST}")
    print(f"  TENANT_DB_NAME: {settings.TENANT_DB_NAME}")
    print(f"  GLOBAL_DB_URL:  {settings.global_db_url[:50]}...")
    print(f"  TENANT_DB_URL:  {settings.tenant_db_url[:50]}...")
    
    # Verify critical settings
    issues = []
    if not settings.GLOBAL_DB_HOST:
        issues.append("GLOBAL_DB_HOST is empty")
    if not settings.GLOBAL_DB_NAME:
        issues.append("GLOBAL_DB_NAME is empty")
    if not settings.TENANT_DB_HOST:
        issues.append("TENANT_DB_HOST is empty")
    if not settings.TENANT_DB_NAME:
        issues.append("TENANT_DB_NAME is empty")
    
    if issues:
        print(f"\n  ❌ ISSUES: {', '.join(issues)}")
        return False
    
    print("\n  ✅ Configuration OK")
    return True


# =============================================================================
# Step 1: Database Connectivity
# =============================================================================

async def test_step_1_database():
    """Test raw database connectivity"""
    print("\n" + "=" * 70)
    print("STEP 1: Database Connectivity")
    print("=" * 70)
    
    from app.core.database import db_manager
    from sqlalchemy import text
    
    # Test global DB
    try:
        async with db_manager.get_global_session() as session:
            result = await session.execute(text("SELECT 1 AS test"))
            row = result.fetchone()
            print(f"  ✅ Global DB: Connected (test={row[0]})")
    except Exception as e:
        print(f"  ❌ Global DB: {e}")
        return False
    
    # Test tenant DB
    try:
        async with db_manager.get_tenant_session() as session:
            result = await session.execute(text("SELECT 1 AS test"))
            row = result.fetchone()
            print(f"  ✅ Tenant DB: Connected (test={row[0]})")
    except Exception as e:
        print(f"  ❌ Tenant DB: {e}")
        return False
    
    # Show tables in both DBs
    try:
        async with db_manager.get_global_session() as session:
            result = await session.execute(text("SHOW TABLES"))
            tables = [r[0] for r in result.fetchall()]
            print(f"  Global DB tables: {tables}")
    except Exception as e:
        print(f"  ⚠️ Could not list global tables: {e}")
    
    try:
        async with db_manager.get_tenant_session() as session:
            result = await session.execute(text("SHOW TABLES"))
            tables = [r[0] for r in result.fetchall()]
            print(f"  Tenant DB tables: {tables}")
    except Exception as e:
        print(f"  ⚠️ Could not list tenant tables: {e}")
    
    return True


# =============================================================================
# Step 2: Cache Loading
# =============================================================================

async def test_step_2_cache():
    """Test MetadataCache loading"""
    print("\n" + "=" * 70)
    print("STEP 2: MetadataCache Loading")
    print("=" * 70)
    
    from app.core.cache import metadata_cache
    
    # Clear and reload
    metadata_cache.clear()
    print(f"  Cache cleared. is_loaded={metadata_cache.is_loaded}")
    
    try:
        await metadata_cache.load_all()
        print(f"  ✅ Cache loaded. is_loaded={metadata_cache.is_loaded}")
    except Exception as e:
        print(f"  ❌ Cache load failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Inspect cache contents
    info = metadata_cache.get_cache_info()
    print(f"\n  Cache info:")
    for name, details in info.items():
        print(f"    {name}: count={details['count']}")
    
    # Production Lines
    lines = metadata_cache.get_production_lines()
    print(f"\n  Production Lines ({len(lines)}):")
    for lid, data in lines.items():
        print(f"    ID={lid}: {data['line_name']} (code={data['line_code']}, threshold={data.get('downtime_threshold', '?')})")
    
    # Areas
    areas = metadata_cache.get_areas()
    print(f"\n  Areas ({len(areas)}):")
    for aid, data in areas.items():
        print(f"    ID={aid}: {data['area_name']} (type={data['area_type']}, line_id={data['line_id']})")
    
    # Products
    products = metadata_cache.get_products()
    print(f"\n  Products ({len(products)}):")
    for pid, data in products.items():
        print(f"    ID={pid}: {data['product_name']} (code={data['product_code']}, weight={data['product_weight']}, std={data.get('production_std', '?')})")
    
    # Shifts
    shifts = metadata_cache.get_shifts()
    print(f"\n  Shifts ({len(shifts)}):")
    for sid, data in shifts.items():
        print(f"    ID={sid}: {data['shift_name']} (start={data['start_time']}, end={data['end_time']}, overnight={data.get('is_overnight', '?')})")
    
    # Filters
    filters = metadata_cache.get_filters()
    print(f"\n  Filters ({len(filters)}):")
    for fid, data in filters.items():
        print(f"    ID={fid}: {data['filter_name']} (order={data['display_order']}, additional={data.get('additional_filter', 'None')})")
    
    # Widget Catalog
    widgets = metadata_cache.get_widget_catalog()
    print(f"\n  Widget Catalog ({len(widgets)}):")
    for wid, data in widgets.items():
        print(f"    ID={wid}: {data['widget_name']} ({data.get('description', '')})")
    
    if not lines:
        print("\n  ⚠️ WARNING: No production lines in cache!")
    if not areas:
        print("  ⚠️ WARNING: No areas in cache!")
    if not products:
        print("  ⚠️ WARNING: No products in cache!")
    if not shifts:
        print("  ⚠️ WARNING: No shifts in cache!")
    if not filters:
        print("  ⚠️ WARNING: No filters in cache!")
    if not widgets:
        print("  ⚠️ WARNING: No widgets in widget catalog!")
    
    return True


# =============================================================================
# Step 3: Layout Configuration
# =============================================================================

async def test_step_3_layout():
    """Test layout config retrieval (what Flask calls via API)"""
    print("\n" + "=" * 70)
    print("STEP 3: Layout Configuration (Tenant=1, Role=ADMIN)")
    print("=" * 70)
    
    from app.core.database import db_manager
    from app.services.config.layout_service import LayoutService
    from app.core.cache import metadata_cache
    
    tenant_id = 1
    role = "ADMIN"
    
    async with db_manager.get_global_session() as session:
        # Test raw DB query
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT template_id, tenant_id, role_access, layout_config FROM dashboard_template WHERE tenant_id = :tid"),
            {"tid": tenant_id}
        )
        rows = result.mappings().all()
        print(f"  Raw dashboard_template rows for tenant {tenant_id}: {len(rows)}")
        for row in rows:
            print(f"    template_id={row['template_id']}, role={row['role_access']}")
            raw_config = row['layout_config']
            print(f"    layout_config type: {type(raw_config)}")
            if isinstance(raw_config, str):
                raw_config = json.loads(raw_config)
            print(f"    layout_config: {json.dumps(raw_config, indent=6, default=str)[:500]}")
    
    # Test via LayoutService
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, tenant_id, role)
        
        if layout is None:
            print(f"\n  ❌ No layout configuration for tenant={tenant_id}, role={role}")
            print("  This means Flask will get NO filters and NO widgets!")
            return False
        
        print(f"\n  LayoutConfig found:")
        print(f"    enabled_widget_ids: {layout.enabled_widget_ids}")
        print(f"    enabled_filter_ids: {layout.enabled_filter_ids}")
        print(f"    has_widgets: {layout.has_widgets}")
        print(f"    has_filters: {layout.has_filters}")
        
        # Resolve widgets
        resolved_widgets = LayoutService.resolve_widgets_from_cache(layout.enabled_widget_ids)
        print(f"\n  Resolved Widgets ({len(resolved_widgets)}):")
        for w in resolved_widgets:
            wd = w.to_dict()
            print(f"    {wd}")
        
        # Resolve filters  
        resolved_filters = LayoutService.resolve_filters_from_cache(layout.enabled_filter_ids)
        print(f"\n  Resolved Filters ({len(resolved_filters)}):")
        for f in resolved_filters:
            fd = f.to_dict()
            print(f"    id={fd['filter_id']}, name={fd['filter_name']}, type={fd['filter_type']}, param={fd['param_name']}, source={fd['options_source']}")
        
        if not resolved_widgets:
            print("\n  ⚠️ WARNING: No resolved widgets! Dashboard will show 'No widgets configured'")
        if not resolved_filters:
            print("  ⚠️ WARNING: No resolved filters! Dashboard will show no filter panel")
    
    return True


# =============================================================================
# Step 4: Filter Options (what JS calls)
# =============================================================================

async def test_step_4_filter_options():
    """Test filter options that Alpine.js fetches"""
    print("\n" + "=" * 70)
    print("STEP 4: Filter Options (what Alpine.js fetches from API)")
    print("=" * 70)
    
    from app.services.filters.filter_resolver import FilterResolver
    
    # Production lines
    line_opts = FilterResolver.get_production_line_options()
    print(f"\n  Production Line options ({len(line_opts)}):")
    for opt in line_opts:
        print(f"    value={opt['value']}, label={opt['label']}, code={opt['line_code']}")
    
    # Products
    product_opts = FilterResolver.get_product_options()
    print(f"\n  Product options ({len(product_opts)}):")
    for opt in product_opts:
        print(f"    value={opt['value']}, label={opt['label']}")
    
    # Shifts
    shift_opts = FilterResolver.get_shift_options()
    print(f"\n  Shift options ({len(shift_opts)}):")
    for opt in shift_opts:
        print(f"    value={opt['value']}, label={opt['label']}, start={opt['start_time']}, end={opt['end_time']}")
    
    if not line_opts:
        print("\n  ⚠️ No production line options — dropdowns will be empty!")
    if not product_opts:
        print("  ⚠️ No product options — multiselect will be empty!")
    if not shift_opts:
        print("  ⚠️ No shift options — shift dropdown will be empty!")
    
    return True


# =============================================================================
# Step 5: Simulate the full API layout call (what Flask route calls)
# =============================================================================

async def test_step_5_simulate_flask_api_call():
    """Simulate what Flask's dashboard route does internally"""
    print("\n" + "=" * 70)
    print("STEP 5: Simulate Flask → API Layout Call")
    print("=" * 70)
    
    from app.core.database import db_manager
    from app.services.config.layout_service import LayoutService
    
    tenant_id = 1
    role = "ADMIN"
    
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, tenant_id, role)
    
    if layout is None:
        print("  ❌ Layout is None — Flask would show error message, no filters, no widgets!")
        return False
    
    from app.services.config.layout_service import LayoutService as LS
    widgets = LS.resolve_widgets_from_cache(layout.enabled_widget_ids)
    filters = LS.resolve_filters_from_cache(layout.enabled_filter_ids)
    
    # Build the response as the API would
    api_response = {
        "tenant_id": layout.tenant_id,
        "role": layout.role,
        "widgets": [w.to_dict() for w in widgets],
        "filters": [f.to_dict() for f in filters],
        "raw_config": layout.raw_config
    }
    
    print(f"  API response keys: {list(api_response.keys())}")
    print(f"  Widgets count: {len(api_response['widgets'])}")
    print(f"  Filters count: {len(api_response['filters'])}")
    
    # This is what Flask extracts and passes to template
    flask_filters = api_response.get("filters", [])
    flask_widgets = api_response.get("widgets", [])
    
    print(f"\n  --- What Flask passes to template ---")
    print(f"  filters (len={len(flask_filters)}):")
    for f in flask_filters:
        print(f"    {json.dumps(f, default=str)[:200]}")
    print(f"  widgets (len={len(flask_widgets)}):")
    for w in flask_widgets:
        print(f"    {json.dumps(w, default=str)[:200]}")
    
    # Now check: the template checks {% if filters %} and {% if widgets %}
    # If filters is an empty list [], the template would NOT show the filter panel
    print(f"\n  Template condition 'if filters': {bool(flask_filters)}")
    print(f"  Template condition 'if widgets': {bool(flask_widgets)}")
    
    if not flask_filters:
        print("  ❌ PROBLEM: No filters → filter panel hidden → no 'Apply Filters' button!")
    if not flask_widgets:
        print("  ❌ PROBLEM: No widgets → widget grid hidden!")
    
    # Check filter structure is correct for the template
    print(f"\n  --- Filter structure check for Jinja2 template ---")
    for f in flask_filters:
        ft = f.get("filter_type")
        pn = f.get("param_name")
        os_val = f.get("options_source")
        so = f.get("static_options")
        dv = f.get("default_value")
        print(f"    [{ft}] param_name={pn}, options_source={os_val}, static_options={'Yes' if so else 'No'}, default={dv}")
        
        # Check for Jinja2 rendering path
        if ft == "daterange":
            print(f"      → Should render date inputs ✓")
        elif ft == "dropdown" and os_val and os_val != "static":
            print(f"      → Should render dynamic dropdown with options from '{os_val}' ✓")
        elif ft == "dropdown" and so:
            print(f"      → Should render static dropdown ✓")
        elif ft == "multiselect":
            print(f"      → Should render multiselect ✓")
        elif ft == "toggle":
            print(f"      → Should render toggle ✓")
        elif ft == "text":
            print(f"      → Should render text input ✓")
        elif ft == "number":
            print(f"      → Should render number input ✓")
        elif ft == "select_buttons" and so:
            print(f"      → Should render select buttons ✓")
        else:
            print(f"      → ⚠️ NO MATCHING TEMPLATE CONDITION!")
    
    return True


# =============================================================================
# Step 6: Test JS → API dashboard data call simulation
# =============================================================================

async def test_step_6_dashboard_data():
    """Simulate the POST /api/v1/dashboard/data call"""
    print("\n" + "=" * 70)
    print("STEP 6: Dashboard Data Pipeline Simulation")
    print("=" * 70)
    
    from app.core.database import db_manager
    from app.core.cache import metadata_cache
    from app.services.config.layout_service import LayoutService
    from app.services.dashboard_data_service import DashboardDataService
    from app.services.widgets.base import FilterParams
    
    # Get the widget IDs from layout config
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, 1, "ADMIN")
    
    if not layout or not layout.enabled_widget_ids:
        print("  ❌ No widgets configured — can't test data pipeline!")
        return False
    
    widget_ids = layout.enabled_widget_ids
    print(f"  Widget IDs to process: {widget_ids}")
    
    # Build params like the JS would send
    # Use date range that contains actual data (2026-01-28)
    params = FilterParams.from_dict({
        "start_date": "2026-01-28",
        "end_date": "2026-01-28",
        "start_time": "00:00",
        "end_time": "23:59",
        "interval": "hour"
    })
    
    print(f"  FilterParams: start={params.start_date}, end={params.end_date}")
    print(f"    start_time={params.start_time}, end_time={params.end_time}")
    print(f"    effective datetimes: {params.get_effective_datetimes()}")
    
    # Execute the data pipeline
    async with db_manager.get_tenant_session() as session:
        service = DashboardDataService(session)
        
        # Get line IDs
        line_ids = service.aggregator.get_line_ids_from_params(params)
        print(f"  Line IDs to query: {line_ids}")
        
        if not line_ids:
            print("  ⚠️ No line IDs — no queries will be made!")
        
        # Fetch data
        try:
            result = await service.get_dashboard_data(params, widget_ids)
            print(f"\n  ✅ Dashboard data pipeline completed!")
            print(f"  Response keys: {list(result.keys())}")
            print(f"  Metadata: {json.dumps(result.get('metadata', {}), default=str, indent=4)}")
            
            print(f"\n  Widget results:")
            for wid, wdata in result.get("widgets", {}).items():
                wtype = wdata.get("widget_type", "?")
                wname = wdata.get("widget_name", "?")
                has_data = wdata.get("data") is not None
                is_empty = wdata.get("metadata", {}).get("empty", False)
                print(f"    [{wid}] {wname} (type={wtype}, has_data={has_data}, empty={is_empty})")
                if has_data and wtype.startswith("kpi_"):
                    data = wdata["data"]
                    print(f"           value={data.get('value')}, unit={data.get('unit')}")
                    if wtype == "kpi_oee":
                        print(f"           availability={data.get('availability')}%, performance={data.get('performance')}%, quality={data.get('quality')}%")
                        print(f"           scheduled_min={data.get('scheduled_minutes')}, downtime_min={data.get('downtime_minutes')}")
        except Exception as e:
            print(f"\n  ❌ Dashboard data pipeline FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


# =============================================================================
# Step 7: Check template rendering context
# =============================================================================

async def test_step_7_template_context():
    """Verify the exact JSON that will be injected into Alpine.js"""
    print("\n" + "=" * 70)
    print("STEP 7: Template Context (what Alpine.js receives)")
    print("=" * 70)
    
    from app.core.database import db_manager
    from app.services.config.layout_service import LayoutService
    
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, 1, "ADMIN")
    
    if not layout:
        print("  ❌ No layout!")
        return False
    
    widgets = LayoutService.resolve_widgets_from_cache(layout.enabled_widget_ids)
    filters = LayoutService.resolve_filters_from_cache(layout.enabled_filter_ids)
    
    filters_json = [f.to_dict() for f in filters]
    widgets_json = [w.to_dict() for w in widgets]
    
    # This is what Jinja2 {{ filters | tojson }} would produce
    filters_tojson = json.dumps(filters_json, default=str)
    widgets_tojson = json.dumps(widgets_json, default=str)
    
    print(f"\n  filters | tojson (truncated):")
    print(f"    {filters_tojson[:500]}")
    print(f"\n  widgets | tojson (truncated):")
    print(f"    {widgets_tojson[:500]}")
    
    # Verify Alpine.js can parse this
    print(f"\n  --- Alpine.js dashboardApp() init check ---")
    print(f"  filterConfigs length: {len(filters_json)}")
    print(f"  widgetConfigs length: {len(widgets_json)}")
    
    # Check the init logic for filterValues
    print(f"\n  filterValues initialization:")
    for fc in filters_json:
        ft = fc.get("filter_type")
        pn = fc.get("param_name")
        dv = fc.get("default_value")
        
        if ft == "daterange":
            days_back = dv.get("days_back", 7) if isinstance(dv, dict) else 7
            print(f"    daterange → start_date/end_date set with days_back={days_back}")
        elif ft == "multiselect":
            print(f"    {pn} → array, default={dv}")
        elif ft == "toggle":
            print(f"    {pn} → boolean, default={dv}")
        else:
            print(f"    {pn} → '{dv}'")
    
    # Check applyFilters would build correct body
    print(f"\n  --- applyFilters() request body check ---")
    print(f"  widget_ids would be: {[w['widget_id'] for w in widgets_json]}")
    
    return True


# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("╔" + "═" * 68 + "╗")
    print("║         DASHBOARD WORKFLOW DIAGNOSTIC TEST                        ║")
    print("╚" + "═" * 68 + "╝")
    
    results = {}
    
    # Step 0: Config
    results["0_config"] = test_step_0_config()
    if not results["0_config"]:
        print("\n🛑 Configuration failed. Cannot continue.")
        return
    
    # Step 1: Database
    results["1_database"] = await test_step_1_database()
    if not results["1_database"]:
        print("\n🛑 Database connection failed. Cannot continue.")
        return
    
    # Step 2: Cache
    results["2_cache"] = await test_step_2_cache()
    if not results["2_cache"]:
        print("\n🛑 Cache loading failed. Cannot continue.")
        return
    
    # Step 3: Layout
    results["3_layout"] = await test_step_3_layout()
    
    # Step 4: Filter options
    results["4_filter_options"] = await test_step_4_filter_options()
    
    # Step 5: Simulate Flask → API
    results["5_flask_api"] = await test_step_5_simulate_flask_api_call()
    
    # Step 6: Dashboard data pipeline
    results["6_dashboard_data"] = await test_step_6_dashboard_data()
    
    # Step 7: Template context
    results["7_template_context"] = await test_step_7_template_context()
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {step}: {status}")
    
    all_passed = all(results.values())
    print(f"\n{'✅ All tests passed!' if all_passed else '❌ Some tests failed!'}")


if __name__ == "__main__":
    asyncio.run(main())
