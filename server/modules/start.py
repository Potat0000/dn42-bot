# -*- coding: utf-8 -*-
from base import bot
from modules.help import send_welcome
from modules.info import get_info
from modules.whoami import whoami
from modules.peer import start_peer
from modules.login import start_login


@bot.message_handler(commands=['start'], is_private_chat=True)
def startup(message):
    try:
        command = message.text.strip().split(" ")[1]
        if command.startswith("whoami_"):
            whoami(message, message.text.strip().split(" ")[1][7:])
        elif command == 'info':
            get_info(message)
        elif command == 'login':
            start_login(message)
        elif command == 'peer':
            start_peer(message)
    except BaseException:
        send_welcome(message)
