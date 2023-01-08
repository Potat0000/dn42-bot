# -*- coding: utf-8 -*-

import config
import tools
from base import bot


@bot.message_handler(commands=['ping', 'trace', 'traceroute', 'tracert'])
def ping_trace(message):
    command = message.text.strip().split(" ")
    if len(command) < 2:
        bot.reply_to(
            message,
            f"Usage: /{command} [ip/domain]\n用法：/{command} [ip/domain]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    parsed_info = tools.test_ip_domain(command[1])
    command = command[0].split('@')[0][1:]
    if not parsed_info:
        bot.reply_to(message, "IP/Domain is wrong\nIP/域名不正确", reply_markup=tools.gen_peer_me_markup(message))
        return
    if config.DN42_ONLY and not parsed_info.dn42:
        bot.reply_to(
            message,
            "IP/Domain not in DN42\nIP/域名不属于 DN42",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    if not parsed_info.ip:
        bot.reply_to(message, "Domain can't be resolved 域名无法被解析", reply_markup=tools.gen_peer_me_markup(message))
        return
    msg = bot.reply_to(
        message,
        "```\n{command_text} {ip}{domain} ...\n```".format(
            command_text="Ping" if command == "ping" else "Traceroute",
            ip=parsed_info.ip,
            domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
        ),
        parse_mode="Markdown",
        reply_markup=tools.gen_peer_me_markup(message),
    )
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    raw = tools.get_from_agent('ping' if command == "ping" else "trace", parsed_info.raw)
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
