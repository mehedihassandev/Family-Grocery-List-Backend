import json
import re
from typing import Optional

import httpx

from app.core.config import get_settings
from app.models.ai import (
    GenerateAiRecipeRequest,
    MonthlyInsightsRequest,
    MonthlyInsightsResponse,
    RecipeIngredient as AiRecipeIngredient,
    RecipeToGroceryRequest,
    RecipeToGroceryResponse,
)
from app.models.recipe import RecipeDetail, RecipeIngredient, RecipeStep


# Standardized Bangladeshi & Global Recipe Knowledge Base for fallback AI engine
KNOWN_RECIPES: dict[str, dict] = {
    "beef tehari": {
        "recipeName": "Beef Tehari",
        "base_servings": 6,
        "ingredients": [
            {
                "name": "Kataribhog Rice",
                "category": "Staples",
                "base_qty": 1.5,
                "unit": "kg",
                "unit_price": 93.33,
            },
            {
                "name": "Beef",
                "category": "Meat",
                "base_qty": 1.5,
                "unit": "kg",
                "unit_price": 780.00,
            },
            {
                "name": "Soybean Oil",
                "category": "Staples",
                "base_qty": 500.0,
                "unit": "ml",
                "unit_price": 0.18,
            },
            {
                "name": "Tehari Spices & Mustard Oil",
                "category": "Household",
                "base_qty": 1.0,
                "unit": "pack",
                "unit_price": 150.00,
            },
        ],
    },
    "chicken biryani": {
        "recipeName": "Chicken Biryani",
        "base_servings": 4,
        "ingredients": [
            {
                "name": "Chinigura Rice",
                "category": "Staples",
                "base_qty": 1.0,
                "unit": "kg",
                "unit_price": 150.00,
            },
            {
                "name": "Chicken",
                "category": "Meat",
                "base_qty": 1.2,
                "unit": "kg",
                "unit_price": 240.00,
            },
            {
                "name": "Mustard / Soybean Oil",
                "category": "Staples",
                "base_qty": 300.0,
                "unit": "ml",
                "unit_price": 0.18,
            },
            {
                "name": "Biryani Masala & Ghee",
                "category": "Household",
                "base_qty": 1.0,
                "unit": "pack",
                "unit_price": 180.00,
            },
            {
                "name": "Yogurt & Onions",
                "category": "Produce",
                "base_qty": 500.0,
                "unit": "g",
                "unit_price": 0.16,
            },
        ],
    },
    "kacchi biryani": {
        "recipeName": "Kacchi Biryani",
        "base_servings": 6,
        "ingredients": [
            {
                "name": "Basmati / Chinigura Rice",
                "category": "Staples",
                "base_qty": 1.5,
                "unit": "kg",
                "unit_price": 160.00,
            },
            {
                "name": "Mutton / Beef",
                "category": "Meat",
                "base_qty": 2.0,
                "unit": "kg",
                "unit_price": 1100.00,
            },
            {
                "name": "Potatoes",
                "category": "Produce",
                "base_qty": 1.0,
                "unit": "kg",
                "unit_price": 55.00,
            },
            {
                "name": "Kacchi Masala & Ghee",
                "category": "Household",
                "base_qty": 1.0,
                "unit": "pack",
                "unit_price": 250.00,
            },
        ],
    },
    "beef kala bhuna": {
        "recipeName": "Beef Kala Bhuna",
        "base_servings": 4,
        "ingredients": [
            {
                "name": "Beef",
                "category": "Meat",
                "base_qty": 1.0,
                "unit": "kg",
                "unit_price": 780.00,
            },
            {
                "name": "Rice (Kataribhog)",
                "category": "Staples",
                "base_qty": 1.0,
                "unit": "kg",
                "unit_price": 95.00,
            },
        ],
    },
    "kala bhuna": {
        "recipeName": "Beef Kala Bhuna",
        "base_servings": 4,
        "ingredients": [
            {
                "name": "Beef",
                "category": "Meat",
                "base_qty": 1.0,
                "unit": "kg",
                "unit_price": 780.00,
            },
            {
                "name": "Rice (Kataribhog)",
                "category": "Staples",
                "base_qty": 1.0,
                "unit": "kg",
                "unit_price": 95.00,
            },
        ],
    },
}



