import json
from datetime import datetime, timezone
from uuid import uuid4

import base
import config
import tools
from base import bot
from expiringdict import ExpiringDict
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

PAGE_SIZE = 15


cache = ExpiringDict(max_len=20, max_age_seconds=259200)


def get_blocked_text(data_id, node, page=0, rank_by_time=False):
    data = cache.get(data_id)
    if not data or node not in data:
        return 'Cache expired. Please try again.\n缓存已过期，请重试。'
    blocked_asns = data[node]
    if isinstance(blocked_asns, str):
        return blocked_asns
    if not blocked_asns:
        return 'No blocked ASNs\n无封禁ASN'
    msg = ''
    if rank_by_time and len(blocked_asns) >= 3:
        key_func = lambda x: -x[1]   # noqa: E731
    else:
        key_func = lambda x: x[0]   # noqa: E731
    blocked_asns = sorted([(asn, time, name) for asn, (time, name) in blocked_asns.items()], key=key_func)
    blocked_asns = blocked_asns[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    for asn, time, name in blocked_asns:
        time_str = datetime.fromtimestamp(time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        msg += f'- AS{asn:<10} {name}\n  {time_str}\n'
    return msg.strip()


def gen_blocked_markup(data_id, node, page=0, rank_by_time=False):
    markup = InlineKeyboardMarkup()
    data = cache.get(data_id)
    if not data or node not in data:
        return ReplyKeyboardRemove()
    blocked_asns = data[node]
    blocked_num = len(blocked_asns) if isinstance(blocked_asns, dict) else 0
    if blocked_num > PAGE_SIZE:
        if page == 0:
            markup.row(
                InlineKeyboardButton(' ', callback_data=' '),
                InlineKeyboardButton(str(page + 1), callback_data=' '),
                InlineKeyboardButton('➡️', callback_data=f'blocked_{data_id}_{node}_1_{int(rank_by_time)}'),
            )
        elif page == (blocked_num - 1) // PAGE_SIZE:
            markup.row(
                InlineKeyboardButton('⬅️', callback_data=f'blocked_{data_id}_{node}_{page - 1}_{int(rank_by_time)}'),
                InlineKeyboardButton(str(page + 1), callback_data=' '),
                InlineKeyboardButton(' ', callback_data=' '),
            )
        else:
            markup.row(
                InlineKeyboardButton('⬅️', callback_data=f'blocked_{data_id}_{node}_{page - 1}_{int(rank_by_time)}'),
                InlineKeyboardButton(str(page + 1), callback_data=' '),
                InlineKeyboardButton('➡️', callback_data=f'blocked_{data_id}_{node}_{page + 1}_{int(rank_by_time)}'),
            )
    if blocked_num >= 3:
        if rank_by_time:
            markup.row(
                InlineKeyboardButton('Rank by ASN', callback_data=f'blocked_{data_id}_{node}_0_0'),
                InlineKeyboardButton('✅ Rank by Time', callback_data=f'blocked_{data_id}_{node}_0_1'),
            )
        else:
            markup.row(
                InlineKeyboardButton('✅ Rank by ASN', callback_data=f'blocked_{data_id}_{node}_0_0'),
                InlineKeyboardButton('Rank by Time', callback_data=f'blocked_{data_id}_{node}_0_1'),
            )
    for n in data.keys():
        selected = '✅ ' if n == node else ''
        markup.row(
            InlineKeyboardButton(
                f'{selected}{base.servers[n]}', callback_data=f'blocked_{data_id}_{n}_0_{int(rank_by_time)}'
            )
        )
    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith('blocked_'))
def blocked_callback_query(call):
    choice = call.data.split('_', 4)[1:5]
    data_id, node = choice[0], choice[1]
    choice[2] = int(choice[2])
    choice[3] = bool(int(choice[3]))
    blocked_text = get_blocked_text(data_id, node, choice[2], choice[3])
    try:
        bot.edit_message_text(
            f'```BlockedASNs-{node.upper()}\n{blocked_text}```',
            parse_mode='Markdown',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=gen_blocked_markup(data_id, node, choice[2], choice[3]),
        )
    except BaseException:
        pass


@bot.message_handler(commands=['blocked', 'banned', 'baned'])
def get_blocked(message, nodes=None):
    if not base.servers:
        bot.send_message(
            message.chat.id,
            f'No available nodes. Please contact {config.CONTACT}\n当前无可用节点，请联系 {config.CONTACT}',
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:
        available_server = [j.lower() for j in base.servers.keys()]
        if nodes is None:
            nodes = [i.lower() for i in message.text.split()[1:]]
        if not nodes:
            raise RuntimeError()
        specific_server = [i for i in available_server if i in nodes]
        if not specific_server:
            specific_server = [i for i in available_server if any(i.startswith(k) for k in nodes)]
        if not specific_server:
            raise RuntimeError()
    except BaseException:
        specific_server = list(base.servers.keys())
    result = tools.get_from_agent('get_blocked', None, specific_server)
    data = {}
    for k, v in result.items():
        if v.status == 200:
            data[k] = json.loads(v.text)
        elif v.status == 500:
            data[k] = 'Blacklist parse error'
        else:
            data[k] = f'Error {v.status}'
    data_id = str(uuid4()).replace('-', '')
    cache[data_id] = data
    node = specific_server[0]
    text = get_blocked_text(data_id, node)
    bot.send_message(
        message.chat.id,
        f'```BlockedASNs-{node.upper()}\n{text}```',
        parse_mode='Markdown',
        reply_markup=gen_blocked_markup(data_id, node),
    )
