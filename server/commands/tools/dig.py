# -*- coding: utf-8 -*-

import shlex
import subprocess

import tools
from base import bot


@bot.message_handler(commands=['dig', 'nslookup'])
def dig(message):
    if len(message.text.split()) != 2:
        bot.reply_to(
            message,
            "Usage: /dig [domain]\n用法：/dig [domain]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    dig_str = message.text.split()[1]
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    dig_command = f"dig +noall +answer +comments +multiline {dig_str} ANY"
    try:
        dig_result = (
            subprocess.run(
                shlex.split(dig_command),
                stdout=subprocess.PIPE,
                timeout=5,
            )
            .stdout.decode("utf-8")
            .strip()
        )
    except BaseException:
        dig_result = 'Something went wrong.\n发生了一些错误。'
    if len(dig_result) > 4096:
        dig_result = f"```DigResult\n{dig_result[:4000]}```\n\n消息过长，已被截断。\nMessage too long, truncated."
    elif not dig_result:
        dig_result = 'No result.\n没有结果。'
    else:
        dig_result = f"```DigResult\n{dig_result}```"
    bot.reply_to(
        message,
        dig_result,
        parse_mode="Markdown",
        reply_markup=tools.gen_peer_me_markup(message),
    )
