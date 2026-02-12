
import pytest
import sys
import os
import importlib.util
from unittest.mock import MagicMock
import types
import subprocess
import threading
import http.server
import json
import socket
import zipfile
import shutil
import time

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

# Load the recipe file using exec since it has a non-standard extension
recipe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Todoist.recipe")
if not os.path.exists(recipe_path):
    raise FileNotFoundError(f"Recipe file not found at {recipe_path}")

module = types.ModuleType("Todoist")
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
        'TODOIST_API_KEY': 'abc',
        'TODOIST_API_URL': 'http://localhost:8000'
    }
    app = create_instance(valid_options)
    assert app.archive_downloaded is True
    assert app.keyword_exceptions == ["ignore"]
    assert app.todoist_project_id == '123'
    assert app.todoist_api_key == 'abc'
    assert app.todoist_api_url == 'http://localhost:8000'


# --- Integration Test ---

class MockTodoistHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if '/api/v1/tasks' in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Mock task with real article
            tasks = [
                {
                    'id': '12345',
                    'content': '[Test Article](https://www.enriquedans.com/2026/01/mas-alla-de-estados-unidos-y-china-el-verdadero-tablero-tecnologico.html)',
                    'created_at': '2026-01-10T12:00:00Z'
                }
            ]
            response_data = {'results': tasks}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        elif 'close' in self.path:
             self.send_response(204)
             self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_POST(self):
         if 'close' in self.path:
             self.send_response(204)
             self.end_headers()
         else:
             self.send_response(404)
             self.end_headers()

@pytest.fixture
def mock_todoist_server():
    # Find free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    
    server = http.server.HTTPServer(('localhost', port), MockTodoistHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    yield f'http://localhost:{port}'
    
    server.shutdown()

def test_full_conversion(mock_todoist_server):
    """
    Integration test that runs ebook-convert with a mocked Todoist API but fetching a real article.
    """
    # Create persistent output directory
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    output_epub = os.path.join(output_dir, "output.epub")
    
    recipe_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Todoist.recipe")
    
    # Load env vars
    from dotenv import load_dotenv
    load_dotenv()
    calibre_binary = os.getenv("CALIBRE_BINARY", "ebook-convert")
    
    # Check if ebook-convert is available
    if shutil.which(calibre_binary) is None:
        pytest.skip(f"{calibre_binary} not found in PATH")
        
    cmd = [
        calibre_binary,
        recipe_file,
        str(output_epub),
        f"--recipe-specific-option=TODOIST_API_URL:{mock_todoist_server}",
        "--recipe-specific-option=TODOIST_PROJECT_ID:mock_project",
        "--recipe-specific-option=TODOIST_API_KEY:mock_key",
        "--recipe-specific-option=ARCHIVE_DOWNLOADED:False"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"Generated EPUB available at: {output_epub}")
    
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        pytest.fail("ebook-convert failed")
        
    assert os.path.exists(output_epub)
    
    # Verification: Unzip and check content
    found_article_text = False
    found_unwanted_markup = False
    
    with zipfile.ZipFile(output_epub, 'r') as zf:
        for filename in zf.namelist():
            if filename.endswith('.html') or filename.endswith('.xhtml'):
                content = zf.read(filename).decode('utf-8')
                
                # Check for article title/content
                if "Más allá de Estados Unidos y China" in content:
                    found_article_text = True
                    
                    # Basic check for stripped markup - verifying it doesn't look like a full webpage
                    # This depends on how good Calibre's cleanup is. 
                    # We check for the absence of some common site clutter if possible, 
                    # or just that the structure is mainly paragraphs.
                    if 'class="sidebar"' in content or 'id="footer"' in content:
                         found_unwanted_markup = True
                         
    assert found_article_text, "Article content not found in EPUB"
    assert not found_unwanted_markup, "Unwanted markup (sidebar/footer) found in EPUB"
