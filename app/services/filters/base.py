"""
Base classes and interfaces for filter system
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class FilterOption:
    """Single option for dropdown/multiselect filters"""
    value: Any
    label: str
    extra: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"value": self.value, "label": self.label}
        if self.extra:
            result["extra"] = self.extra
        return result


@dataclass
class FilterConfig:
    """Configuration for a filter"""
    filter_id: int
    filter_name: str
    param_name: str
    filter_type: str
    placeholder: Optional[str] = None
    default_value: Any = None
    required: bool = False
    options_source: Optional[str] = None
    static_options: Optional[List[Dict[str, Any]]] = None
    depends_on: Optional[str] = None
    ui_config: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filter_id": self.filter_id,
            "filter_name": self.filter_name,
            "param_name": self.param_name,
            "filter_type": self.filter_type,
            "placeholder": self.placeholder,
            "default_value": self.default_value,
            "required": self.required,
            "options_source": self.options_source,
            "static_options": self.static_options,
            "depends_on": self.depends_on,
            "ui_config": self.ui_config or {}
        }


class BaseFilter(ABC):
    """
    Abstract base class for all filter types.
    Each filter type implements its own logic for loading options.
    """
    
    def __init__(self, config: FilterConfig):
        self.config = config
    
    @abstractmethod
    def get_options(self, parent_values: Optional[Dict[str, Any]] = None) -> List[FilterOption]:
        """
        Get options for this filter.
        
        Args:
            parent_values: Values from parent filters for cascade filtering
            
        Returns:
            List of FilterOption
        """
        pass
    
    def validate_value(self, value: Any) -> bool:
        """
        Validate if a value is acceptable for this filter.
        
        Args:
            value: Value to validate
            
        Returns:
            True if valid, False otherwise
        """
        if self.config.required and value is None:
            return False
        return True
    
    def get_default_value(self) -> Any:
        """Get the default value for this filter"""
        return self.config.default_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert filter to dict for JSON response"""
        result = self.config.to_dict()
        result["options"] = [opt.to_dict() for opt in self.get_options()]
        return result


class OptionsFilter(BaseFilter):
    """
    Base class for filters that have options (dropdown, multiselect).
    Provides common functionality for option-based filters.
    """
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self._cached_options: Optional[List[FilterOption]] = None
    
    def get_options(self, parent_values: Optional[Dict[str, Any]] = None) -> List[FilterOption]:
        """
        Get options with caching support.
        Override _load_options in subclasses.
        """
        # If no parent values and already cached, return cache
        if parent_values is None and self._cached_options is not None:
            return self._cached_options
        
        options = self._load_options(parent_values)
        
        # Cache if no parent dependencies
        if parent_values is None:
            self._cached_options = options
        
        return options
    
    @abstractmethod
    def _load_options(self, parent_values: Optional[Dict[str, Any]] = None) -> List[FilterOption]:
        """
        Load options from data source.
        Subclasses must implement this.
        """
        pass
    
    def validate_value(self, value: Any) -> bool:
        """Validate that value exists in options"""
        if not super().validate_value(value):
            return False
        
        if value is None:
            return True
        
        options = self.get_options()
        valid_values = [opt.value for opt in options]
        
        if isinstance(value, list):
            return all(v in valid_values for v in value)
        
        return value in valid_values


class InputFilter(BaseFilter):
    """
    Base class for input-based filters (text, number, date).
    No options to load, just validation.
    """
    
    def get_options(self, parent_values: Optional[Dict[str, Any]] = None) -> List[FilterOption]:
        """Input filters don't have options"""
        return []
