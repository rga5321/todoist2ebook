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
    logging.info('Sending email to: ' + DESTINATION_EMAIL)
    # Send the file via email

    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    maintype, subtype = mime_type.split('/', 1)
    
    # Crear mensaje
    msg = EmailMessage()
    msg['From'] = SMTP_FROM
    msg['To'] = DESTINATION_EMAIL
    msg['Subject'] = 'Kindle delivery: ' + file_name
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Message-ID'] = email.utils.make_msgid()
    msg['MIME-Version'] = '1.0'
    msg['Content-Transfer-Encoding'] = 'base64'

    # Cuerpo del mensaje
    msg.set_content("Adjunto libro para tu Kindle.")

    # Adjuntar archivo
    with open(file_name, 'rb') as f:
        file_data = f.read()
        msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)

    # Enviar email
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        # server.set_debuglevel(1)  # Muestra el diálogo SMTP
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

    logging.info("Correo enviado con éxito.")



    # logging.info('Sending email to: ' + DESTINATION_EMAIL)
    # subprocess.run(
    #     ['calibre-smtp','--attachment',file_name,'--relay',SMTP_SERVER,'--port',SMTP_PORT,'--username',SMTP_USER,'--password',SMTP_PASSWORD,
    #     '--encryption-method','TLS','--subject',file_name,SMTP_FROM,DESTINATION_EMAIL,'email body']
    # )

    logging.info('End')