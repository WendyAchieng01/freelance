# utils.py
import os
from disposable_email_domains import blocklist


def is_disposable_email(email):
    domain = email.split('@')[-1].lower()
    return domain in blocklist
