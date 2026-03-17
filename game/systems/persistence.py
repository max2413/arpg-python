"""Player state persistence (saving/loading)."""

import json
import os

from game.systems.inventory import sanitize_inventory_payload
from game.systems.paths import data_path, save_path

SAVE_PATH = save_path("save.json")
LEGACY_SAVE_PATH = data_path("save.json")

def save_game(inventory, skills, quest_manager=None):
    """Saves player inventory, skills, and quests to data/save.json."""
    data = {
        "inventory": inventory.to_dict(),
        "skills": skills.to_dict(),
    }
    if quest_manager:
        data["quests"] = quest_manager.to_dict()
        
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[save] game state saved to {SAVE_PATH}")
    except Exception as e:
        print(f"[save] failed to save game state: {e}")

def load_game(inventory, skills, quest_manager=None):
    """Loads player inventory, skills, and quests from data/save.json."""
    source_path = SAVE_PATH if os.path.exists(SAVE_PATH) else LEGACY_SAVE_PATH
    if not os.path.exists(source_path):
        print(f"[save] no save file found at {SAVE_PATH}")
        return False
    
    try:
        with open(source_path, "r") as f:
            data = json.load(f)
        
        if "inventory" in data:
            inventory.from_dict(sanitize_inventory_payload(data["inventory"]))
        if "skills" in data:
            skills.from_dict(data["skills"])
        if quest_manager and "quests" in data:
            quest_manager.from_dict(data["quests"])
            
        print(f"[save] game state loaded from {source_path}")
        return True
    except Exception as e:
        print(f"[save] failed to load game state: {e}")
        return False
