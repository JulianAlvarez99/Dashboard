"""
Toggle Filter - Boolean on/off switch
"""

from typing import Any

from app.services.filters.base import InputFilter


class ToggleFilter(InputFilter):
    """
    Boolean toggle filter.
    Simple on/off switch for binary options.
    """
    
    def validate_value(self, value: Any) -> bool:
        """Validate boolean value"""
        if value is None:
            return not self.config.required
        
        return isinstance(value, bool)
    
    def get_default_value(self) -> bool:
        """Get default toggle value"""
        return self.config.default_value if self.config.default_value is not None else False
