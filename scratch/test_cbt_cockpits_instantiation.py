import sys
sys.path.insert(0, ".")
import json
import flet as ft
from unittest.mock import MagicMock

def test_cockpit_instantiation():
    mock_page = MagicMock()
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.overlay = []

    # Import self_study component / test cockpit helpers
    from src.self_study import format_material_title, clean_pack_import_tag

    # Test title formatting
    assert clean_pack_import_tag("[PACK IMPORT] JAMB Mathematics") == "JAMB Mathematics"

    print("Cockpit helpers test passed!")

if __name__ == "__main__":
    test_cockpit_instantiation()
