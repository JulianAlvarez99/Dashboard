"""
Number Filter - Numeric input
"""

from typing import Any, Union

from app.services.filters.base import InputFilter


class NumberFilter(InputFilter):
    """
    Numeric input filter.
    Supports integers and floats with min/max validation.
    """
    
    def validate_value(self, value: Any) -> bool:
        """Validate numeric value"""
        if not super().validate_value(value):
            return False
        
        if value is None:
            return not self.config.required
        
        if not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (ValueError, TypeError):
                return False
        
        # Check min/max if configured
        ui_config = self.config.ui_config or {}
        min_val = ui_config.get("min")
        max_val = ui_config.get("max")
        
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        
        return True
    
    def get_default_value(self) -> Union[int, float, None]:
        """Get default numeric value"""
        return self.config.default_value or 0
