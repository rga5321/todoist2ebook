#!/usr/bin/env python3

import os
import subprocess
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s -  %(levelname)s-  %(message)s')
logging.info('Start')

SEND_EMAIL = os.getenv("SEND_EMAIL", "false").strip().lower() in ("True", "true")

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = os.getenv('SMTP_PORT')
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_FROM = os.getenv('SMTP_FROM')

DESTINATION_EMAIL= os.getenv('DESTINATION_EMAIL')

# File naming
output = subprocess.check_output(["date", "+%d-%m-%Y-%H-%M-%S"])
file_stamp=bytes.decode(output)
file_name = 'todoist-' + file_stamp.strip() + '.epub'
logging.info('File name: ' + file_name)

# Building the epub with the recipe
subprocess.run(['ebook-convert','Todoist.recipe',file_name])

if SEND_EMAIL:
    # Send the file via email
    logging.info('Sending email to: ' + DESTINATION_EMAIL)
    subprocess.run(
        ['calibre-smtp','--attachment',file_name,'--relay',SMTP_SERVER,'--port',SMTP_PORT,'--username',SMTP_USER,'--password',SMTP_PASSWORD,
        '--encryption-method','TLS','--subject',file_name,SMTP_FROM,DESTINATION_EMAIL,'email body']
    )

    logging.info('End')