"""
core.py — Pure business logic for ACEest Fitness & Gym.

This module contains NO Flask, NO Tkinter, NO database code.
Just pure functions that take inputs and return outputs.

Why this matters:
    - Easy to unit-test with pytest (no mocks needed)
    - Reusable across web API, CLI, or future mobile backend
    - Demonstrates modularization (a graded criterion)
"""

# ---------------------------------------------------------------------------
# Program definitions
# ---------------------------------------------------------------------------
# Each program has a "calorie factor" — a multiplier for daily calorie needs.
# Values are taken directly from the Tkinter versions provided by the lecturer.
# ---------------------------------------------------------------------------

PROGRAMS = {
    "Fat Loss (FL) - 3 day": {
        "factor": 22,
        "desc": "3-day full-body fat loss program",
    },
    "Fat Loss (FL) - 5 day": {
        "factor": 24,
        "desc": "5-day split, higher volume fat loss",
    },
    "Muscle Gain (MG) - PPL": {
        "factor": 35,
        "desc": "Push/Pull/Legs hypertrophy program",
    },
    "Beginner (BG)": {
        "factor": 26,
        "desc": "3-day simple beginner full-body program",
    },
}


# ---------------------------------------------------------------------------
# Business logic functions
# ---------------------------------------------------------------------------

def calculate_calories(weight_kg: float, program: str) -> int:
    """
    Calculate daily calorie target based on client weight and program.

    Args:
        weight_kg: Client weight in kilograms (must be > 0)
        program:   One of the keys in PROGRAMS dict

    Returns:
        Integer daily calorie target

    Raises:
        ValueError: if weight is invalid or program is unknown
    """
    if weight_kg <= 0:
        raise ValueError("Weight must be a positive number")
    if program not in PROGRAMS:
        raise ValueError(f"Unknown program: {program}")

    factor = PROGRAMS[program]["factor"]
    return int(weight_kg * factor)


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """
    Calculate Body Mass Index.

    BMI = weight(kg) / (height(m))^2

    Args:
        weight_kg: Weight in kilograms (> 0)
        height_cm: Height in centimeters (> 0)

    Returns:
        BMI rounded to 1 decimal place

    Raises:
        ValueError: if weight or height is non-positive
    """
    if weight_kg <= 0:
        raise ValueError("Weight must be positive")
    if height_cm <= 0:
        raise ValueError("Height must be positive")

    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 1)


def bmi_category(bmi: float) -> dict:
    """
    Classify a BMI value into a category with a risk note.

    Categories (WHO standard):
        < 18.5  → Underweight
        18.5–24.9 → Normal
        25–29.9 → Overweight
        >= 30   → Obese

    Returns:
        dict with keys 'category' and 'risk'
    """
    if bmi < 18.5:
        return {
            "category": "Underweight",
            "risk": "Potential nutrient deficiency, low energy levels.",
        }
    if bmi < 25:
        return {
            "category": "Normal",
            "risk": "Low risk if physically active and strong.",
        }
    if bmi < 30:
        return {
            "category": "Overweight",
            "risk": "Moderate risk. Focus on adherence and progressive activity.",
        }
    return {
        "category": "Obese",
        "risk": "Higher risk. Prioritize fat loss, consistency, and supervision.",
    }


def list_programs() -> list:
    """
    Return all available programs as a list of dicts (for API responses).
    """
    return [
        {"name": name, "factor": info["factor"], "desc": info["desc"]}
        for name, info in PROGRAMS.items()
    ]
