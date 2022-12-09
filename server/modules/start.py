# -*- coding: utf-8 -*-
from base import bot
from modules.help import send_welcome
from modules.info import get_info
from modules.whoami import whoami
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=['start'], is_for_me=True, is_private_chat=True)
def startup(message):
    try:
        if message.text.strip().split(" ")[1] == "peer":
            bot.send_message(
                message.chat.id,
                "Use /peer to create a Peer with me!\n使用 /peer 与我建立 Peer！",
                reply_markup=ReplyKeyboardRemove(),
            )
        elif message.text.strip().split(" ")[1].startswith("whoami_"):
            whoami(message, message.text.strip().split(" ")[1][7:])
        elif message.text.strip().split(" ")[1] == 'info':
            get_info(message)
    except BaseException:
        send_welcome(message)
