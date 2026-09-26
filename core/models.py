"""
Pydantic models for type safety and validation.
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, validator


class Budget(BaseModel):
    """Budget configuration."""
    max_per_meal: float = 20.0
    currency: str = "USD"


class UserProfile(BaseModel):
    """User dietary profile and preferences."""
    name: str
    allergies: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    budget: Budget = Field(default_factory=lambda: Budget())
    location: Optional[Dict[str, float]] = None
    nutrition_targets: Optional[Dict[str, float]] = None

    @validator('allergies', 'dietary_restrictions', pre=True)
    def lowercase_lists(cls, v):
        """Normalize to lowercase for matching."""
        return [item.lower().strip() for item in v] if v else []


class Intent(BaseModel):
    """Extracted user intent from query."""
    is_restaurant_query: bool
    query_type: Literal["search", "filter", "question", "off_topic"]
    location: Optional[Dict[str, float]] = None  # lat, lng, radius
    cuisine: Optional[str] = None
    price_range: Optional[Dict[str, float]] = None  # min, max
    dietary_requirements: List[str] = Field(default_factory=list)
    nutrition_requirements: Dict[str, Any] = Field(default_factory=dict)
    meal_type: Optional[str] = None  # breakfast, lunch, dinner
    raw_query: str


class MenuItem(BaseModel):
    """Single menu item."""
    name: str
    price: Optional[str] = None
    price_float: Optional[float] = None
    description: Optional[str] = None
    section: Optional[str] = None
    currency: str = "USD"
    ingredients: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    nutrition: Optional[Dict[str, float]] = None  # protein, calories, etc.
    dietary_tags: List[str] = Field(default_factory=list)  # vegan, gluten-free, etc.

    @validator('price_float', pre=True, always=True)
    def extract_price(cls, v, values):
        """Extract float from price string."""
        if v is not None:
            return v
        price_str = values.get('price', '')
        if price_str:
            import re
            match = re.search(r'\d+\.?\d*', price_str.replace(',', ''))
            if match:
                return float(match.group(0))
        return None


class Restaurant(BaseModel):
    """Restaurant with menu."""
    id: str
    name: str
    url: str
    menu_url: Optional[str] = None
    menu_url_kind: Optional[str] = None
    location: Optional[Dict[str, float]] = None
    rating: Optional[float] = None
    price_level: Optional[str] = None
    menu_items: List[MenuItem] = Field(default_factory=list)
    menu_fetched: bool = False
    menu_cached: bool = False


class FilterResult(BaseModel):
    """Results after filtering."""
    restaurants: List[Restaurant]
    filtered_items: List[Dict[str, Any]]  # restaurant + matching items
    total_items_before: int
    total_items_after: int
    filters_applied: List[str]


class AgentResponse(BaseModel):
    """Final agent response."""
    success: bool
    message: str
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    cost: float = 0.0
    tokens_used: int = 0


class GuardrailResult(BaseModel):
    """Guardrail check result."""
    is_valid: bool
    reason: Optional[str] = None
    intent: Optional[Intent] = None
    cost: float = 0.0
