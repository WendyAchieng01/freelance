# tasks.py
from django.core.mail import EmailMultiAlternatives
from django.utils.html import format_html
from celery import shared_task


@shared_task
def send_verification_email(username, email_address, verification_url):
    subject = 'Verify Your Email Address'
    message_text = f'Hi {username},\n\nPlease click the link to verify your email: {verification_url}'
    message_html = format_html(
        '<div style="font-family: Arial, sans-serif; text-align: center;">'
        f'<h2>Welcome, {username}!</h2>'
        '<p>Please click the button below to verify your email address:</p>'
        f'<a href="{verification_url}" style="display: inline-block; background-color: #28a745; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">'
        'Verify Email</a><p>If you didn\'t sign up, ignore this email.</p>'
        '</div>'
    )
    email = EmailMultiAlternatives(
        subject, message_text, 'info@nilltechsolutions.com', [email_address])
    email.attach_alternative(message_html, "text/html")
    email.send()
