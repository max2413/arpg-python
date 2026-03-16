"""Simple quest system for tracking objectives and rewards."""

class Quest:
    def __init__(self, id, name, objectives, rewards):
        self.id = id
        self.name = name
        self.objectives = objectives # List of {"text": str, "count": int, "target": int, "type": "kill"|"gather"|"craft"|"skin", "id": str}
        self.rewards = rewards # {"gold": int, "xp": {skill: int}}
        self.completed = False

    def is_finished(self):
        return all(obj["count"] >= obj["target"] for obj in self.objectives)

class QuestManager:
    def __init__(self, app):
        self.app = app
        self.active_quests = []
        self.completed_ids = set()
        
    def start_quest(self, quest):
        if quest.id not in self.completed_ids and not any(q.id == quest.id for q in self.active_quests):
            self.active_quests.append(quest)
            self.app.hud.show_prompt(f"New Quest: {quest.name}")
            return True
        return False

    def notify_action(self, action_type, target_id, amount=1):
        """Called when player kills, gathers, crafts, or skins."""
        changed = False
        for quest in self.active_quests:
            for obj in quest.objectives:
                if obj["type"] == action_type and obj["id"] == target_id:
                    if obj["count"] < obj["target"]:
                        obj["count"] = min(obj["target"], obj["count"] + amount)
                        changed = True
            
            if quest.is_finished() and not quest.completed:
                self.complete_quest(quest)
                changed = True
        
        if changed:
            self.app.hud.refresh_quests()

    def complete_quest(self, quest):
        quest.completed = True
        self.completed_ids.add(quest.id)
        self.active_quests.remove(quest)
        
        # Give rewards
        rewards = quest.rewards
        if "gold" in rewards:
            self.app.inventory.add_item("gold", rewards["gold"])
        if "xp" in rewards:
            for skill, amount in rewards["xp"].items():
                self.app.skills.add_xp(skill, amount)
        
        self.app.hud.show_prompt(f"Quest Completed: {quest.name}!")
        self.app.hud.refresh_inventory()
        self.app.hud.refresh_skills()

    def to_dict(self):
        return {
            "completed_ids": list(self.completed_ids),
            "active_quests": [
                {
                    "id": q.id,
                    "name": q.name,
                    "objectives": q.objectives,
                    "rewards": q.rewards
                } for q in self.active_quests
            ]
        }

    def from_dict(self, data):
        self.completed_ids = set(data.get("completed_ids", []))
        self.active_quests = []
        for q_data in data.get("active_quests", []):
            q = Quest(q_data["id"], q_data["name"], q_data["objectives"], q_data["rewards"])
            self.active_quests.append(q)

def create_tutorial_quest():
    return Quest(
        "tutorial_basics",
        "The Hunter's Path",
        [
            {"text": "Kill a Wolf", "count": 0, "target": 1, "type": "kill", "id": "Wolf"},
            {"text": "Skin a Wolf Carcass", "count": 0, "target": 1, "type": "skin", "id": "leather"},
            {"text": "Gather Wood and Ore", "count": 0, "target": 2, "type": "gather", "id": "any"}, # Simplified
            {"text": "Craft a Bronze Sword", "count": 0, "target": 1, "type": "craft", "id": "bronze_sword"}
        ],
        {"gold": 100, "xp": {"Melee": 100, "Defense": 100, "Blacksmithing": 100}}
    )
