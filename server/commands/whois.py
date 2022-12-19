# -*- coding: utf-8 -*-

import shlex
import string
import subprocess

import config
import tools
from base import bot


@bot.message_handler(commands=['whois'])
def whois(message):
    if len(message.text.strip().split(" ")) != 2:
        bot.reply_to(
            message,
            "Usage: /whois [something]\n用法：/whois [something]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    whois_str = message.text.strip().split(" ")[1]
    allowed_punctuation = "_-./:"
    if any(c not in (string.ascii_letters + string.digits + allowed_punctuation) for c in whois_str):
        bot.reply_to(
            message,
            (
                "Invalid input.\n"
                "输入无效\n"
                "\n"
                "Only non-empty strings which contain only upper and lower case letters, numbers, spaces and the following special symbols are accepted.\n"
                "只接受仅由大小写英文字母、数字、空格及以下特殊符号组成的非空字符串。\n"
                f"`{allowed_punctuation}`\n"
            ),
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    try:
        whois_result = (
            subprocess.check_output(shlex.split(f"whois -h {config.WHOIS_ADDRESS} {whois_str}"), timeout=3)
            .decode("utf-8")
            .strip()
        )
    except BaseException:
        whois_result = 'Something went wrong.\n发生了一些错误。'
    bot.reply_to(
        message,
        f"```\n{whois_result}```",
        parse_mode="Markdown",
        reply_markup=tools.gen_peer_me_markup(message),
    )