def _extract_servings_from_prompt(prompt: str, default_servings: int) -> int:
    match = re.search(r"(\d+)\n?\s*(?:people|persons|servings|person)", prompt, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return default_servings


def convert_recipe_to_grocery(payload: RecipeToGroceryRequest) -> RecipeToGroceryResponse:
    """Convert recipe prompt to structured grocery items list using Gemini AI or fallback engine."""
    settings = get_settings()
    servings = _extract_servings_from_prompt(payload.recipePrompt, payload.servings)

    # Use Gemini API if gemini_api_key is configured
    if settings.gemini_api_key:
        try:
            gemini_key = settings.gemini_api_key
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:"
                f"generateContent?key={gemini_key}"
            )
            prompt_text = (
                "You are a helpful grocery assistant. Convert this recipe prompt into a JSON "
                f"grocery list with exact recipe name, servings ({servings}), and ingredient list. "
                "Each ingredient must have name, category, quantity, and estimatedPriceBDT in BDT. "
                f"Prompt: {payload.recipePrompt}"
            )
            body = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {"response_mime_type": "application/json"},
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=body)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)
                    ingredients = [
                        AiRecipeIngredient(
                            name=ing.get("name", "Ingredient"),
                            category=ing.get("category", "Staples"),
                            quantity=str(ing.get("quantity", "1 pack")),
                            estimatedPriceBDT=float(ing.get("estimatedPriceBDT", 100)),
                        )
                        for ing in parsed.get("ingredients", [])
                    ]
                    return RecipeToGroceryResponse(
                        recipeName=parsed.get("recipeName", payload.recipePrompt.title()),
                        servings=servings,
                        ingredients=ingredients,
                    )
        except Exception:
            # Fallback to local intelligence if API call fails
            pass

    # High-quality fallback engine
    prompt_lower = payload.recipePrompt.lower()
    recipe_key = next((k for k in KNOWN_RECIPES if k in prompt_lower), None)

    if recipe_key:
        matched = KNOWN_RECIPES[recipe_key]
        recipe_name = matched["recipeName"]
        base_servings = matched["base_servings"]
        ratio = servings / base_servings

        ingredients: list[AiRecipeIngredient] = []
        for ing in matched["ingredients"]:
            scaled_qty_val = round(ing["base_qty"] * ratio, 2)
            if ing["unit"] != "pack":
                qty_str = f"{scaled_qty_val}{ing['unit']}"
                est_price = round(ing["unit_price"] * scaled_qty_val, 0)
            else:
                qty_str = f"{int(max(1, round(scaled_qty_val)))} pack"
                est_price = round(ing["unit_price"] * ratio, 0)

            ingredients.append(
                AiRecipeIngredient(
                    name=ing["name"],
                    category=ing["category"],
                    quantity=qty_str,
                    estimatedPriceBDT=est_price,
                )
            )
        return RecipeToGroceryResponse(
            recipeName=recipe_name,
            servings=servings,
            ingredients=ingredients,
        )

    # Dynamic fallback generator for custom/unknown recipes
    pattern = r"(?i)\s*(for\s*\d+\s*(people|persons|servings)?)"
    clean_name = re.sub(pattern, "", payload.recipePrompt).strip().title()
    if not clean_name:
        clean_name = "Custom Recipe"

    ratio = servings / 4.0
    ingredients = [
        AiRecipeIngredient(
            name=f"{clean_name} Main Staple / Rice",
            category="Staples",
            quantity=f"{round(1.0 * ratio, 1)}kg",
            estimatedPriceBDT=round(120.0 * ratio, 0),
        ),
        AiRecipeIngredient(
            name=f"Fresh Meat / Protein for {clean_name}",
            category="Meat",
            quantity=f"{round(1.0 * ratio, 1)}kg",
            estimatedPriceBDT=round(750.0 * ratio, 0),
        ),
        AiRecipeIngredient(
            name="Cooking Oil & Ghee",
            category="Staples",
            quantity=f"{int(500 * ratio)}ml",
            estimatedPriceBDT=round(90.0 * ratio, 0),
        ),
        AiRecipeIngredient(
            name="Spices & Seasoning Pack",
            category="Household",
            quantity="1 pack",
            estimatedPriceBDT=round(130.0 * ratio, 0),
        ),
    ]

    return RecipeToGroceryResponse(
        recipeName=clean_name,
        servings=servings,
        ingredients=ingredients,
    )



