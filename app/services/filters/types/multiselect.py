"""
Multiselect Filter - Multiple selection from options
"""

from typing import Dict, List, Any, Optional

from app.services.filters.base import FilterOption, FilterConfig
from app.services.filters.types.dropdown import DropdownFilter


class MultiselectFilter(DropdownFilter):
    """
    Multi-select filter.
    Inherits option loading from DropdownFilter but allows multiple values.
    """
    
    def validate_value(self, value: Any) -> bool:
        """Validate that value is a list and all items are valid"""
        if not isinstance(value, list):
            return False
        
        if self.config.required and len(value) == 0:
            return False
        
        # Validate each item in the list
        options = self.get_options()
        valid_values = [opt.value for opt in options]
        
        return all(v in valid_values for v in value)
    
    def get_default_value(self) -> List[Any]:
        """Get default value as a list"""
        default = self.config.default_value
        if default is None:
            return []
        if isinstance(default, list):
            return default
        return [default]
