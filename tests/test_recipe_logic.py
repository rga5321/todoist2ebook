
import pytest
import sys
import os
import importlib.util
from unittest.mock import MagicMock

# Mock calibre modules before importing the recipe
sys.modules['mechanize'] = MagicMock()
sys.modules['calibre'] = MagicMock()
sys.modules['calibre.web'] = MagicMock()
sys.modules['calibre.web.feeds'] = MagicMock()
sys.modules['calibre.web.feeds.news'] = MagicMock()

# Setup BasicNewsRecipe mock
class MockBasicNewsRecipe:
    recipe_specific_options = {}
    def __init__(self, *args, **kwargs):
        pass
    def abort_recipe_processing(self, msg):
        raise Exception(f"Aborted: {msg}")

sys.modules['calibre.web.feeds.news'].BasicNewsRecipe = MockBasicNewsRecipe

import types

# Load the recipe file using exec since it has a non-standard extension
recipe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Todoist.recipe")
if not os.path.exists(recipe_path):
    raise FileNotFoundError(f"Recipe file not found at {recipe_path}")

module = types.ModuleType("Todoist")
# We need to inject the mock BasicNewsRecipe into the module's namespace before exec
# actually, since it imports it, we need to make sure sys.modules has it (which we did)

with open(recipe_path, 'r') as f:
    exec(f.read(), module.__dict__)

def test_parse_env_bool():
    assert module.parse_env_bool("True") is True
    assert module.parse_env_bool("true") is True
    assert module.parse_env_bool("1") is True
    assert module.parse_env_bool("False") is False
    assert module.parse_env_bool("0") is False

def test_parse_env_list():
    assert module.parse_env_list("['a', 'b']") == ['a', 'b']
    assert module.parse_env_list("[]") == []

def test_todoist2ebook_init():
    # Helper to create instance with options
    def create_instance(options):
        # Patch the class options for the test
        module.Todoist2ebook.recipe_specific_options = options
        return module.Todoist2ebook()

    # Test missing Project ID
    with pytest.raises(Exception, match="TODOIST_PROJECT_ID mandatory parameter missing"):
        create_instance({
            'ARCHIVE_DOWNLOADED': 'False',
            'URL_KEYWORD_EXCEPTIONS': '[]'
        })
        
    # Test valid init
    valid_options = {
        'ARCHIVE_DOWNLOADED': 'True',
        'URL_KEYWORD_EXCEPTIONS': '["ignore"]',
        'TODOIST_PROJECT_ID': '123',
        'TODOIST_API_KEY': 'abc'
    }
    app = create_instance(valid_options)
    assert app.archive_downloaded is True
    assert app.keyword_exceptions == ["ignore"]
    assert app.todoist_project_id == '123'
    assert app.todoist_api_key == 'abc'