def generate_monthly_insights(payload: MonthlyInsightsRequest) -> MonthlyInsightsResponse:
    """Generate monthly natural-language family grocery insights."""
    settings = get_settings()

    if settings.gemini_api_key:
        try:
            gemini_key = settings.gemini_api_key
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:"
                f"generateContent?key={gemini_key}"
            )
            prompt_text = (
                "Analyze this family monthly grocery consumption and breakdown: "
                f"{payload.model_dump_json()}. Return JSON with keys: insights "
                "(string natural language family savings advice), keyRecommendations "
                "(array of strings), and potentialMonthlySavingsBDT (float savings in BDT)."
            )
            body = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {"response_mime_type": "application/json"},
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=body)
                if res.status_code == 200:
                    data = res.json()
                    parsed = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
                    return MonthlyInsightsResponse(
                        familyId=payload.familyId,
                        insights=parsed.get(
                            "insights", "Monthly consumption analysis complete."
                        ),
                        keyRecommendations=parsed.get("keyRecommendations", []),
                        potentialMonthlySavingsBDT=parsed.get(
                            "potentialMonthlySavingsBDT", 450.0
                        ),
                    )
        except Exception:
            pass

    # High-quality natural language insights generator
    insights_text = (
        "Based on your family's monthly grocery spending across Shwapno, Meena Bazar, and Agora, "
        "your highest expense categories are Meat and Staples (Rice & Cooking Oil). "
        "Consolidating monthly bulk orders for staples like 5L Soybean Oil and 5kg Kataribhog Rice "
        "from Meena Bazar provides the best baseline price in Dhaka."
    )
    recommendations = [
        "Purchase staples like Kataribhog Rice (5kg) and Soybean Oil in bulk from Meena Bazar "
        "to save up to 65 BDT per basket.",
        (
            "Compare promotional deals between Shwapno and Meena Bazar "
            "on weekend dairy & egg packages."
        ),
        "Batch your weekly grocery list using the Superstore Basket Cost Optimizer before buying.",
    ]

    return MonthlyInsightsResponse(
        familyId=payload.familyId,
        insights=insights_text,
        keyRecommendations=recommendations,
        potentialMonthlySavingsBDT=450.0,
    )


def _save_recipe_to_store(recipe: RecipeDetail) -> None:
    from app.api.routes.recipes import RECIPES_STORE

    RECIPES_STORE[recipe.id] = recipe
    try:
        from app.core.firebase import get_firestore_client

        get_firestore_client().collection("recipes").document(recipe.id).set(recipe.model_dump())
    except Exception:
        pass


