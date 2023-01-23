# -*- coding: utf-8 -*-

from uuid import uuid4

import config
import tools
from base import bot, db, db_privilege
from expiringdict import ExpiringDict
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

cache = ExpiringDict(max_len=500, max_age_seconds=259200)


def gen_generaltest_markup(chat, data_id, node):
    markup = InlineKeyboardMarkup()
    for k, v in config.SERVER.items():
        if k == node:
            markup.row(InlineKeyboardButton(f'✅ {v}', callback_data=f"generaltest_{data_id}_{k}"))
        else:
            markup.row(InlineKeyboardButton(v, callback_data=f"generaltest_{data_id}_{k}"))
    if chat.id in db_privilege:
        return markup
    if chat.type == "private" and chat.id in db:
        if tools.get_info(db[chat.id]):
            return markup
    markup.row(InlineKeyboardButton("Peer with me | 与我 Peer", url=f"https://t.me/{config.BOT_USERNAME}"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith("generaltest_"))
def generaltest_callback_query(call):
    data_id = call.data.split("_", 2)[1]
    node = call.data.split("_", 2)[2]
    text = cache.get(data_id)
    if text is None:
        bot.edit_message_text(
            'The result is expired, please run it again.\n结果已失效，请重新运行。',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=tools.gen_peer_me_markup(call.message),
        )
        return
    text = text[node]
    try:
        bot.edit_message_text(
            f'```\n{text.strip()}\n```',
            parse_mode='Markdown',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=gen_generaltest_markup(call.message.chat, data_id, node),
        )
    except BaseException:
        pass


@bot.message_handler(commands=['ping', 'ping4', 'ping6', 'trace', 'trace4', 'trace6', 'route', 'route4', 'route6'])
def generaltest(message):
    command = message.text.strip().split(" ")
    if len(command) < 2:
        command = command[0].split('@')[0][1:]
        if command.endswith("4") or command.endswith("6"):
            cmd = command[:-1]
        else:
            cmd = command
        bot.reply_to(
            message,
            f"Usage: /{cmd}{{4|6}} [ip/domain]\n用法：/{cmd}{{4|6}} [ip/domain] {{node1}} {{node2}} ...",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    parsed_info = tools.test_ip_domain(command[1])
    command = command[0].split('@')[0][1:]
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
    if command.endswith("4"):
        command = command[:-1]
        if parsed_info.ipv4:
            ip = parsed_info.ipv4
        else:
            bot.reply_to(
                message,
                "Not IPv4 address or domain can't resolve IPv4 record\n不是 IPv4 地址或域名无法解析出 IPv4 记录",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
    if command.endswith("6"):
        command = command[:-1]
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
    if command == 'ping':
        command_text = 'Ping'
    elif command == 'trace':
        command_text = 'Traceroute'
    elif command == 'route':
        command_text = 'Route to'
    msg = bot.reply_to(
        message,
        "```\n{command_text} {ip}{domain} ...\n```".format(
            command_text=command_text,
            ip=ip,
            domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
        ),
        parse_mode="Markdown",
    )
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    raw = tools.get_from_agent(command, ip)
    try:
        specific_server = [i.lower() for i in message.text.strip().split(" ")[2:]]
        raw_new = {k: v for k, v in raw.items() if k in specific_server}
        if raw_new:
            raw = raw_new
    except (IndexError, KeyError):
        pass
    data = {}
    for k, v in raw.items():
        if v.status == 200:
            if command == 'ping':
                text = "Ping {ip}{domain} 56 data bytes\n".format(
                    ip=ip,
                    domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
                )
                text += '\n'.join(v.text.strip().split("\n")[1:])
            elif command == 'trace':
                text = "Traceroute to {ip}{domain}, 30 hops max, 80 byte packets\n".format(
                    ip=ip,
                    domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
                )
                text += '\n'.join(v.text.strip().split("\n")[1:])
            elif command == 'route':
                text = v.text.strip()
            data[k] = text
        elif v.status == 408:
            data[k] = 'Request Timeout 请求超时'
        else:
            data[k] = 'Something went wrong.\n发生了一些错误。'
    data_id = str(uuid4()).replace('-', '')
    cache[data_id] = data
    node = list(config.SERVER.keys())[0]
    text = data[node]
    bot.edit_message_text(
        f'```\n{text.strip()}\n```',
        parse_mode="Markdown",
        chat_id=message.chat.id,
        message_id=msg.message_id,
        reply_markup=gen_generaltest_markup(message.chat, data_id, node),
    )
