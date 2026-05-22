"""
VeggieFeed — Nutrient Data & Matching Engine
=============================================

Peel nutrition values:
  Approximate compositions derived from USDA FoodData Central entries for
  the whole vegetable (e.g. FDC #170026 "Potatoes, russet, flesh and skin,
  raw"; FDC #169213 "Carrots, raw"; FDC #170000 "Onions, raw").
  USDA FDC does not publish separate entries for most peels/skins, so the
  values here are *estimates* based on the nearest whole-vegetable record,
  adjusted where published peel-specific literature exists.
  Fresh-weight values are converted to a dry-matter (DM) basis so that
  they are directly comparable with animal feed requirement tables.

Animal feed nutrient requirements:
  Expressed as % of dietary dry matter (DM) for protein, fat, fibre,
  calcium and phosphorus, and as kcal ME / kg DM for energy.
  Production classes assumed:
    Cattle  — Dairy, lactating adult   (NRC 2001, 7th rev.)
    Goats   — Adult maintenance        (NRC 2007; MSD Vet Manual)
    Poultry — Broiler, grower phase    (NRC 1994; MSD Vet Manual)
    Pigs    — Grower-finisher 50-80 kg (NRC 2012; MSD Vet Manual)

All nutrient values are per 100 g DM unless stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Tuple


# ── Helper: fresh → DM conversion ────────────────────────────
# The moisture percentage is a hardcoded static value sourced from USDA proxy data,
# which is then used to mathematically convert the fresh (as-fed) weight of the peel into its Dry Matter (DM) weight.
# Here is exactly how the calculation works in nutrient_data.py:
# 1. Calculate dm_frac = (100.0 - moisture_pct) / 100.0
# 2. Scale nutrients = fresh_val / dm_frac
# 3. Estimate DM weight = avg_fresh_weight * dm_frac

def _to_dm(fresh: Dict[str, float]) -> Dict[str, float]:
    """Convert a fresh-weight nutrient dict to dry-matter basis.

    Input keys (per 100 g fresh):
        calories_kcal, protein_g, fat_g, fiber_g,
        calcium_mg, phosphorus_mg, moisture_pct,
        avg_peel_weight_fresh_g

    Output keys (per 100 g DM):
        calories_kcal, protein_g, fat_g, fiber_g,
        calcium_mg, phosphorus_mg, moisture_pct,
        avg_peel_weight_dm_g          ← dry-matter weight of one peel
    """
    moisture = fresh["moisture_pct"]
    dm_frac = (100.0 - moisture) / 100.0  # e.g. 0.167 for potato
    scale = 1.0 / dm_frac  # multiply fresh value to get per-100g-DM

    return {
        "calories_kcal":  round(fresh["calories_kcal"] * scale, 1),
        "protein_g":      round(fresh["protein_g"]     * scale, 2),
        "fat_g":          round(fresh["fat_g"]         * scale, 2),
        "fiber_g":        round(fresh["fiber_g"]       * scale, 2),
        "calcium_mg":     round(fresh["calcium_mg"]    * scale, 1),
        "phosphorus_mg":  round(fresh["phosphorus_mg"] * scale, 1),
        "moisture_pct":   moisture,
        "dm_pct":         round(100.0 - moisture, 1),
        # Dry-matter weight of one average peel
        "avg_peel_weight_dm_g": round(
            fresh["avg_peel_weight_fresh_g"] * dm_frac, 2
        ),
        # Keep fresh weight for reference / display
        "avg_peel_weight_fresh_g": fresh["avg_peel_weight_fresh_g"],
    }


# ── Raw fresh-weight data (USDA FDC approximate proxies) ──────
# These are per 100 g as-fed (fresh).  Converted to DM below.

_FRESH: Dict[str, Dict[str, float]] = {
    # FDC proxy: #11369 Potatoes, skin only (microwaved, without salt)
    # Note: values match skin-only data, not the whole-vegetable #170026 entry.
    "Potato Skins": {
        "calories_kcal": 58.0, "protein_g": 2.57, "fat_g": 0.10,
        "fiber_g": 2.5, "calcium_mg": 30.0, "phosphorus_mg": 38.0,
        "moisture_pct": 83.3, "avg_peel_weight_fresh_g": 15.0,
    },
    # FDC proxy: #170000 Onions, raw
    "Onion Skins": {
        "calories_kcal": 40.0, "protein_g": 1.10, "fat_g": 0.10,
        "fiber_g": 1.7, "calcium_mg": 23.0, "phosphorus_mg": 29.0,
        "moisture_pct": 89.1, "avg_peel_weight_fresh_g": 5.0,
    },
    # FDC proxy: #169213 Carrots, raw
    "Carrot Peels": {
        "calories_kcal": 41.0, "protein_g": 0.93, "fat_g": 0.24,
        "fiber_g": 2.8, "calcium_mg": 33.0, "phosphorus_mg": 35.0,
        "moisture_pct": 88.3, "avg_peel_weight_fresh_g": 8.0,
    },
    # FDC proxy: #170457 Tomatoes, red, ripe, raw
    "Tomato Skins": {
        "calories_kcal": 18.0, "protein_g": 0.88, "fat_g": 0.20,
        "fiber_g": 1.2, "calcium_mg": 11.0, "phosphorus_mg": 24.0,
        "moisture_pct": 94.5, "avg_peel_weight_fresh_g": 10.0,
    },
    # FDC proxy: #168409 Cucumber, with peel, raw
    "Cucumber Peels": {
        "calories_kcal": 15.0, "protein_g": 0.65, "fat_g": 0.11,
        "fiber_g": 0.5, "calcium_mg": 16.0, "phosphorus_mg": 24.0,
        "moisture_pct": 95.2, "avg_peel_weight_fresh_g": 12.0,
    },
    # FDC proxy: #169228 Eggplant, raw
    "Brinjal Peels": {
        "calories_kcal": 25.0, "protein_g": 0.98, "fat_g": 0.18,
        "fiber_g": 3.0, "calcium_mg": 9.0, "phosphorus_mg": 24.0,
        "moisture_pct": 92.3, "avg_peel_weight_fresh_g": 10.0,
    },
    # FDC proxy: #169975 Cabbage, raw
    "Cabbage Leaves": {
        "calories_kcal": 25.0, "protein_g": 1.28, "fat_g": 0.10,
        "fiber_g": 2.5, "calcium_mg": 40.0, "phosphorus_mg": 26.0,
        "moisture_pct": 92.2, "avg_peel_weight_fresh_g": 20.0,
    },

    # FDC proxy: #170108 Peppers, sweet, green, raw
    "Bell Pepper Scraps": {
        "calories_kcal": 31.0, "protein_g": 0.99, "fat_g": 0.30,
        "fiber_g": 2.1, "calcium_mg": 7.0, "phosphorus_mg": 26.0,
        "moisture_pct": 92.2, "avg_peel_weight_fresh_g": 12.0,
    },

    # FDC proxy: #170379 Broccoli, raw
    "Broccoli Stems": {
        "calories_kcal": 34.0, "protein_g": 2.82, "fat_g": 0.37,
        "fiber_g": 2.6, "calcium_mg": 47.0, "phosphorus_mg": 66.0,
        "moisture_pct": 89.3, "avg_peel_weight_fresh_g": 25.0,
    },
    # FDC proxy: #169986 Cauliflower, raw
    "Cauliflower Leaves": {
        "calories_kcal": 25.0, "protein_g": 1.92, "fat_g": 0.28,
        "fiber_g": 2.0, "calcium_mg": 22.0, "phosphorus_mg": 44.0,
        "moisture_pct": 92.1, "avg_peel_weight_fresh_g": 18.0,
    },

}

# Build the public DM-basis table
PEEL_NUTRITION: Dict[str, Dict[str, float]] = {
    label: _to_dm(vals) for label, vals in _FRESH.items()
}

# Backward-compat alias: system_controller uses "avg_peel_weight_g"
# which now means DM weight.  We store it under both names.
for _v in PEEL_NUTRITION.values():
    _v["avg_peel_weight_g"] = _v["avg_peel_weight_dm_g"]


# ── Per-class fresh weight ranges (grams, as-fed) ────────────
# Each peel is assigned a random fresh weight from these ranges
# every time it is classified.  The fresh weight is then
# converted to DM weight using the peel's moisture percentage.
PEEL_WEIGHT_RANGES: Dict[str, Tuple[float, float]] = {
    "Potato Skins":       (1.8, 2.2),
    "Onion Skins":        (1.8, 2.2),
    "Carrot Peels":       (6.8, 7.2),
    "Cucumber Peels":     (6.0, 8.0),
    # All remaining classes: 4–8 g
    "Tomato Skins":       (3.0, 5.0),
    "Brinjal Peels":      (4.8, 5.2),
    "Cabbage Leaves":     (6.0, 10.0),
    "Bell Pepper Scraps": (8.0, 10.0),
    "Broccoli Stems":     (7.0, 11.0),
    "Cauliflower Leaves": (8.0, 12.0),
}

# Default range for any label not listed above
_DEFAULT_WEIGHT_RANGE: Tuple[float, float] = (4.0, 8.0)


def _random_fresh_weight(peel_label: str) -> float:
    """Return a random fresh (as-fed) weight in grams for one peel."""
    lo, hi = PEEL_WEIGHT_RANGES.get(peel_label, _DEFAULT_WEIGHT_RANGE)
    return round(random.uniform(lo, hi), 1)


# Nutrient keys used for matching and accumulation
# All values are per 100 g DM.
NUTRIENT_KEYS = [
    "calories_kcal",   # kcal / 100 g DM
    "protein_g",       # g crude protein / 100 g DM  (= % DM)
    "fat_g",           # g crude fat / 100 g DM      (= % DM)
    "fiber_g",         # g total dietary fiber / 100 g DM (= % DM)
    "calcium_mg",      # mg Ca / 100 g DM
    "phosphorus_mg",   # mg P  / 100 g DM
]


# ── Animal Feed Requirements (% DM basis) ────────────────────
# (min, max) ideal range.  Protein, fat, fibre are % of DM.
# Calcium and phosphorus are also % of DM (converted to mg/100g DM
# in this dict so units match the peel data above).
# Energy is kcal ME / 100 g DM (i.e. divide kcal/kg by 10).
#
# Sources & production classes:
#   Cattle — Dairy lactating adult, NRC (2001) Nutrient Requirements
#            of Dairy Cattle, 7th rev.  CP 15-17.5% DM; Ca 0.60-0.80%
#            DM; P 0.30-0.45% DM; NDF min 25% → crude fibre ~17-21%;
#            NEL 1.5-1.7 Mcal/kg ≈ ME 2300-2700 kcal/kg.
#   Goats  — Adult maintenance, NRC (2007) Nutrient Requirements of
#            Small Ruminants; MSD Vet Manual.  CP 7-11% DM; Ca 0.30-
#            0.50% DM; P 0.20-0.30% DM; fibre 15-25% DM.
#   Poultry — Broiler grower (21-42 d), NRC (1994) Nutrient
#             Requirements of Poultry, 9th rev.; MSD Vet Manual.
#             CP 20-23%; Ca 0.90-1.00%; avail. P 0.35-0.45% (total
#             ~0.60-0.70%); crude fibre 3-5%; ME 3000-3200 kcal/kg.
#   Pigs   — Grower-finisher 50-80 kg, NRC (2012) Nutrient
#            Requirements of Swine, 11th rev.; MSD Vet Manual.
#            CP 13-18%; Ca 0.50-0.70%; total P 0.45-0.65%;
#            crude fibre 5-7%; ME 3200-3400 kcal/kg.

ANIMAL_PROFILES: Dict[str, Dict[str, Tuple[float, float]]] = {
    # (min, max) — units match PEEL_NUTRITION keys above
    "Cattle": {
        # Dairy lactating adult (NRC 2001)
        "calories_kcal":  (230.0, 270.0),   # kcal ME / 100 g DM
        "protein_g":      (15.0,  17.5),    # % DM (g/100g DM)
        "fat_g":          (3.0,   6.0),     # % DM
        "fiber_g":        (17.0,  21.0),    # % DM (crude fibre approx)
        "calcium_mg":     (600.0, 800.0),   # mg / 100 g DM  (= 0.60-0.80%)
        "phosphorus_mg":  (300.0, 450.0),   # mg / 100 g DM  (= 0.30-0.45%)
    },
    "Goats": {
        # Adult maintenance (NRC 2007, MSD)
        "calories_kcal":  (200.0, 240.0),   # kcal ME / 100 g DM
        "protein_g":      (7.0,   11.0),    # % DM
        "fat_g":          (2.0,   5.0),     # % DM
        "fiber_g":        (15.0,  25.0),    # % DM
        "calcium_mg":     (300.0, 500.0),   # mg / 100 g DM
        "phosphorus_mg":  (200.0, 300.0),   # mg / 100 g DM
    },
    "Poultry": {
        # Broiler grower 21-42 d (NRC 1994, MSD)
        "calories_kcal":  (300.0, 320.0),   # kcal ME / 100 g DM
        "protein_g":      (20.0,  23.0),    # % DM
        "fat_g":          (3.0,   8.0),     # % DM
        "fiber_g":        (3.0,   5.0),     # % DM
        "calcium_mg":     (900.0, 1000.0),  # mg / 100 g DM
        "phosphorus_mg":  (600.0, 700.0),   # mg / 100 g DM (total P)
    },
    "Pigs": {
        # Grower-finisher 50-80 kg (NRC 2012, MSD)
        "calories_kcal":  (320.0, 340.0),   # kcal ME / 100 g DM
        "protein_g":      (13.0,  18.0),    # % DM
        "fat_g":          (3.0,   8.0),     # % DM
        "fiber_g":        (5.0,   7.0),     # % DM
        "calcium_mg":     (500.0, 700.0),   # mg / 100 g DM
        "phosphorus_mg":  (450.0, 650.0),   # mg / 100 g DM
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
    "protein_g": 2.0,       # Protein is critical for all animals
    "fat_g": 1.0,
    "fiber_g": 1.5,         # Fibre tolerance varies greatly across species
    "calcium_mg": 1.5,      # Ca:P ratio important
    "phosphorus_mg": 1.5,
}


# ── Bin State Tracking ────────────────────────────────────────

@dataclass
class BinState:
    """Tracks the nutrient accumulation and DM weight of a single bin."""
    animal: str
    bin_id: int
    total_weight_g: float = 0.0         # From MiniScale (actual DM weight)
    estimated_weight_g: float = 0.0     # Estimated DM weight from classification
    peel_count: int = 0
    # Accumulated nutrients (absolute amounts, not per 100 g)
    nutrients: Dict[str, float] = field(default_factory=lambda: {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "calcium_mg": 0.0,
        "phosphorus_mg": 0.0,
    })

    def add_peel(self, peel_label: str, count: int = 1, actual_weight_g: Optional[float] = None):
        """Add a peel (or multiple) to this bin and update nutrient totals.

        Weight tracking is on a DM basis.  ``actual_weight_g`` should be
        a DM weight if provided; otherwise we use a randomly generated
        fresh weight (1.7g to 2.5g) converted to DM.
        """
        nutrition = PEEL_NUTRITION.get(peel_label)
        if not nutrition:
            return

        if actual_weight_g is not None:
            dm_weight = actual_weight_g
        else:
            dm_frac = nutrition.get("dm_pct", 10.0) / 100.0
            dm_weight = 0.0
            for _ in range(count):
                fresh_w = _random_fresh_weight(peel_label)
                dm_weight += fresh_w * dm_frac

        self.estimated_weight_g += dm_weight
        self.peel_count += count

        # Scale nutrients from per-100g-DM to actual DM weight
        scale = dm_weight / 100.0
        for key in NUTRIENT_KEYS:
            self.nutrients[key] += nutrition.get(key, 0.0) * scale

    def update_actual_weight(self, scale_weight_g: float):
        """Update with actual weight from MiniScale."""
        self.total_weight_g = scale_weight_g

    def get_nutrient_profile_per_100g(self) -> Dict[str, float]:
        """Get current bin nutrient profile normalized to per 100 g DM."""
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
    """Compute suitability using Cosine Similarity on DM-basis profiles.

    Because both peel nutrients and animal requirements are now in the
    same units (per 100 g DM), the cosine similarity directly measures
    how well the *proportional shape* of the peel's nutrient profile
    matches what the animal needs.

    All six nutrient dimensions are used, each weighted by
    ``NUTRIENT_WEIGHTS`` to reflect nutritional importance.
    """
    nutrition = PEEL_NUTRITION.get(peel_label)
    profile = ANIMAL_PROFILES.get(animal)
    if not nutrition or not profile:
        return 0.0

    peel_vector = []
    animal_vector = []

    for key in NUTRIENT_KEYS:
        peel_val = nutrition.get(key, 0.0)
        low, high = profile.get(key, (0.0, 1.0))
        target_val = (low + high) / 2.0
        weight = NUTRIENT_WEIGHTS.get(key, 1.0)

        # Normalize each dimension by the animal's target midpoint so
        # that nutrients with very different magnitudes (e.g. 300 kcal
        # vs 0.5% fat) contribute equally before weighting.
        if target_val > 0:
            peel_vector.append((peel_val / target_val) * weight)
            animal_vector.append(1.0 * weight)  # target is 1.0 after norm
        else:
            peel_vector.append(0.0)
            animal_vector.append(0.0)

    # Cosine similarity
    dot = sum(p * a for p, a in zip(peel_vector, animal_vector))
    mag_p = sum(p ** 2 for p in peel_vector) ** 0.5
    mag_a = sum(a ** 2 for a in animal_vector) ** 0.5

    if mag_p == 0 or mag_a == 0:
        return 0.0

    similarity = dot / (mag_p * mag_a)
    score = similarity * 100.0

    # Adaptive bias: penalise bins that are getting too full (DM weight)
    if current_bin_state and current_bin_state.peel_count > 0:
        effective_wt = (
            current_bin_state.total_weight_g
            if current_bin_state.total_weight_g > 0
            else current_bin_state.estimated_weight_g
        )
        if effective_wt > 500:
            score *= 0.8

    return score


def find_optimal_bin(
    peel_labels: List[str],
    bin_states: Dict[int, BinState],
) -> int:
    """Find optimal bin using Cosine-Similarity scoring + load balancing.

    If the top two bins score within 9 points of each other, the lighter
    bin (by DM weight) wins.
    """
    scores = {}
    for bin_id, state in bin_states.items():
        animal = state.animal
        total_score = 0.0
        for label in peel_labels:
            total_score += compute_suitability_score(label, animal, state)
        scores[bin_id] = total_score / max(len(peel_labels), 1)

    sorted_bins = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    if not sorted_bins:
        return 0

    best_bin_id, best_score = sorted_bins[0]

    # Tie-breaker: if second-best is within 9 points, load-balance
    if len(sorted_bins) > 1:
        second_bin_id, second_score = sorted_bins[1]
        if (best_score - second_score) < 9.0:
            w1 = bin_states[best_bin_id].total_weight_g or bin_states[best_bin_id].estimated_weight_g
            w2 = bin_states[second_bin_id].total_weight_g or bin_states[second_bin_id].estimated_weight_g
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
    """Get estimated DM weight for a peel type using a per-class random
    fresh weight converted to DM."""
    nutrition = PEEL_NUTRITION.get(peel_label)
    if not nutrition:
        return 1.0 * count  # conservative DM fallback

    dm_frac = nutrition.get("dm_pct", 10.0) / 100.0
    total_dm_weight = 0.0
    for _ in range(count):
        fresh_w = _random_fresh_weight(peel_label)
        total_dm_weight += fresh_w * dm_frac

    return total_dm_weight


def get_peel_nutrients_for_weight(peel_label: str, weight_g: float) -> Dict[str, float]:
    """Get scaled nutrient values for a given peel at a specific DM weight."""
    nutrition = PEEL_NUTRITION.get(peel_label, {})
    scale = weight_g / 100.0
    return {
        key: round(nutrition.get(key, 0.0) * scale, 3)
        for key in NUTRIENT_KEYS
    }
