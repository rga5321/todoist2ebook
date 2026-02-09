#!/usr/bin/env python3

import os
import subprocess
import logging
import smtplib
import ssl
from email.message import EmailMessage
import os
import email.utils
import mimetypes

from dotenv import load_dotenv
from epub_qr import add_qr_to_epub
import ast

# Load environment variables
load_dotenv()



# Global functions
def parse_env_list(val):
    try:
        return ast.literal_eval(val)
    except Exception:
        return []

def send_email(file_name, smtp_conf, destination_email):
    logging.info("Sending email to: " + destination_email)
    
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type is None:
        mime_type = "application/octet-stream"
    maintype, subtype = mime_type.split("/", 1)

    # Create message
    msg = EmailMessage()
    msg["From"] = smtp_conf["FROM"]
    msg["To"] = destination_email
    msg["Subject"] = "Kindle delivery: " + file_name
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()
    msg["MIME-Version"] = "1.0"
    msg["Content-Transfer-Encoding"] = "base64"

    msg.set_content(
        "This is the body of the email. The attached file is the latest Todoist tasks in epub format."
    )

    with open(file_name, "rb") as f:
        file_data = f.read()
        msg.add_attachment(
            file_data, maintype=maintype, subtype=subtype, filename=file_name
        )

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_conf["SERVER"], smtp_conf["PORT"]) as server:
        server.starttls(context=context)
        server.login(smtp_conf["USER"], smtp_conf["PASSWORD"])
        server.send_message(msg)

    logging.info("Email sent successfully to " + destination_email)

def main():
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s -  %(levelname)s-  %(message)s"
    )
    logging.info("Start")

    SEND_EMAIL = os.getenv("SEND_EMAIL", "false").strip().lower() in ("True", "true")
    CALIBRE_BINARY = os.getenv("CALIBRE_BINARY", "ebook-convert")
    
    smtp_conf = {
        "SERVER": os.getenv("SMTP_SERVER"),
        "PORT": os.getenv("SMTP_PORT"),
        "USER": os.getenv("SMTP_USER"),
        "PASSWORD": os.getenv("SMTP_PASSWORD"),
        "FROM": os.getenv("SMTP_FROM"),
    }
    DESTINATION_EMAIL = os.getenv("DESTINATION_EMAIL")

    file_name = f"todoist-{subprocess.check_output(['date', '+%Y-%m-%d_%H%M']).decode('utf-8').strip()}.epub"
    logging.info("File name: " + file_name)

    # Load .env variables for recipe
    env = os.environ.copy()
    env["URL_KEYWORD_EXCEPTIONS"] = os.getenv("URL_KEYWORD_EXCEPTIONS", "[]")
    env["ARCHIVE_DOWNLOADED"] = os.getenv("ARCHIVE_DOWNLOADED", "False")
    env["TODOIST_PROJECT_ID"] = os.getenv("TODOIST_PROJECT_ID", "")
    env["TODOIST_API_KEY"] = os.getenv("TODOIST_API_KEY", "")

    # Check calibre version
    try:
        version_output = subprocess.check_output([CALIBRE_BINARY, "--version"]).decode("utf-8").strip()
        logging.info(f"Calibre version: {version_output}")
    except Exception as e:
        logging.error(f"Failed to get calibre version: {e}")

    # Build command
    cmd = [
        CALIBRE_BINARY,
        "Todoist.recipe",
        file_name,
        f'--recipe-specific-option=URL_KEYWORD_EXCEPTIONS:{env["URL_KEYWORD_EXCEPTIONS"]}',
        f'--recipe-specific-option=ARCHIVE_DOWNLOADED:{env["ARCHIVE_DOWNLOADED"]}',
        f'--recipe-specific-option=TODOIST_PROJECT_ID:{env["TODOIST_PROJECT_ID"]}',
        f'--recipe-specific-option=TODOIST_API_KEY:{env["TODOIST_API_KEY"]}',
    ]
    
    # Building the epub with the recipe, passing env vars
    subprocess.run(
        cmd,
        env=env,
    )

    # Add QR to every article in epub file
    logging.info("Adding QR codes to EPUB")
    add_qr_to_epub(file_name)

    # EPUB to MOBI to EPUB conversion round-trip
    # Amazon's "Send to Kindle" service has problematic behavior with native EPUB files.
    # Converting EPUB → MOBI → EPUB normalizes the ebook structure and ensures better
    # compatibility and formatting when processed by Amazon's Kindle delivery service.
    
    # Convert EPUB to MOBI
    mobi_file_name = file_name.replace('.epub', '.mobi')
    logging.info(f"Converting EPUB to MOBI: {mobi_file_name}")
    convert_cmd = [CALIBRE_BINARY, file_name, mobi_file_name]
    try:
        subprocess.run(convert_cmd, check=True)
        logging.info(f"Successfully converted to MOBI: {mobi_file_name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to convert EPUB to MOBI: {e}")
        return

    # Convert MOBI back to EPUB
    final_epub_file_name = file_name.replace('.epub', '-final.epub')
    logging.info(f"Converting MOBI back to EPUB: {final_epub_file_name}")
    convert_back_cmd = [CALIBRE_BINARY, mobi_file_name, final_epub_file_name]
    try:
        subprocess.run(convert_back_cmd, check=True)
        logging.info(f"Successfully converted back to EPUB: {final_epub_file_name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to convert MOBI to EPUB: {e}")
        return

    # Send the final EPUB file via email if configured
    if SEND_EMAIL:
        send_email(final_epub_file_name, smtp_conf, DESTINATION_EMAIL)
    
    logging.info("End")

if __name__ == "__main__":
    main()

