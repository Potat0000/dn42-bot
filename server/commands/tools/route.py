# -*- coding: utf-8 -*-

import config
import tools
from base import bot


@bot.message_handler(commands=['route', 'route4', 'route6'])
def route(message):
    if len(message.text.strip().split(" ")) < 2:
        bot.reply_to(
            message,
            "Usage: /route [ip/domain]\n用法：/route [ip/domain]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    parsed_info = tools.test_ip_domain(message.text.strip().split(" ")[1])
    if not parsed_info:
        bot.reply_to(
            message,
            "IP is incorrect or domain can'no't be resolved\nIP 不正确或域名无法被解析",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    if config.DN42_ONLY and not parsed_info.dn42:
        bot.reply_to(
            message,
            "IP/Domain not in DN42\nIP/域名不属于 DN42",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    if message.text.strip().split(" ")[0].endswith("4"):
        if parsed_info.ipv4:
            ip = parsed_info.ipv4
        else:
            bot.reply_to(
                message,
                "Not IPv4 address or domain can't resolve IPv4 record\n不是 IPv4 地址或域名无法解析出 IPv4 记录",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
    elif message.text.strip().split(" ")[0].endswith("6"):
        if parsed_info.ipv6:
            ip = parsed_info.ipv6
        else:
            bot.reply_to(
                message,
                "Not IPv6 address or domain can't resolve IPv6 record\n不是 IPv6 地址或域名无法解析出 IPv6 记录",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
    else:
        ip = parsed_info.ipv4 if parsed_info.ipv4 else parsed_info.ipv6
    msg = bot.reply_to(
        message,
        "```\nRoute to {ip}{domain} ...\n```".format(
            ip=ip,
            domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
        ),
        parse_mode="Markdown",
        reply_markup=tools.gen_peer_me_markup(message),
    )
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    raw = tools.get_from_agent('route', ip)
    try:
        specific_server = [i.lower() for i in message.text.strip().split(" ")[2:]]
        raw_new = {k: v for k, v in raw.items() if k in specific_server}
        if raw_new:
            raw = raw_new
    except (IndexError, KeyError):
        pass
    output = []
    for k, v in raw.items():
        if v.status == 200:
            output.append("{server}\n```\n{text}```".format(server=config.SERVER[k], text=v.text.strip()))
        elif v.status == 408:
            output.append(f"{config.SERVER[k]}\n```\nRequest Timeout 请求超时```")
        else:
            output.append(f"{config.SERVER[k]}\n```\nSomething went wrong.\n发生了一些错误。```")
    output = "\n\n".join(output)
    bot.edit_message_text(
        output,
        parse_mode="Markdown",
        chat_id=message.chat.id,
        message_id=msg.message_id,
        reply_markup=tools.gen_peer_me_markup(message),
    )
