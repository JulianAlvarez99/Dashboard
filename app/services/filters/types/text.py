"""
Text Filter - Free text input
"""

from typing import Any

from app.services.filters.base import InputFilter


class TextFilter(InputFilter):
    """
    Free text input filter.
    Can be used for search, codes, names, etc.
    """
    
    def validate_value(self, value: Any) -> bool:
        """Validate text value"""
        if not super().validate_value(value):
            return False
        
        if value is None:
            return not self.config.required
        
        if not isinstance(value, str):
            return False
        
        # Check min/max length if configured
        ui_config = self.config.ui_config or {}
        min_length = ui_config.get("min_length", 0)
        max_length = ui_config.get("max_length", 1000)
        
        return min_length <= len(value) <= max_length
    
    def get_default_value(self) -> str:
        """Get default text value"""
        return self.config.default_value or ""
