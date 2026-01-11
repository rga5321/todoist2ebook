import pytest
import os
import zipfile
import shutil
from bs4 import BeautifulSoup
import sys

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epub_qr import add_qr_to_epub

@pytest.fixture
def sample_epub(tmp_path):
    """Creates a dummy EPUB file with minimal structure for testing."""
    epub_path = tmp_path / "test.epub"
    
    # Create content
    html_content = """
    <html>
        <body>
            <h1>Test Article</h1>
            <a rel="calibre-downloaded-from" href="https://example.com/article">Source</a>
            <p>Some content</p>
        </body>
    </html>
    """
    
    # Create zip structure
    with zipfile.ZipFile(epub_path, 'w') as zf:
        zf.writestr('index.html', html_content)
        
    return str(epub_path)

def test_add_qr_to_epub(sample_epub):
    """Verifies that QR code is added to the EPUB."""
    add_qr_to_epub(sample_epub)
    
    # Verify content
    with zipfile.ZipFile(sample_epub, 'r') as zf:
        # Check files exist
        files = zf.namelist()
        png_files = [f for f in files if f.endswith('.png')]
        assert len(png_files) > 0, "No PNG file added to archive"
        
        # Check HTML modification
        html_content = zf.read('index.html').decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for img tag
        imgs = soup.find_all('img')
        assert len(imgs) > 0, "No <img> tag added to HTML"
        assert imgs[-1]['alt'] == 'QR to article URL'
