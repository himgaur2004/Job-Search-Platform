import requests
import socket

domain = "mastercard.wd1.myworkdayjobs.com"
try:
    ip = socket.gethostbyname(domain)
    print(f"{domain} resolves to {ip}")
except Exception as e:
    print(e)
