import zipfile
import os
import tempfile
import shutil
import qrcode
from PIL import Image
from bs4 import BeautifulSoup
import io

def add_qr_to_epub(epub_path):
    """
    Unzips an EPUB file, adds a QR code and a source link to each article, and repacks the EPUB.

    For each HTML/XHTML file found in the EPUB:
      - Searches for the article's URL (prefers <a rel="alternate">, otherwise first external link)
      - Generates a QR code image pointing to that URL
      - Appends a paragraph at the end of the <body> with:
          <b><u>Source</u></b>: <a href="URL">URL</a>
      - Appends the QR code image after the source paragraph

    The EPUB is then repacked, replacing the original file.

    Args:
        epub_path (str): Path to the EPUB file to process. The file is modified in place.
    """
    # 1. Unzip the EPUB into a temporary directory
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # 2. Find all HTML/XHTML files in the EPUB
    html_files = []
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if file.endswith('.html') or file.endswith('.xhtml'):
                html_files.append(os.path.join(root, file))

    # 3. For each HTML file, find the article URL and add a QR code
    for html_file in html_files:
        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        # Search for the link <a rel="calibre-downloaded-from">
        url = None
        a_tag = soup.find('a', href=True, rel='calibre-downloaded-from')
        if a_tag:
            url = a_tag['href']
        if not url:
            continue  # No URL found, skip this file

        # Generate the QR code for the article URL
        qr = qrcode.QRCode(box_size=3, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_data = img_byte_arr.getvalue()

        # Save the QR image in the same directory as the HTML file
        img_dir = os.path.dirname(html_file)
        img_name = f'qr_{os.path.splitext(os.path.basename(html_file))[0]}.png'
        img_path = os.path.join(img_dir, img_name)
        with open(img_path, 'wb') as img_file:
            img_file.write(img_data)

        # Add "Source: $url" and the <img> tag at the end of the <body>
        body = soup.find('body')
        if body:
            # Insert QR code
            img_tag = soup.new_tag('img', src=os.path.relpath(img_path, os.path.dirname(html_file)))
            img_tag['alt'] = 'QR to article URL'
            body.append(img_tag)
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(str(soup))

    # 4. Repack the EPUB
    temp_epub = epub_path + '.tmp'
    with zipfile.ZipFile(temp_epub, 'w') as zip_out:
        for foldername, subfolders, filenames in os.walk(temp_dir):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                arcname = os.path.relpath(file_path, temp_dir)
                zip_out.write(file_path, arcname)
    shutil.move(temp_epub, epub_path)
    shutil.rmtree(temp_dir)
