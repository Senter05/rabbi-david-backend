"""The complete written reading is free; plan and audio retain separate access."""
import copy

def reading_view(reading, tier):
    return copy.deepcopy(reading), dict(percent=100, locked_sections=[])
