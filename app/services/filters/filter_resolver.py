"""
FilterResolver - Resolves filter configurations and options
Refactored to use FilterFactory and specific filter type implementations
"""

from typing import Dict, List, Any, Optional

from app.core.cache import metadata_cache
from app.services.filters.base import FilterConfig
from app.services.filters.factory import FilterFactory


class FilterResolver:
    """
    Resolves filter configurations using FilterFactory.
    Simplified to delegate to specific filter type implementations.
    """
    
    @staticmethod
    def resolve_filter(
        filter_id: int,
        parent_values: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a single filter with its options.
        
        Args:
            filter_id: ID of the filter to resolve
            parent_values: Dict of parent filter values for cascades
        
        Returns:
            Filter dict or None if filter not found
        """
        filter_data = metadata_cache.get_filter(filter_id)
        if not filter_data:
            return None
        
        # Parse filter configuration
        config = FilterResolver._parse_filter_config(filter_data)
        
        # Create filter instance using factory
        filter_instance = FilterFactory.create(config)
        if not filter_instance:
            return None
        
        # Get options (with parent values for cascades)
        options = filter_instance.get_options(parent_values)
        
        # Build response dict
        result = config.to_dict()
        result["options"] = [opt.to_dict() for opt in options]
        result["display_order"] = filter_data["display_order"]
        result["description"] = filter_data["description"]
        
        return result
    
    @staticmethod
    def _parse_filter_config(filter_data: Dict[str, Any]) -> FilterConfig:
        """
        Parse filter data from cache into FilterConfig.
        
        Args:
            filter_data: Raw filter data from cache
            
        Returns:
            FilterConfig instance
        """
        additional = filter_data.get("additional_filter", {})
        
        return FilterConfig(
            filter_id=filter_data["filter_id"],
            filter_name=filter_data["filter_name"],
            param_name=additional.get("param_name", filter_data["filter_name"].lower().replace(" ", "_")),
            filter_type=additional.get("type", "text"),
            placeholder=additional.get("placeholder"),
            default_value=additional.get("default_value"),
            required=additional.get("required", False),
            options_source=additional.get("options_source"),
            static_options=additional.get("static_options"),
            depends_on=additional.get("depends_on"),
            ui_config=additional.get("ui_config")
        )
    
    @staticmethod
    def resolve_filters(
        filter_ids: List[int],
        parent_values: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Resolve multiple filters.
        
        Args:
            filter_ids: List of filter IDs to resolve
            parent_values: Dict of parent filter values for cascades
        
        Returns:
            List of filter dicts sorted by display_order
        """
        resolved = []
        for fid in filter_ids:
            config = FilterResolver.resolve_filter(fid, parent_values)
            if config:
                resolved.append(config)
        
        resolved.sort(key=lambda f: f["display_order"])
        return resolved
    
    @staticmethod
    def get_filter_options(
        filter_id: int,
        parent_values: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get just the options for a specific filter.
        Useful for HTMX cascade updates.
        
        Args:
            filter_id: Filter ID
            parent_values: Parent filter values
        
        Returns:
            List of option dicts
        """
        config = FilterResolver.resolve_filter(filter_id, parent_values)
        if config:
            return config.get("options", [])
        return []
    
    @staticmethod
    def get_production_line_options() -> List[Dict[str, Any]]:
        """Get all production line options directly"""
        lines = metadata_cache.get_production_lines()
        return [
            {
                "value": line_id,
                "label": data["line_name"],
                "line_code": data["line_code"],
                "downtime_threshold": data["downtime_threshold"]
            }
            for line_id, data in lines.items()
        ]

    @staticmethod
    def get_production_line_options_with_groups() -> List[Dict[str, Any]]:
        """
        Get production line options including line groups from filter additional_filter.
        
        Groups come from the filter table where the additional_filter JSON contains
        {"alias": "...", "line_ids": [...]}
        """
        lines = metadata_cache.get_production_lines()
        options: List[Dict[str, Any]] = []

        # First: add an "All lines" option
        all_ids = list(lines.keys())
        if len(all_ids) > 1:
            options.append({
                "value": f"all",
                "label": "Todas las líneas",
                "line_code": None,
                "downtime_threshold": None,
                "is_group": True,
                "line_ids": all_ids,
            })

        # Second: add line groups from filters' additional_filter
        filters = metadata_cache.get_filters()
        for fid, fdata in filters.items():
            af = fdata.get("additional_filter")
            if not af:
                continue
            # Parse JSON string if needed
            if isinstance(af, str):
                import json
                try:
                    af = json.loads(af)
                except Exception:
                    continue
            # Single group format: {"alias": "...", "line_ids": [...]}
            if isinstance(af, dict) and "alias" in af and "line_ids" in af:
                group_line_ids = af["line_ids"]
                options.append({
                    "value": f"group_{fid}",
                    "label": af["alias"],
                    "line_code": None,
                    "downtime_threshold": None,
                    "is_group": True,
                    "line_ids": group_line_ids,
                })
            # Multiple groups format: {"groups": [{"alias": "...", "line_ids": [...]}, ...]}
            elif isinstance(af, dict) and "groups" in af:
                for idx, grp in enumerate(af["groups"]):
                    if "alias" in grp and "line_ids" in grp:
                        options.append({
                            "value": f"group_{fid}_{idx}",
                            "label": grp["alias"],
                            "line_code": None,
                            "downtime_threshold": None,
                            "is_group": True,
                            "line_ids": grp["line_ids"],
                        })

        # Third: add individual lines
        for line_id, data in lines.items():
            options.append({
                "value": line_id,
                "label": data["line_name"],
                "line_code": data["line_code"],
                "downtime_threshold": data["downtime_threshold"],
                "is_group": False,
                "line_ids": None,
            })

        return options
    
    @staticmethod
    def get_areas_for_line(line_id: int) -> List[Dict[str, Any]]:
        """Get areas filtered by production line"""
        areas = metadata_cache.get_areas_by_line(line_id)
        return [
            {
                "value": area["area_id"],
                "label": area["area_name"],
                "area_type": area["area_type"]
            }
            for area in areas
        ]
    
    @staticmethod
    def get_product_options() -> List[Dict[str, Any]]:
        """Get all product options directly"""
        products = metadata_cache.get_products()
        return [
            {
                "value": product_id,
                "label": data["product_name"],
                "product_code": data["product_code"],
                "product_weight": float(data["product_weight"]),
                "product_color": data["product_color"]
            }
            for product_id, data in products.items()
        ]
    
    @staticmethod
    def get_shift_options() -> List[Dict[str, Any]]:
        """Get all shift options directly"""
        shifts = metadata_cache.get_shifts()
        return [
            {
                "value": shift_id,
                "label": data["shift_name"],
                "start_time": str(data["start_time"]),
                "end_time": str(data["end_time"]),
                "is_overnight": data["is_overnight"]
            }
            for shift_id, data in shifts.items()
        ]