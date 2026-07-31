from typing import Optional
from pydantic import BaseModel, Field


class RecipeIngredient(BaseModel):
    id: str
    name: str
    amount: str
    inPantry: bool = True
    price: Optional[float] = None


class RecipeStep(BaseModel):
    stepNumber: int
    totalSteps: int = 4
    phase: str = "Prep"
    title: str
    instruction: str
    timerMins: int = 10
    heatLevel: Optional[str] = "High Heat"
    imageUrl: Optional[str] = None
    voicePrompt: str = 'SAY "NEXT" TO CONTINUE'


class RecipeDetail(BaseModel):
    id: str = "creamy-garlic-pasta"
    title: str = "Creamy Garlic Pasta"
    prepTimeMins: int = 20
    difficulty: str = "Easy"
    servings: int = 4
    kcal: int = 420
    pantryMatchPercent: int = 92
    isVegetarian: bool = True
    imageUrl: str = "https://images.unsplash.com/photo-1621996346565-e3d5d6288590?w=800&auto=format&fit=crop&q=80"
    missingCount: int = 2
    missingTotalCost: float = 6.48
    ingredients: list[RecipeIngredient] = Field(default_factory=list)
    steps: list[RecipeStep] = Field(default_factory=list)


class RecipePackItem(BaseModel):
    name: str
    category: str = "Household"
    quantity: str = "1 pack"
    priority: str = "Medium"


class RecipePack(BaseModel):
    id: str
    title: str
    description: str
    icon: str = "🍝"
    tag: str = "Quick Dinner"
    color: str = "#047857"
    items: list[RecipePackItem] = Field(default_factory=list)

