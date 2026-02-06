"""
Dropdown Filter - Single selection from options
"""

from typing import Dict, List, Any, Optional

from app.services.filters.base import OptionsFilter, FilterOption, FilterConfig
from app.core.cache import metadata_cache


class DropdownFilter(OptionsFilter):
    """
    Single-select dropdown filter.
    Can load options from cache or use static options.
    """
    
    def _load_options(self, parent_values: Optional[Dict[str, Any]] = None) -> List[FilterOption]:
        """Load options based on options_source"""
        
        # Static options
        if self.config.static_options:
            return [
                FilterOption(
                    value=opt["value"],
                    label=opt["label"],
                    extra=opt.get("extra")
                )
                for opt in self.config.static_options
            ]
        
        # Dynamic options from cache
        source = self.config.options_source
        if not source:
            return []
        
        if source == "production_line":
            return self._load_production_lines()
        elif source == "area":
            return self._load_areas(parent_values)
        elif source == "product":
            return self._load_products()
        elif source == "shift":
            return self._load_shifts()
        
        return []
    
    def _load_production_lines(self) -> List[FilterOption]:
        """Load production line options"""
        lines = metadata_cache.get_production_lines()
        return [
            FilterOption(
                value=line_id,
                label=data["line_name"],
                extra={
                    "line_code": data["line_code"],
                    "downtime_threshold": data.get("downtime_threshold")
                }
            )
            for line_id, data in lines.items()
        ]
    
    def _load_areas(self, parent_values: Optional[Dict[str, Any]] = None) -> List[FilterOption]:
        """Load area options, filtered by line_id if available"""
        areas = metadata_cache.get_areas()
        
        # Filter by parent line_id if dependency exists
        if self.config.depends_on == "line_id" and parent_values:
            line_id = parent_values.get("line_id")
            if line_id:
                areas = {
                    aid: data for aid, data in areas.items()
                    if data["line_id"] == line_id
                }
        
        return [
            FilterOption(
                value=area_id,
                label=data["area_name"],
                extra={
                    "area_type": data["area_type"],
                    "line_id": data["line_id"]
                }
            )
            for area_id, data in areas.items()
        ]
    
    def _load_products(self) -> List[FilterOption]:
        """Load product options"""
        products = metadata_cache.get_products()
        return [
            FilterOption(
                value=product_id,
                label=data["product_name"],
                extra={
                    "product_code": data["product_code"],
                    "product_weight": float(data["product_weight"]),
                    "product_color": data["product_color"]
                }
            )
            for product_id, data in products.items()
        ]
    
    def _load_shifts(self) -> List[FilterOption]:
        """Load shift options"""
        shifts = metadata_cache.get_shifts()
        return [
            FilterOption(
                value=shift_id,
                label=data["shift_name"],
                extra={
                    "start_time": str(data["start_time"]),
                    "end_time": str(data["end_time"]),
                    "is_overnight": data["is_overnight"]
                }
            )
            for shift_id, data in shifts.items()
        ]
