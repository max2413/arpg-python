"""Player state persistence (saving/loading)."""

import json
import os

SAVE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "save.json",
)

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
    if not os.path.exists(SAVE_PATH):
        print(f"[save] no save file found at {SAVE_PATH}")
        return False
    
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
        
        if "inventory" in data:
            inventory.from_dict(data["inventory"])
        if "skills" in data:
            skills.from_dict(data["skills"])
        if quest_manager and "quests" in data:
            quest_manager.from_dict(data["quests"])
            
        print(f"[save] game state loaded from {SAVE_PATH}")
        return True
    except Exception as e:
        print(f"[save] failed to load game state: {e}")
        return False
