"""Game constants and utility functions."""
import json
from pathlib import Path
from typing import Dict, Optional

# Load mappings from JSON files to keep constants manageable
_CONSTANTS_DIR = Path(__file__).parent / "data"


def _load_json_mapping(filename: str) -> Dict[int, str]:
    """Load ID-to-name mapping from JSON file."""
    try:
        with open(_CONSTANTS_DIR / filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert string keys to int keys
            return {int(k): v for k, v in data.items()}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback to empty dict if file missing or invalid
        return {}


# Load game data mappings
HERO_ID_TO_NAME: Dict[int, str] = _load_json_mapping("hero_ids.json")
ITEM_ID_TO_NAME: Dict[int, str] = _load_json_mapping("item_ids.json") 
ABILITY_ID_TO_NAME: Dict[int, str] = _load_json_mapping("ability_ids.json")

# Rank tier mappings for Herald analysis
RANK_TIERS: Dict[int, str] = {
    11: "Herald I",
    12: "Herald II", 
    13: "Herald III",
    14: "Herald IV",
    15: "Herald V",
    21: "Guardian I",
    22: "Guardian II",
    23: "Guardian III", 
    24: "Guardian IV",
    25: "Guardian V",
    31: "Crusader I",
    32: "Crusader II",
    33: "Crusader III",
    34: "Crusader IV", 
    35: "Crusader V",
    41: "Archon I",
    42: "Archon II",
    43: "Archon III",
    44: "Archon IV",
    45: "Archon V",
    51: "Legend I",
    52: "Legend II",
    53: "Legend III",
    54: "Legend IV",
    55: "Legend V",
    61: "Ancient I",
    62: "Ancient II",
    63: "Ancient III",
    64: "Ancient IV",
    65: "Ancient V",
    71: "Divine I",
    72: "Divine II",
    73: "Divine III",
    74: "Divine IV",
    75: "Divine V",
    80: "Immortal"
}


def get_hero_name(hero_id: Optional[int]) -> str:
    """Get hero name by ID with fallback."""
    if hero_id is None:
        return "Unknown Hero"
    return HERO_ID_TO_NAME.get(hero_id, f"Unknown Hero ({hero_id})")


def get_item_name(item_id: Optional[int]) -> str:
    """Get item name by ID with fallback."""
    if item_id is None or item_id == 0:
        return "Empty"
    return ITEM_ID_TO_NAME.get(item_id, f"Unknown Item ({item_id})")


def get_ability_name(ability_id: Optional[int]) -> str:
    """Get ability name by ID with fallback."""
    if ability_id is None:
        return "Unknown Ability"
    return ABILITY_ID_TO_NAME.get(ability_id, f"Unknown Ability ({ability_id})")


def get_rank_name(rank_tier: Optional[int]) -> str:
    """Get rank name by tier with Herald highlighting."""
    if rank_tier is None:
        return "Unranked"
    return RANK_TIERS.get(rank_tier, f"Unknown Rank ({rank_tier})")


def is_herald_rank(rank_tier: Optional[int]) -> bool:
    """Check if rank tier is Herald (11-15)."""
    return rank_tier is not None and 11 <= rank_tier <= 15


def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS."""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


def calculate_kda_ratio(kills: int, deaths: int, assists: int) -> float:
    """Calculate KDA ratio with proper handling of zero deaths."""
    if deaths == 0:
        return float(kills + assists)
    return (kills + assists) / deaths


def format_large_number(number: int) -> str:
    """Format large numbers with commas."""
    return f"{number:,}"