import shlex
import string
import subprocess

import config
import tools
from base import bot
import json


@bot.message_handler(commands=['whois'])
def whois(message):
    if len(message.text.split()) < 2:
        bot.reply_to(
            message,
            "Usage: /whois [something]\n用法：/whois [something]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    whois_str = message.text.split()[1]
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
    whois_command = f"whois -h {config.WHOIS_ADDRESS} {whois_str}"
    while True:
        try:
            whois_result = (
                subprocess.run(
                    shlex.split(whois_command),
                    stdout=subprocess.PIPE,
                    timeout=3,
                )
                .stdout.decode("utf-8")
                .strip()
            )
        except BaseException:
            whois_result = 'Something went wrong.\n发生了一些错误。'
            break
        if len(whois_result.split('\n')) > 1 and '% 404' not in whois_result:
            break
        try:
            asn = int(whois_str)
            if asn < 10000:
                whois_str = f"AS424242{asn:04d}"
            elif 20000 <= asn < 30000:
                whois_str = f"AS42424{asn}"
            else:
                whois_str = f"AS{asn}"
            whois_command = f"whois -h {config.WHOIS_ADDRESS} {whois_str}"
        except ValueError:
            whois_command = f"whois -I {message.text.split()[1]}"
        whois_result = ''
    route_result = ""
    if whois_str.startswith('AS') and whois_result.startswith('% This is the dn42 whois query service.'):
        try:
            int(whois_str[2:])
            with open(config.ROA_PATH, 'r') as f:
                roas = json.loads(f.read())
            roas = roas['roas']
            for r in sorted([roa['prefix'] for roa in roas if roa['asn'] == whois_str]):
                ipver = '6' if ':' in r else '4'
                route_result += f"route{ipver}:             {r}\n"
        except BaseException:
            pass
    if route_result:
        whois_result += "\n\n" f"% Routes for '{whois_str}':\n" f"{route_result.strip()}"
    if len(whois_result) > 4096:
        whois_result = f"```WhoisResult\n{whois_result[:4000]}```\n\n消息过长，已被截断。\nMessage too long, truncated."
    else:
        whois_result = f"```WhoisResult\n{whois_result}```"
    bot.reply_to(
        message,
        whois_result,
        parse_mode="Markdown",
        reply_markup=tools.gen_peer_me_markup(message),
    )
