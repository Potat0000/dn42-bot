# -*- coding: utf-8 -*-

from uuid import uuid4

import base
import config
import tools
from base import bot, db, db_privilege
from expiringdict import ExpiringDict
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

cache = ExpiringDict(max_len=500, max_age_seconds=259200)


def gen_generaltest_markup(chat, data_id, node, available_nodes):
    markup = InlineKeyboardMarkup()
    for n in available_nodes:
        if n == node:
            markup.row(InlineKeyboardButton(f'✅ {base.servers[n]}', callback_data=f"generaltest_{data_id}_{n}"))
        else:
            markup.row(InlineKeyboardButton(base.servers[n], callback_data=f"generaltest_{data_id}_{n}"))
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
    available_nodes = list(text.keys())
    text = text[node]
    try:
        bot.edit_message_text(
            f'```Result\n{text.strip()}\n```',
            parse_mode='Markdown',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=gen_generaltest_markup(call.message.chat, data_id, node, available_nodes),
        )
    except BaseException:
        pass


@bot.message_handler(
    commands=[
        'ping',
        'ping4',
        'ping6',
        'trace',
        'trace4',
        'trace6',
        'route',
        'route4',
        'route6',
        'tcping',
        'tcping4',
        'tcping6',
        'path',
    ]
)
def generaltest(message):
    command = message.text.split()
    if len(command) < 2:
        command = command[0].split('@')[0][1:]
        if command.endswith("4") or command.endswith("6"):
            cmd = command[:-1]
        else:
            cmd = command
        if command != 'path':
            cmd = command + '{4|6}'
        addon = ""
        if cmd == 'tcping':
            addon = " {port}"
        bot.reply_to(
            message,
            (
                f"Usage: /{cmd} [ip/domain]{addon} {{node1}} {{node2}} ...\n"
                f"用法：/{cmd} [ip/domain]{addon} {{node1}} {{node2}} ..."
            ),
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
    if not base.servers:
        bot.send_message(
            message.chat.id,
            f"No available nodes. Please contact {config.CONTACT}\n当前无可用节点，请联系 {config.CONTACT}",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove(),
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
    server_list = message.text.split()[2:]
    command_data = ip
    addon = ""
    if command == 'ping':
        command_text = 'Ping'
    elif command == 'tcping':
        command_text = 'TCPing'
        try:
            if 0 < int(server_list[0]) < 65535:
                addon = f" Port {server_list[0]}"
                command_data = f"{ip} {server_list[0]}"
                server_list = server_list[1:]
        except BaseException:
            pass
    elif command == 'trace':
        command_text = 'Traceroute'
    elif command == 'route':
        command_text = 'Route to'
    elif command == 'path':
        command_text = 'AS-Path of'
    msg = bot.reply_to(
        message,
        "```Querying\n{command_text} {ip}{domain}{addon}...\n```".format(
            command_text=command_text,
            ip=ip,
            domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
            addon=addon,
        ),
        parse_mode="Markdown",
    )
    bot.send_chat_action(chat_id=message.chat.id, action='typing', timeout=20 if command == 'trace' else 10)
    try:
        specific_server = [i.lower() for i in server_list if i.lower() in base.servers]
        if not specific_server:
            raise RuntimeError()
    except BaseException:
        specific_server = list(base.servers.keys())
    raw = tools.get_from_agent(command, command_data, specific_server)
    data = {}
    for k, v in raw.items():
        if v.status == 200:
            if command == 'ping':
                if v.text.strip().startswith("PING "):
                    text = "Ping {ip}{domain} 56 data bytes\n".format(
                        ip=ip,
                        domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
                    )
                    text += v.text.strip().split("\n", 1)[1]
                else:
                    text = v.text.strip()
            elif command == 'tcping':
                text = "TCPing {ip}{domain}{addon}\n".format(
                    ip=ip,
                    domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
                    addon=addon,
                )
                text += v.text.strip()
            elif command == 'trace':
                if v.text.strip().startswith("traceroute to "):
                    text = "Traceroute to {ip}{domain}, 30 hops max, 80 byte packets\n".format(
                        ip=ip,
                        domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
                    )
                    text += v.text.strip().split("\n", 1)[1]
                else:
                    text = v.text.strip()
            elif command == 'route' or command == 'path':
                text = v.text.strip()
                if text.startswith("BIRD "):
                    text = v.text.strip().split("\n", 1)[1]
            data[k] = text
        elif v.status == 408:
            data[k] = 'Request Timeout 请求超时'
        elif command == 'path' and v.status == 404:
            data[k] = 'Not found 未找到'
        else:
            data[k] = 'Something went wrong.\n发生了一些错误。'
    data_id = str(uuid4()).replace('-', '')
    cache[data_id] = data
    node = specific_server[0]
    text = data[node]
    bot.edit_message_text(
        f'```Result\n{text.strip()}\n```',
        parse_mode="Markdown",
        chat_id=message.chat.id,
        message_id=msg.message_id,
        reply_markup=gen_generaltest_markup(message.chat, data_id, node, specific_server),
    )
