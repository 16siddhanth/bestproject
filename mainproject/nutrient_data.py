"""
VeggieFeed — Nutrient Data & Matching Engine
=============================================

Peel nutrition values sourced from USDA FoodData Central (FDC).
Animal feed nutrient requirements sourced from:
  - Merck Veterinary Manual (merckvetmanual.com)
  - Alabama Cooperative Extension System (ACES)
  - NRC Nutrient Requirements of Domestic Animals series

All values are per 100 g unless stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Peel Nutrition (per 100 g, USDA FDC approximate) ──────────

PEEL_NUTRITION: Dict[str, Dict[str, float]] = {
    "Potato Skins": {
        "calories_kcal": 58.0,
        "protein_g": 2.57,
        "fat_g": 0.10,
        "fiber_g": 2.5,
        "calcium_mg": 30.0,
        "phosphorus_mg": 38.0,
        "moisture_pct": 83.3,
        "avg_peel_weight_g": 15.0,
    },
    "Onion Skins": {
        "calories_kcal": 40.0,
        "protein_g": 1.10,
        "fat_g": 0.10,
        "fiber_g": 1.7,
        "calcium_mg": 23.0,
        "phosphorus_mg": 29.0,
        "moisture_pct": 89.1,
        "avg_peel_weight_g": 5.0,
    },
    "Carrot Peels": {
        "calories_kcal": 41.0,
        "protein_g": 0.93,
        "fat_g": 0.24,
        "fiber_g": 2.8,
        "calcium_mg": 33.0,
        "phosphorus_mg": 35.0,
        "moisture_pct": 88.3,
        "avg_peel_weight_g": 8.0,
    },
    "Tomato Skins": {
        "calories_kcal": 18.0,
        "protein_g": 0.88,
        "fat_g": 0.20,
        "fiber_g": 1.2,
        "calcium_mg": 11.0,
        "phosphorus_mg": 24.0,
        "moisture_pct": 94.5,
        "avg_peel_weight_g": 10.0,
    },
    "Cucumber Peels": {
        "calories_kcal": 15.0,
        "protein_g": 0.65,
        "fat_g": 0.11,
        "fiber_g": 0.5,
        "calcium_mg": 16.0,
        "phosphorus_mg": 24.0,
        "moisture_pct": 95.2,
        "avg_peel_weight_g": 12.0,
    },
    "Brinjal Peels": {
        "calories_kcal": 25.0,
        "protein_g": 0.98,
        "fat_g": 0.18,
        "fiber_g": 3.0,
        "calcium_mg": 9.0,
        "phosphorus_mg": 24.0,
        "moisture_pct": 92.3,
        "avg_peel_weight_g": 10.0,
    },
    "Cabbage Leaves": {
        "calories_kcal": 25.0,
        "protein_g": 1.28,
        "fat_g": 0.10,
        "fiber_g": 2.5,
        "calcium_mg": 40.0,
        "phosphorus_mg": 26.0,
        "moisture_pct": 92.2,
        "avg_peel_weight_g": 20.0,
    },
    "Spinach": {
        "calories_kcal": 23.0,
        "protein_g": 2.86,
        "fat_g": 0.39,
        "fiber_g": 2.2,
        "calcium_mg": 99.0,
        "phosphorus_mg": 49.0,
        "moisture_pct": 91.4,
        "avg_peel_weight_g": 10.0,
    },
    "Bell Pepper Scraps": {
        "calories_kcal": 31.0,
        "protein_g": 0.99,
        "fat_g": 0.30,
        "fiber_g": 2.1,
        "calcium_mg": 7.0,
        "phosphorus_mg": 26.0,
        "moisture_pct": 92.2,
        "avg_peel_weight_g": 12.0,
    },
    "Lettuce": {
        "calories_kcal": 15.0,
        "protein_g": 1.36,
        "fat_g": 0.15,
        "fiber_g": 1.3,
        "calcium_mg": 36.0,
        "phosphorus_mg": 29.0,
        "moisture_pct": 94.9,
        "avg_peel_weight_g": 15.0,
    },
    "Broccoli Stems": {
        "calories_kcal": 34.0,
        "protein_g": 2.82,
        "fat_g": 0.37,
        "fiber_g": 2.6,
        "calcium_mg": 47.0,
        "phosphorus_mg": 66.0,
        "moisture_pct": 89.3,
        "avg_peel_weight_g": 25.0,
    },
    "Cauliflower Leaves": {
        "calories_kcal": 25.0,
        "protein_g": 1.92,
        "fat_g": 0.28,
        "fiber_g": 2.0,
        "calcium_mg": 22.0,
        "phosphorus_mg": 44.0,
        "moisture_pct": 92.1,
        "avg_peel_weight_g": 18.0,
    },
    "Celery": {
        "calories_kcal": 14.0,
        "protein_g": 0.69,
        "fat_g": 0.17,
        "fiber_g": 1.6,
        "calcium_mg": 40.0,
        "phosphorus_mg": 24.0,
        "moisture_pct": 95.4,
        "avg_peel_weight_g": 12.0,
    },
}

# Nutrient keys used for matching (excluding metadata like avg_peel_weight_g)
NUTRIENT_KEYS = [
    "calories_kcal",
    "protein_g",
    "fat_g",
    "fiber_g",
    "calcium_mg",
    "phosphorus_mg",
]

# ── Animal Feed Requirements (per 100 g of feed) ─────────────
# Sources:
#   Cattle — Merck Vet Manual, NRC Nutrient Requirements of Beef Cattle
#   Goats  — Merck Vet Manual, Langston University Goat Research
#   Poultry — Merck Vet Manual, NRC Nutrient Requirements of Poultry
#   Pigs   — Merck Vet Manual, NRC Nutrient Requirements of Swine, ACES

ANIMAL_PROFILES: Dict[str, Dict[str, Tuple[float, float]]] = {
    # (min, max) ideal range per 100 g feed
    "Cattle": {
        "calories_kcal": (250.0, 300.0),
        "protein_g": (12.0, 16.0),
        "fat_g": (3.0, 5.0),
        "fiber_g": (17.0, 25.0),
        "calcium_mg": (400.0, 800.0),
        "phosphorus_mg": (200.0, 500.0),
    },
    "Goats": {
        "calories_kcal": (250.0, 280.0),
        "protein_g": (14.0, 18.0),
        "fat_g": (3.0, 5.0),
        "fiber_g": (15.0, 22.0),
        "calcium_mg": (400.0, 600.0),
        "phosphorus_mg": (200.0, 400.0),
    },
    "Poultry": {
        "calories_kcal": (280.0, 320.0),
        "protein_g": (16.0, 22.0),
        "fat_g": (3.0, 8.0),
        "fiber_g": (3.0, 5.0),
        "calcium_mg": (800.0, 1200.0),
        "phosphorus_mg": (400.0, 600.0),
    },
    "Pigs": {
        "calories_kcal": (320.0, 360.0),
        "protein_g": (13.0, 18.0),
        "fat_g": (5.0, 10.0),
        "fiber_g": (5.0, 8.0),
        "calcium_mg": (500.0, 900.0),
        "phosphorus_mg": (400.0, 700.0),
    },
}

# Bin assignment: animal name → bin index
ANIMAL_TO_BIN: Dict[str, int] = {
    "Cattle": 0,
    "Goats": 1,
    "Poultry": 2,
    "Pigs": 3,
}

BIN_TO_ANIMAL: Dict[int, str] = {v: k for k, v in ANIMAL_TO_BIN.items()}

# Servo angles (degrees) for each bin
BIN_SERVO_ANGLES: Dict[int, float] = {
    0: 30.0,   # Cattle
    1: 70.0,   # Goats
    2: 110.0,  # Poultry
    3: 150.0,  # Pigs
}

# Nutrient importance weights for scoring
NUTRIENT_WEIGHTS: Dict[str, float] = {
    "calories_kcal": 1.0,
    "protein_g": 2.0,    # Protein is critical for all animals
    "fat_g": 1.0,
    "fiber_g": 1.5,      # Fiber matters more for ruminants
    "calcium_mg": 1.5,   # Ca:P ratio important
    "phosphorus_mg": 1.5,
}


# ── Bin State Tracking ────────────────────────────────────────

@dataclass
class BinState:
    """Tracks the nutrient accumulation and weight of a single bin."""
    animal: str
    bin_id: int
    total_weight_g: float = 0.0         # From MiniScale (actual)
    estimated_weight_g: float = 0.0     # From classification estimates
    peel_count: int = 0
    # Accumulated nutrients (absolute, not per 100g)
    nutrients: Dict[str, float] = field(default_factory=lambda: {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "calcium_mg": 0.0,
        "phosphorus_mg": 0.0,
    })

    def add_peel(self, peel_label: str, count: int = 1, actual_weight_g: Optional[float] = None):
        """Add a peel (or multiple) to this bin and update nutrient totals."""
        nutrition = PEEL_NUTRITION.get(peel_label)
        if not nutrition:
            return

        avg_weight = nutrition.get("avg_peel_weight_g", 10.0)
        weight = actual_weight_g if actual_weight_g is not None else (avg_weight * count)
        self.estimated_weight_g += weight
        self.peel_count += count

        # Scale nutrients from per-100g to actual weight
        scale = weight / 100.0
        for key in NUTRIENT_KEYS:
            self.nutrients[key] += nutrition.get(key, 0.0) * scale

    def update_actual_weight(self, scale_weight_g: float):
        """Update with actual weight from MiniScale."""
        self.total_weight_g = scale_weight_g

    def get_nutrient_profile_per_100g(self) -> Dict[str, float]:
        """Get current bin nutrient profile normalized to per 100g."""
        total = self.total_weight_g if self.total_weight_g > 0 else self.estimated_weight_g
        if total <= 0:
            return {k: 0.0 for k in NUTRIENT_KEYS}
        scale = 100.0 / total
        return {k: round(self.nutrients[k] * scale, 2) for k in NUTRIENT_KEYS}

    def to_dict(self) -> dict:
        """Serialize for API response."""
        profile = self.get_nutrient_profile_per_100g()
        target = ANIMAL_PROFILES.get(self.animal, {})
        return {
            "animal": self.animal,
            "bin_id": self.bin_id,
            "total_weight_g": round(self.total_weight_g, 1),
            "estimated_weight_g": round(self.estimated_weight_g, 1),
            "peel_count": self.peel_count,
            "nutrients_per_100g": profile,
            "target_ranges": {
                k: {"min": v[0], "max": v[1]}
                for k, v in target.items()
            },
        }


# ── Matching Algorithm ────────────────────────────────────────

def compute_suitability_score(
    peel_label: str,
    animal: str,
    current_bin_state: Optional[BinState] = None,
) -> float:
    """
    Compute suitability using Ratio Matching.
    Compares the 'shape' of the peel's nutrient profile to the animal's needs.
    """
    nutrition = PEEL_NUTRITION.get(peel_label)
    profile = ANIMAL_PROFILES.get(animal)
    if not nutrition or not profile:
        return 0.0

    # Calculate 'Nutrient Density' vector for the peel
    # We use a subset of core nutrients to define the 'type' of feed
    core_keys = ["protein_g", "fiber_g", "calcium_mg"]
    
    peel_vector = []
    animal_vector = []
    
    for key in core_keys:
        peel_val = nutrition.get(key, 0.0)
        low, high = profile.get(key, (1.0, 100.0))
        target_val = (low + high) / 2.0
        
        # Normalize by typical values to keep units comparable
        norm = 100.0 if "mg" in key else 10.0
        peel_vector.append(peel_val / norm)
        animal_vector.append(target_val / norm)

    # Calculate Dot Product / Magnitude (Cosine Similarity)
    dot = sum(p * a for p, a in zip(peel_vector, animal_vector))
    mag_p = sum(p**2 for p in peel_vector)**0.5
    mag_a = sum(a**2 for a in animal_vector)**0.5
    
    if mag_p == 0 or mag_a == 0:
        return 0.0
        
    similarity = dot / (mag_p * mag_a)
    score = similarity * 100.0

    # Adaptive bias: favor bins that are currently 'hungry' for this specific profile
    if current_bin_state and current_bin_state.peel_count > 0:
        # If bin is already getting too full, slightly penalize
        if current_bin_state.total_weight_g > 500:
            score *= 0.8
            
    return score


def find_optimal_bin(
    peel_labels: List[str],
    bin_states: Dict[int, BinState],
) -> int:
    """
    Find optimal bin using a combination of Ratio Matching and Load Balancing.
    If multiple animals are a good fit, favor the one with the least food.
    """
    scores = {}
    for bin_id, state in bin_states.items():
        animal = state.animal
        total_score = 0.0
        for label in peel_labels:
            total_score += compute_suitability_score(label, animal, state)
        scores[bin_id] = total_score / max(len(peel_labels), 1)

    # Sort bins by score (descending)
    sorted_bins = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_bins:
        return 0
        
    best_bin_id, best_score = sorted_bins[0]
    
    # Check if the second-best is close (within 5 points)
    # If so, pick the one between the two that has the lowest weight
    if len(sorted_bins) > 1:
        second_bin_id, second_score = sorted_bins[1]
        if (best_score - second_score) < 5.0:
            # They are very close matches! Load balance instead.
            w1 = bin_states[best_bin_id].total_weight_g
            w2 = bin_states[second_bin_id].total_weight_g
            if w2 < w1:
                return second_bin_id
                
    return best_bin_id


def create_initial_bin_states() -> Dict[int, BinState]:
    """Create fresh bin states for all 4 animals."""
    return {
        bin_id: BinState(animal=animal, bin_id=bin_id)
        for animal, bin_id in ANIMAL_TO_BIN.items()
    }


def get_estimated_weight(peel_label: str, count: int = 1) -> float:
    """Get estimated weight for a peel type (avg_peel_weight_g * count)."""
    nutrition = PEEL_NUTRITION.get(peel_label)
    if not nutrition:
        return 10.0 * count  # default fallback
    return nutrition.get("avg_peel_weight_g", 10.0) * count


def get_peel_nutrients_for_weight(peel_label: str, weight_g: float) -> Dict[str, float]:
    """Get scaled nutrient values for a given peel at a specific weight."""
    nutrition = PEEL_NUTRITION.get(peel_label, {})
    scale = weight_g / 100.0
    return {
        key: round(nutrition.get(key, 0.0) * scale, 3)
        for key in NUTRIENT_KEYS
    }
