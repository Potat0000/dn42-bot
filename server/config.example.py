import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BOT_TOKEN = "XXXXX:XXXXXXXXXXXXXXXXXXX"
BOT_USERNAME = "Potat0_DN42_Bot"
CONTACT = "@Potat0_PM_Bot"
DN42_ASN = 4242421816

WELCOME_TEXT = (
    f"Hello, I'm the bot for Potat0's DN42 Network (<code>AS{DN42_ASN}</code>).\n"
    f"你好，我是 Potat0 (<code>AS{DN42_ASN}</code>) 的 DN42 机器人。\n"
    "\n"
    "For more information, please check: 更多信息请查看：\n"
    "https://dn42.potat0.cc/\n"
)

# API settings
ENDPOINT = "dn42.domain.tld"  # Also used for tunnel
API_PORT = 54321
API_TOKEN = "secret_token"
SERVER = {'us1': 'US1 | New York - BuyVM', 'jp1': 'JP1 | Tokyo - AWS'}

# Webhook settings
WEBHOOK_URL = 'https://bot.dn42.domain.tld/'
WEBHOOK_LISTEN_HOST = '127.0.0.1'
WEBHOOK_LISTEN_PORT = 3443

# Optional settings
LG_DOMAIN = 'https://lg.dn42.domain.tld'
PRIVILEGE_CODE = "123456"
SINGLE_PRIVILEGE = False


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
        mimemsg['From'] = "My DN42<no-reply@mydomain.tld>"
        mimemsg['To'] = f"{mnt}<{email}>"
        mimemsg['Subject'] = "Verification Code"
        mimemsg.attach(MIMEText(text, 'plain'))
        connection = smtplib.SMTP(host='smtp.office365.com', port=587)
        connection.starttls()
        connection.login("no-reply@mydomain.tld", "secret_password")
        connection.send_message(mimemsg)
        connection.quit()
    except BaseException:
        raise RuntimeError
