# -*- coding: utf-8 -*-
"""邮件发送模块（QQ 邮箱 SMTP / SSL）"""
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr


def send_email(smtp_host: str, smtp_port: int, sender: str,
               auth_code: str, receiver: str, subject: str,
               body_text: str) -> None:
    """通过 SMTP/SSL 发送邮件，失败抛异常"""
    msg = MIMEText(body_text, "plain", "utf-8")
    msg["From"] = formataddr((str(Header("SteamPY 价格监控", "utf-8")), sender))
    msg["To"] = formataddr((str(Header("收件人", "utf-8")), receiver))
    msg["Subject"] = Header(subject, "utf-8")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30, context=ctx) as server:
        server.login(sender, auth_code)
        server.sendmail(sender, [receiver], msg.as_string())
