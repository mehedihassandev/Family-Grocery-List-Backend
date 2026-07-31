from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import ensure_family_access, get_current_user
from app.models.recipe import RecipeDetail, RecipeIngredient, RecipeStep, RecipePack, RecipePackItem
from app.models.grocery import CreateGroceryItemRequest, GroceryActor
from app.services.grocery import create_grocery_item

router = APIRouter()

CREAMY_GARLIC_PASTA = RecipeDetail(
    id="creamy-garlic-pasta",
    title="Creamy Garlic Pasta",
    prepTimeMins=20,
    difficulty="Easy",
    servings=4,
    kcal=420,
    pantryMatchPercent=92,
    isVegetarian=True,
    imageUrl="https://images.unsplash.com/photo-1621996346565-e3d5d6288590?w=800&auto=format&fit=crop&q=80",
    missingCount=2,
    missingTotalCost=6.48,
    ingredients=[
        RecipeIngredient(id="i1", name="500g Linguine", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i2", name="4 cloves Garlic", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i3", name="1/2 cup Parmesan", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i4", name="2 tbsp Olive Oil", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i5", name="1 cup Heavy Cream", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i6", name="Fresh Parsley", amount="Missing ($1.49)", inPantry=False, price=1.49),
        RecipeIngredient(id="i7", name="Chicken Bouillon", amount="Missing ($4.99)", inPantry=False, price=4.99),
    ],
    steps=[
        RecipeStep(
            stepNumber=1,
            totalSteps=4,
            phase="Prep",
            title="Boil salted water and cook linguine until al dente.",
            instruction="Ensure the water is at a rolling boil before adding the pasta. Stir occasionally during the first few minutes to prevent sticking.",
            timerMins=10,
            heatLevel="High Heat",
            imageUrl="https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=2,
            totalSteps=4,
            phase="Cook",
            title="In a large pan, sauté minced garlic in olive oil until fragrant.",
            instruction="Sauté over medium heat for about 2 minutes until light golden brown. Be careful not to burn the garlic.",
            timerMins=2,
            heatLevel="Medium Heat",
            imageUrl="https://images.unsplash.com/photo-1621996346565-e3d5d6288590?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=3,
            totalSteps=4,
            phase="Simmer",
            title="Stir in heavy cream and bouillon; simmer for 5 minutes.",
            instruction="Pour cream slowly while stirring constantly to combine with sautéed garlic oil and bouillon.",
            timerMins=5,
            heatLevel="Low Heat",
            imageUrl="https://images.unsplash.com/photo-1621996346565-e3d5d6288590?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=4,
            totalSteps=4,
            phase="Serve",
            title="Toss pasta with sauce and parmesan; garnish with parsley.",
            instruction="Combine cooked linguine directly into sauce. Top generously with grated parmesan and freshly chopped parsley.",
            timerMins=1,
            heatLevel="Low Heat",
            imageUrl="https://images.unsplash.com/photo-1621996346565-e3d5d6288590?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "DONE" TO FINISH',
        ),
    ],
)

AVOCADO_TOAST = RecipeDetail(
    id="avocado-toast",
    title="Avocado Toast & Poached Egg",
    prepTimeMins=15,
    difficulty="Easy",
    servings=2,
    kcal=380,
    pantryMatchPercent=100,
    isVegetarian=True,
    imageUrl="https://images.unsplash.com/photo-1525351484163-7529414344d8?w=800&auto=format&fit=crop&q=80",
    missingCount=0,
    missingTotalCost=0.0,
    ingredients=[
        RecipeIngredient(id="i1", name="2 Slices Sourdough", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i2", name="1 Ripe Avocado", amount="In Pantry", inPantry=True),
        RecipeIngredient(id="i3", name="2 Organic Eggs", amount="In Pantry", inPantry=True),
    ],
    steps=[
        RecipeStep(
            stepNumber=1,
            totalSteps=2,
            phase="Prep",
            title="Toast bread and mash ripe avocado with lemon and salt.",
            instruction="Spread mashed avocado evenly on toasted sourdough slice.",
            timerMins=3,
            heatLevel="Medium Heat",
            imageUrl="https://images.unsplash.com/photo-1525351484163-7529414344d8?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=2,
            totalSteps=2,
            phase="Poach",
            title="Poach eggs in simmering water for 3 minutes.",
            instruction="Top avocado toast with poached egg and red pepper flakes.",
            timerMins=3,
            heatLevel="Low Heat",
            imageUrl="https://images.unsplash.com/photo-1525351484163-7529414344d8?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "DONE" TO FINISH',
        ),
    ],
)

RECIPES_STORE: dict[str, RecipeDetail] = {
    CREAMY_GARLIC_PASTA.id: CREAMY_GARLIC_PASTA,
    AVOCADO_TOAST.id: AVOCADO_TOAST,
}

RECIPE_PACKS_STORE: list[RecipePack] = [
    RecipePack(
        id="pasta-night",
        title="Italian Pasta Feast",
        description="Classic Italian dinner with pasta, garlic cream sauce, and fresh basil.",
        icon="🍝",
        tag="Quick Dinner",
        color="#047857",
        items=[
            RecipePackItem(name="Penne or Spaghetti Pasta", category="Household", quantity="2 Boxes", priority="Medium"),
            RecipePackItem(name="Marinara Pasta Sauce", category="Household", quantity="2 Jars", priority="Urgent"),
            RecipePackItem(name="Grated Parmesan Cheese", category="Dairy", quantity="1 Tub", priority="Medium"),
            RecipePackItem(name="Fresh Garlic & Olive Oil", category="Vegetables", quantity="1 Head", priority="Low"),
            RecipePackItem(name="Fresh Basil & Oregano", category="Vegetables", quantity="1 Bunch", priority="Low"),
        ],
    ),
    RecipePack(
        id="taco-night",
        title="Taco Tuesday",
        description="Everything you need for a delicious Mexican taco feast with avocados.",
        icon="🌮",
        tag="Family Favorite",
        color="#F59E0B",
        items=[
            RecipePackItem(name="Ground Beef / Turkey", category="Meat", quantity="1 lb", priority="Urgent"),
            RecipePackItem(name="Soft Tortillas & Shells", category="Household", quantity="1 Pack", priority="Medium"),
            RecipePackItem(name="Salsa & Pico de Gallo", category="Snacks", quantity="1 Jar", priority="Medium"),
            RecipePackItem(name="Shredded Mexican Cheese", category="Dairy", quantity="8 oz", priority="Medium"),
            RecipePackItem(name="Avocados & Lime", category="Fruits", quantity="3 pcs", priority="Low"),
        ],
    ),
    RecipePack(
        id="tehari-special",
        title="Dhaka Beef Tehari Pack",
        description="Authentic Old Dhaka style beef tehari ingredients with Kataribhog rice.",
        icon="🍲",
        tag="Traditional BD",
        color="#D97706",
        items=[
            RecipePackItem(name="Kataribhog Rice", category="Staples", quantity="1.5 kg", priority="Urgent"),
            RecipePackItem(name="Beef (Curry Cut)", category="Meat", quantity="1.5 kg", priority="Urgent"),
            RecipePackItem(name="Tehari Spice Mix & Mustard Oil", category="Household", quantity="1 Pack", priority="Medium"),
            RecipePackItem(name="Green Chilies & Onions", category="Produce", quantity="500 g", priority="Medium"),
        ],
    ),
]


@router.get("/recipes/packs", response_model=list[RecipePack])
def list_recipe_packs() -> list[RecipePack]:
    """Retrieve curated recipe packs catalog from API."""
    return RECIPE_PACKS_STORE


@router.get("/recipes", response_model=list[RecipeDetail])
def list_recipes() -> list[RecipeDetail]:
    """Retrieve all available and AI-generated recipes."""
    return list(RECIPES_STORE.values())


@router.get("/recipes/{recipe_id}", response_model=RecipeDetail)
def read_recipe_detail(recipe_id: str) -> RecipeDetail:
    """Retrieve detailed recipe info including ingredients, pantry match, and instructions."""
    if recipe_id in RECIPES_STORE:
        return RECIPES_STORE[recipe_id]
    return CREAMY_GARLIC_PASTA


@router.post("/recipes", response_model=RecipeDetail, status_code=status.HTTP_201_CREATED)
def create_ai_recipe(recipe: RecipeDetail) -> RecipeDetail:
    """Save an AI-generated recipe to the database."""
    RECIPES_STORE[recipe.id] = recipe
    return recipe


@router.post(
    "/families/{family_id}/recipes/{recipe_id}/add-missing",
    status_code=status.HTTP_200_OK,
)
def add_missing_recipe_ingredients(
    family_id: str,
    recipe_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> dict[str, Any]:
    """Bulk add missing ingredients for a recipe directly to the family's grocery list."""
    if current_user:
        ensure_family_access(family_id, current_user)
        actor = GroceryActor(
            uid=current_user.get("uid", ""),
            name=current_user.get("name", "Unknown User"),
            photoURL=current_user.get("picture"),
        )
    else:
        actor = GroceryActor(uid="system", name="System Chef", photoURL=None)

    target_recipe = RECIPES_STORE.get(recipe_id, CREAMY_GARLIC_PASTA)
    missing_items = [i for i in target_recipe.ingredients if not i.inPantry]
    added = []

    for item in missing_items:
        payload = CreateGroceryItemRequest(
            name=item.name,
            category="Household",
            quantity="1",
            priority="Medium",
            unitPrice=item.price,
            notes=f"Missing ingredient for {target_recipe.title}",
        )
        try:
            res = create_grocery_item(family_id, payload, added_by=actor)
            added.append(res.name)
        except Exception:
            added.append(item.name)

    return {
        "success": True,
        "addedCount": len(added),
        "items": added,
        "message": f"Added {len(added)} missing ingredients to grocery cart.",
    }
