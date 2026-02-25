import asyncio
from app.core.cache import metadata_cache
from app.core.database import db_manager

async def check():
    await metadata_cache.load_all()
    areas = metadata_cache.get_areas()
    types = set(a['area_type'] for a in areas.values())
    print(f"Area types in DB: {types}")
    for a in areas.values():
        print(f"  {a['area_id']}: {a['area_name']} (type={a['area_type']}) line={a['line_id']}")

asyncio.run(check())
