# -*- coding: utf-8 -*-
import config
from base import bot
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=['help'], is_for_me=True, is_private_chat=True)
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        (
            f"{config.WELCOME_TEXT}"
            "\n"
            "Command List 指令列表:\n"
            "    Tools:\n"
            "        - /ping [ip/domain]\n"
            "        - /trace [ip/domain]\n"
            "    User Manage:\n"
            "        - /login - Login to verify your ASN 登录以验证你的 ASN\n"
            "        - /logout - Logout current logged ASN 退出当前登录的 ASN\n"
            "        - /whoami - Get current login user 获取当前登录用户\n"
            "    Peer:\n"
            "        - /peer - Set up a peer 设置一个 Peer\n"
            "        - /remove - Remove a peer 移除一个 Peer\n"
            "        - /info - Show your peer info and status 查看你的 Peer 信息及状态\n"
            "    Other:\n"
            "        - /stats - Show preferred routes ranking 显示优选 Routes 排名\n"
            "\n"
            "You can always use /cancel to interrupt current operation.\n"
            "你始终可以使用 /cancel 终止当前正在进行的操作。\n"
            "\n"
            f"When something unexpected happens or the bot can't meet your needs, please contact {config.CONTACT}\n"
            f"当出现了什么意料之外的，或者机器人无法满足你的需求，请联系 {config.CONTACT}"
        ),
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
