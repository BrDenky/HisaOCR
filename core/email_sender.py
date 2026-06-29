import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

def send_excel_email(excel_path, sender_email, app_password, recipient_email):
    """
    Envía el archivo Excel como adjunto a través del servidor SMTP de Gmail.
    Retorna (success: bool, message: str)
    """
    # Validar archivo
    if not os.path.exists(excel_path):
        return False, f"El archivo Excel {excel_path} no existe."

    # Procesar destinatarios múltiples (pueden venir separados por comas)
    recipients = [email.strip() for email in recipient_email.split(",") if email.strip()]
    if not recipients:
        return False, "No se especificaron destinatarios válidos."

    # Configuración SMTP
    smtp_server = "smtp.gmail.com"
    port = 587
    
    # Crear mensaje
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    
    # Subject con fecha actual
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    msg['Subject'] = f"Reporte Semanal OCR Cédulas - {fecha_hoy}"
    
    body = (
        "Estimado,\n\n"
        f"Se adjunta el reporte semanal correspondiente al corte del {fecha_hoy} de los registros "
        "de ingreso de visitas por el sistema OCR.\n\n"
        "Este es un mensaje generado automáticamente.\n\n"
        "Atentamente,\n"
        "Sistema OCR Cédulas"
    )
    msg.attach(MIMEText(body, 'plain'))
    
    # Adjuntar archivo Excel
    filename = os.path.basename(excel_path)
    try:
        with open(excel_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}",
            )
            msg.attach(part)
    except Exception as e:
        return False, f"Error al adjuntar el archivo Excel: {str(e)}"
        
    # Enviar correo
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()  # Iniciar cifrado TLS
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True, "Correo enviado exitosamente."
    except Exception as e:
        return False, f"Error de conexión SMTP: {str(e)}"
