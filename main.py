#!/usr/bin/env python3

import os
import subprocess
import logging
import smtplib
import ssl
import sys
from email.message import EmailMessage
import email.utils
import mimetypes

from dotenv import load_dotenv
from epub_qr import add_qr_to_epub
from epub_sections import remove_empty_sections

# Load environment variables
load_dotenv()

# Aux function to clean env vars, stripping comments and quotes
def clean_env_var(val):
    if not val:
        return val
    # Strip everything after a '#' to handle inline comments, then strip quotes/spaces
    return str(val).split("#", 1)[0].strip(" \"'")

def run_ebook_convert(cmd, env):
    """Run ebook-convert while filtering recipe-specific options from its output.

    Calibre logs the values of all recipe-specific options at INFO level, which
    can include credentials. The values are still passed on the command line,
    but this keeps them out of the log.
    """
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    try:
        for line in process.stdout:
            if (
                "TODOIST_API_KEY" in line
            ):
                continue
            sys.stdout.write(line)
            sys.stdout.flush()
    finally:
        process.stdout.close()

    returncode = process.wait()
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, cmd)

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

    SEND_EMAIL = clean_env_var(os.getenv("SEND_EMAIL", "false")).lower() in ("true", "1", "yes")
    CALIBRE_BINARY = clean_env_var(os.getenv("CALIBRE_BINARY", "ebook-convert"))
    
    smtp_conf = {
        "SERVER": clean_env_var(os.getenv("SMTP_SERVER")),
        "PORT": clean_env_var(os.getenv("SMTP_PORT")),
        "USER": clean_env_var(os.getenv("SMTP_USER")),
        "PASSWORD": clean_env_var(os.getenv("SMTP_PASSWORD")),
        "FROM": clean_env_var(os.getenv("SMTP_FROM")),
    }
    DESTINATION_EMAIL = clean_env_var(os.getenv("DESTINATION_EMAIL"))

    file_name = f"todoist-{subprocess.check_output(['date', '+%Y-%m-%d_%H%M']).decode('utf-8').strip()}-original.epub"
    logging.info("File name: " + file_name)

    # Load .env variables for recipe
    env = os.environ.copy()
    env["URL_KEYWORD_EXCEPTIONS"] = os.getenv("URL_KEYWORD_EXCEPTIONS", "[]") # Handled by ast.literal_eval
    env["ARCHIVE_DOWNLOADED"] = clean_env_var(os.getenv("ARCHIVE_DOWNLOADED", "False"))
    env["TODOIST_PROJECT_ID"] = clean_env_var(os.getenv("TODOIST_PROJECT_ID", ""))
    env["TODOIST_API_KEY"] = clean_env_var(os.getenv("TODOIST_API_KEY", ""))
    env["TODOIST_FAILED_ARTICLES_LABEL"] = clean_env_var(os.getenv("TODOIST_FAILED_ARTICLES_LABEL", ""))


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
        f'--recipe-specific-option=TODOIST_FAILED_ARTICLES_LABEL:{env["TODOIST_FAILED_ARTICLES_LABEL"]}',
    ]

    
    # Building the epub with the recipe, passing env vars
    try:
        run_ebook_convert(cmd, env)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to build initial EPUB: {e}")
        if os.path.exists(file_name):
            os.remove(file_name)
        return

    # Remove sections whose articles all failed to download. This happens after
    # Calibre has built the EPUB because failed articles are removed too late
    # for Calibre's own empty-feed filtering.
    try:
        removed_sections = remove_empty_sections(file_name)
        if removed_sections:
            logging.info(f"Removed {removed_sections} empty section(s) from EPUB")
    except Exception:
        logging.exception(
            "Failed to remove empty sections; continuing with the current EPUB"
        )

    # Add QR to every article in epub file
    logging.info("Adding QR codes to EPUB")
    articles_count = add_qr_to_epub(file_name)
    if articles_count == 0:
        logging.warning("Generated EPUB contains no downloaded articles. Aborting conversion and delivery.")
        if os.path.exists(file_name):
            os.remove(file_name)
        return

    # EPUB to MOBI to EPUB conversion round-trip
    # Amazon's "Send to Kindle" service has problematic behavior with native EPUB files.
    # Converting EPUB → MOBI → EPUB normalizes the ebook structure and ensures better
    # compatibility and formatting when processed by Amazon's Kindle delivery service.

    # Send the initial EPUB file via email if configured
    if SEND_EMAIL:
        send_email(file_name, smtp_conf, DESTINATION_EMAIL)
    
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
    backup_epub_file_name = file_name.replace('-original.epub', '-backup.epub')
    logging.info(f"Converting MOBI back to EPUB: {backup_epub_file_name}")
    convert_back_cmd = [CALIBRE_BINARY, mobi_file_name, backup_epub_file_name]
    try:
        subprocess.run(convert_back_cmd, check=True)
        logging.info(f"Successfully converted back to EPUB: {backup_epub_file_name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to convert MOBI to EPUB: {e}")
        return

    # Send the backup EPUB file via email if configured
    if SEND_EMAIL:
        send_email(backup_epub_file_name, smtp_conf, DESTINATION_EMAIL)
    
    logging.info("End")

if __name__ == "__main__":
    main()

