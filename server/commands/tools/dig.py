import shlex
import subprocess
from ipaddress import IPv4Network, IPv6Network, ip_address

import tools
from base import bot
from config import DN42_ONLY
from punycode import convert as punycode


@bot.message_handler(commands=["dig", "nslookup"])
def dig(message):
    dig_type_whitelist = ["ANY", "A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "SRV", "PTR"]
    help_text = ", ".join(f"`{i}`" for i in dig_type_whitelist)
    help_text = (
        "Usage: /dig [domain] {type} {@dns\\_server}\n"
        "用法：/dig [domain] {type} {@dns\\_server}\n\n"
        "Only accept following types\n"
        "只接受以下类型的查询\n"
        f"{help_text}"
    )
    raw = message.text.split()[1:]
    if len(raw) == 0 or len(raw) > 3:
        bot.reply_to(
            message,
            help_text,
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    dig_server = ""
    dig_type = "ANY"
    try:
        t = [i for i in raw if i.startswith("@")]
        if len(t) > 1:
            raise RuntimeError
        elif len(t) == 1:
            dig_server = t[0]
            raw.remove(dig_server)
            dig_server = dig_server[1:].strip()
        t = [i for i in raw if "." not in i]
        if len(t) > 1:
            raise RuntimeError
        elif len(t) == 1:
            dig_type = t[0]
            raw.remove(dig_type)
            dig_type = dig_type.strip().upper()
        if len(raw) != 1:
            raise RuntimeError
        else:
            dig_target = raw[0].strip()
    except BaseException:
        bot.reply_to(
            message,
            help_text,
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    if dig_server:
        try:
            t = ip_address(dig_server)
        except BaseException:
            bot.reply_to(
                message,
                "Invalid DNS server.\n无效的 DNS 服务器。",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
        if DN42_ONLY and not any(
            t in n
            for n in [
                IPv4Network("172.20.0.0/14"),
                IPv4Network("10.127.0.0/16"),
                IPv6Network("fc00::/7"),
            ]
        ):
            bot.reply_to(
                message,
                "Only accept DN42 DNS server.\n只接受 DN42 DNS 服务器。",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
        dig_server = f" @{dig_server}"
    try:
        dig_target = punycode(dig_target, ascii_only=True)
    except BaseException:
        bot.reply_to(
            message,
            "Invalid domain.\n无效的域名。",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    if DN42_ONLY and not dig_target.endswith(".dn42"):
        bot.reply_to(
            message,
            "Only accept `.dn42` domain.\n只接受 `.dn42` 域名。",
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    if dig_type not in dig_type_whitelist:
        bot.reply_to(
            message,
            help_text,
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action="typing")
    dig_command = f"dig +noall +answer +comments +multiline {dig_target} {dig_type}{dig_server}"
    try:
        dig_result = (
            subprocess.run(
                shlex.split(dig_command),
                stdout=subprocess.PIPE,
                timeout=8,
            )
            .stdout.decode("utf-8")
            .strip()
        )
    except subprocess.TimeoutExpired:
        dig_result = "Request timeout.\n请求超时。"
    except BaseException:
        dig_result = "Something went wrong.\n发生了一些错误。"
    if not dig_result:
        dig_result = "No result.\n没有结果。"
    if len(dig_result) > 4000:
        dig_result = tools.split_long_msg(dig_result)
        last_msg = message
        for index, m in enumerate(dig_result):
            if index < len(dig_result) - 1:
                last_msg = bot.reply_to(
                    last_msg,
                    f"```DigResult\n{m}```To be continued...",
                    parse_mode="Markdown",
                    reply_markup=tools.gen_peer_me_markup(message),
                )
            else:
                bot.reply_to(
                    last_msg,
                    f"```DigResult\n{m}```",
                    parse_mode="Markdown",
                    reply_markup=tools.gen_peer_me_markup(message),
                )
    else:
        bot.reply_to(
            message,
            f"```DigResult\n{dig_result}```",
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