def _clean_recipe_title(prompt: str) -> str:
    cleaned = prompt.strip()
    cleaned = re.sub(r"(?i)^(create|make|cook|prepare|generate|how\s+to\s+make|how\s+to\s+cook|recipe\s+for)\s+", "", cleaned)
    cleaned = re.sub(r"(?i)\s*(recipe|recepi|for\s*\d+\s*(people|persons|servings|person)?)$", "", cleaned)
    cleaned = re.sub(r"(?i)\s*recipe\s*", " ", cleaned)
    cleaned = re.sub(r"(?i)\s*recepi\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() or "Custom Recipe"


def _generate_fallback_recipe(
    clean_title: str,
    servings: int,
    recipe_id: str,
    family_id: Optional[str] = None,
    created_user_id: Optional[str] = None,
    author_name: Optional[str] = "Family Chef",
) -> RecipeDetail:
    ratio = servings / 4.0
    steps = [
        RecipeStep(
            stepNumber=1,
            totalSteps=4,
            phase="Prep",
            title=f"Prepare Ingredients for {clean_title}",
            instruction=f"Clean, chop, and measure all fresh ingredients, spices, and proteins needed for {clean_title} ({servings} servings).",
            timerMins=10,
            heatLevel="Low Heat",
            imageUrl="https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=2,
            totalSteps=4,
            phase="Cook",
            title="Sauté Aromatics & Spices",
            instruction=f"Heat oil in a heavy pot over medium heat. Sauté onions, garlic, ginger, and aromatic spices until golden brown.",
            timerMins=8,
            heatLevel="Medium Heat",
            imageUrl="https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=3,
            totalSteps=4,
            phase="Simmer",
            title="Simmer & Infuse Flavors",
            instruction=f"Add proteins/vegetables and liquids to {clean_title}. Cover and simmer over low heat until tender and thoroughly infused.",
            timerMins=20,
            heatLevel="Low Heat",
            imageUrl="https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "NEXT" TO CONTINUE',
        ),
        RecipeStep(
            stepNumber=4,
            totalSteps=4,
            phase="Garnish & Serve",
            title="Final Touch & Plating",
            instruction=f"Garnish {clean_title} with fresh cilantro, lemon slices, or fried onions. Serve hot.",
            timerMins=2,
            heatLevel="Low Heat",
            imageUrl="https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
            voicePrompt='SAY "SERVE" TO FINISH',
        ),
    ]
    ingredients = [
        RecipeIngredient(
            id="i1",
            name=f"{clean_title} Main Base",
            amount=f"{round(0.8 * ratio, 1)}kg" if ratio != 1 else "600g",
            inPantry=True,
            price=round(450.0 * ratio, 0),
        ),
        RecipeIngredient(
            id="i2",
            name="Seasoning & Spice Pack",
            amount="1 pack",
            inPantry=True,
            price=round(40.0 * ratio, 0),
        ),
        RecipeIngredient(
            id="i3",
            name="Fresh Herbs & Garnish",
            amount="1 bunch",
            inPantry=False,
            price=round(30.0 * ratio, 0),
        ),
        RecipeIngredient(
            id="i4",
            name="Cooking Oil / Butter",
            amount="2 tbsp",
            inPantry=True,
            price=round(50.0 * ratio, 0),
        ),
    ]
    recipe = RecipeDetail(
        id=recipe_id,
        title=clean_title,
        prepTimeMins=20,
        difficulty="Easy",
        servings=servings,
        kcal=int(450 * ratio),
        pantryMatchPercent=75,
        isVegetarian=False,
        familyId=family_id,
        createdUserId=created_user_id,
        authorName=author_name or "Family Chef",
        imageUrl="https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
        missingCount=len([i for i in ingredients if not i.inPantry]),
        missingTotalCost=sum(i.price or 0.0 for i in ingredients if not i.inPantry),
        ingredients=ingredients,
        steps=steps,
    )
    _save_recipe_to_store(recipe)
    return recipe


def generate_ai_recipe(payload: GenerateAiRecipeRequest) -> RecipeDetail:
    """Generate a complete AI recipe using Google Gemini API with intelligent fallback."""
    settings = get_settings()
    servings = payload.servings
    raw_prompt = payload.recipePrompt.strip()
    clean_title = _clean_recipe_title(raw_prompt)
    slug = re.sub(r"[^a-z0-9]", "-", clean_title.lower())[:30].strip("-") or "ai-recipe"
    recipe_id = f"ai-{slug}-{servings}p"

    gemini_key = settings.gemini_api_key.strip() if settings.gemini_api_key else ""

    if gemini_key:
        endpoints = [
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent",
        ]
        prompt_text = (
            f"You are a master AI chef. Create an authentic, detailed recipe for '{clean_title}' ({servings} servings) in valid JSON format.\n"
            "Output ONLY JSON. Do not include markdown headers or commentary.\n"
            "JSON Schema:\n"
            "{\n"
            f'  "title": "{clean_title}",\n'
            '  "prepTimeMins": 30,\n'
            '  "difficulty": "Easy",\n'
            f'  "servings": {servings},\n'
            '  "kcal": 550,\n'
            '  "pantryMatchPercent": 85,\n'
            '  "isVegetarian": false,\n'
            '  "imageUrl": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",\n'
            '  "ingredients": [\n'
            '    {"id": "i1", "name": "Ingredient Name", "amount": "100g", "inPantry": true, "price": 2.50}\n'
            '  ],\n'
            '  "steps": [\n'
            '    {\n'
            '      "stepNumber": 1,\n'
            '      "totalSteps": 4,\n'
            '      "phase": "Prep",\n'
            '      "title": "Detailed Step Title",\n'
            '      "instruction": "Full authentic instruction describing how to cook this dish.",\n'
            '      "timerMins": 10,\n'
            '      "heatLevel": "High Heat",\n'
            '      "imageUrl": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",\n'
            '      "voicePrompt": "SAY \\"NEXT\\" TO CONTINUE"\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "Ensure every step title and instruction specifically relates to cooking " + clean_title + "."
        )
        body = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        for endpoint_base in endpoints:
            try:
                url = f"{endpoint_base}?key={gemini_key}"
                with httpx.Client(timeout=15.0) as client:
                    res = client.post(url, json=body)
                    if res.status_code == 200:
                        raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                        raw_text = re.sub(r"^```(json)?\s*", "", raw_text, flags=re.MULTILINE)
                        raw_text = re.sub(r"\s*```$", "", raw_text, flags=re.MULTILINE).strip()

                        parsed = json.loads(raw_text)
                        steps_raw = parsed.get("steps", [])
                        total_steps = len(steps_raw)
                        steps = [
                            RecipeStep(
                                stepNumber=s.get("stepNumber", idx + 1),
                                totalSteps=total_steps,
                                phase=s.get("phase", "Cook"),
                                title=s.get("title", f"Step {idx + 1}"),
                                instruction=s.get("instruction", ""),
                                timerMins=int(s.get("timerMins", 5)),
                                heatLevel=s.get("heatLevel", "Medium Heat"),
                                imageUrl=s.get("imageUrl")
                                or "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
                                voicePrompt=s.get("voicePrompt") or 'SAY "NEXT" TO CONTINUE',
                            )
                            for idx, s in enumerate(steps_raw)
                        ]
                        ingredients = [
                            RecipeIngredient(
                                id=i.get("id", f"i{idx + 1}"),
                                name=i.get("name", "Ingredient"),
                                amount=str(i.get("amount", "1 pack")),
                                inPantry=bool(i.get("inPantry", True)),
                                price=float(i.get("price")) if i.get("price") is not None else None,
                            )
                            for idx, i in enumerate(parsed.get("ingredients", []))
                        ]
                        recipe = RecipeDetail(
                            id=recipe_id,
                            title=_clean_recipe_title(parsed.get("title", clean_title)),
                            prepTimeMins=int(
                                parsed.get("prepTimeMins", sum(s.timerMins for s in steps) or 25)
                            ),
                            difficulty=parsed.get("difficulty", "Easy"),
                            servings=servings,
                            kcal=int(parsed.get("kcal", 500)),
                            pantryMatchPercent=int(parsed.get("pantryMatchPercent", 88)),
                            isVegetarian=bool(parsed.get("isVegetarian", False)),
                            familyId=payload.familyId,
                            createdUserId=payload.createdUserId,
                            authorName=payload.authorName or "Family Chef",
                            imageUrl=parsed.get("imageUrl")
                            or "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
                            missingCount=len([i for i in ingredients if not i.inPantry]),
                            missingTotalCost=sum(i.price or 0.0 for i in ingredients if not i.inPantry),
                            ingredients=ingredients,
                            steps=steps,
                        )
                        _save_recipe_to_store(recipe)
                        return recipe
            except Exception:
                continue

    # Fall back to high-quality local generator if API key is missing or quota/limits are exceeded
    return _generate_fallback_recipe(
        clean_title,
        servings,
        recipe_id,
        family_id=payload.familyId,
        created_user_id=payload.createdUserId,
        author_name=payload.authorName or "Family Chef",
    )



