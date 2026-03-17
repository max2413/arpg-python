from setuptools import find_packages, setup

from direct.dist.commands import build_apps


APP_NAME = "arpg-prototype"


setup(
    name=APP_NAME,
    version="0.1.0",
    description="ARPG prototype",
    packages=find_packages(),
    options={
        "build_apps": {
            "gui_apps": {
                APP_NAME: "main.py",
            },
            "platforms": ["win_amd64"],
            "include_patterns": [
                "data/creatures.json",
                "data/items.json",
                "data/recipes.json",
                "data/vendors.json",
            ],
            "exclude_patterns": [
                "data/save.json",
                "data/overworld_level.json",
                "runtime/**",
                "**/__pycache__/**",
                "**/*.pyc",
                "tests/**",
                "tools/**",
                ".venv/**",
                ".claude/**",
            ],
            "include_modules": [
                "game",
                "game.app",
                "game.core",
                "game.entities",
                "game.services",
                "game.systems",
                "game.ui",
                "game.world",
            ],
            "plugins": [
                "pandagl",
                "p3openal_audio",
            ],
            "log_filename": "$USER_APPDATA/ARPG Prototype/output.log",
            "log_append": False,
        }
    },
    cmdclass={
        "build_apps": build_apps,
    },
)
