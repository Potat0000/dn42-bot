import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BOT_TOKEN = "XXXXX:XXXXXXXXXXXXXXXXXXX"
CONTACT = "@Potat00000"
DN42_ASN = 4242421816

WELCOME_TEXT = (
    f"Hello, I'm the bot for Potat0's DN42 Network (`AS{DN42_ASN}`).\n"
    f"你好，我是 Potat0 (`AS{DN42_ASN}`) 的 DN42 机器人。\n"
    "\n"
    "For more information, please check: 更多信息请查看：\n"
    "https://dn42.potat0.cc/\n"
)

WHOIS_ADDRESS = "127.0.0.1"
DN42_ONLY = False
ALLOW_NO_CLEARNET = True

# API settings
ENDPOINT = "dn42.domain.tld"  # Also used for tunnel
API_PORT = 54321
API_TOKEN = "secret_token"
SERVERS = {
    "las": "LAS | Las Vegas, USA | BuyVM",
    "hkg": "HKG | Hong Kong | Skywolf",
    "trf": "TRF | Sandefjord, Norway | Gigahost",
}
HOSTS = {
    "las": "192.168.1.1",
    "hkg": "hkg.domain.tld",
}

# Webhook settings
WEBHOOK_URL = ""
WEBHOOK_LISTEN_HOST = "127.0.0.1"
WEBHOOK_LISTEN_PORT = 3443

# Optional settings
LG_DOMAIN = "https://lg.dn42.domain.tld"
PRIVILEGE_CODE = "123456"
SINGLE_PRIVILEGE = False
CN_WHITELIST_IP = ["8.8.8.8", "2001:4860:4860::8888"]
SENTRY_DSN = None


# Email-sending function
def send_email(asn, mnt, code, email):
    text = (
        f"Hi {mnt} (AS{asn}),\n"
        "\n"
        "Welcome to my DN42 Network.\n"
        "\n"
        f"Here is your code: {code}\n"
        "\n"
        "Have fun!\n"
    )
    try:
        mimemsg = MIMEMultipart()
        mimemsg["From"] = "My DN42<no-reply@mydomain.tld>"
        mimemsg["To"] = f"{mnt}<{email}>"
        mimemsg["Subject"] = "Verification Code"
        mimemsg.attach(MIMEText(text, "plain"))
        connection = smtplib.SMTP(host="smtp.office365.com", port=587)
        connection.starttls()
        connection.login("no-reply@mydomain.tld", "secret_password")
        connection.send_message(mimemsg)
        connection.quit()
    except BaseException:
        raise RuntimeError
