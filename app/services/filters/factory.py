"""
Filter Factory - Creates filter instances based on type
"""

from typing import Optional, Dict, Any

from app.services.filters.base import BaseFilter, FilterConfig
from app.services.filters.types import (
    DateRangeFilter,
    DropdownFilter,
    MultiselectFilter,
    TextFilter,
    NumberFilter,
    ToggleFilter
)


class FilterFactory:
    """
    Factory for creating filter instances.
    Maps filter types to their implementation classes.
    """
    
    _filter_map = {
        "daterange": DateRangeFilter,
        "dropdown": DropdownFilter,
        "multiselect": MultiselectFilter,
        "text": TextFilter,
        "number": NumberFilter,
        "toggle": ToggleFilter,
        "checkbox": ToggleFilter,  # Alias for toggle
    }
    
    @classmethod
    def create(cls, config: FilterConfig) -> Optional[BaseFilter]:
        """
        Create a filter instance from configuration.
        
        Args:
            config: Filter configuration
            
        Returns:
            Filter instance or None if type not supported
        """
        filter_class = cls._filter_map.get(config.filter_type)
        if not filter_class:
            return None
        
        return filter_class(config)
    
    @classmethod
    def create_from_dict(cls, data: Dict[str, Any]) -> Optional[BaseFilter]:
        """
        Create a filter from a dictionary (e.g., from database).
        
        Args:
            data: Dictionary with filter configuration
            
        Returns:
            Filter instance or None
        """
        config = FilterConfig(
            filter_id=data["filter_id"],
            filter_name=data["filter_name"],
            param_name=data.get("param_name", data["filter_name"].lower().replace(" ", "_")),
            filter_type=data["filter_type"],
            placeholder=data.get("placeholder"),
            default_value=data.get("default_value"),
            required=data.get("required", False),
            options_source=data.get("options_source"),
            static_options=data.get("static_options"),
            depends_on=data.get("depends_on"),
            ui_config=data.get("ui_config")
        )
        
        return cls.create(config)
    
    @classmethod
    def register_filter_type(cls, filter_type: str, filter_class: type):
        """
        Register a new custom filter type.
        
        Args:
            filter_type: Type identifier
            filter_class: Class implementing BaseFilter
        """
        cls._filter_map[filter_type] = filter_class
    
    @classmethod
    def get_supported_types(cls) -> list:
        """Get list of supported filter types"""
        return list(cls._filter_map.keys())
