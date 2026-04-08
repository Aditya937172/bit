from __future__ import annotations

import os


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(CURRENT_DIR, "skills")


def read_skill(skill_name: str) -> str:
    path = os.path.join(SKILLS_DIR, skill_name)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def build_skill_block(file_names: list[str]) -> str:
    parts = []
    for file_name in file_names:
        content = read_skill(file_name)
        if content:
            parts.append(content)
    return "\n\n".join(parts)
