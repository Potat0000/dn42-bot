# -*- coding: utf-8 -*-
import time

import config
import tools
from base import bot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def gen_stats_markup(ip_ver, simple, node):
    markup = InlineKeyboardMarkup()
    if simple:
        simple_str = '1'
        markup.row(
            InlineKeyboardButton("To Detailed Mode | 显示详细模式", callback_data=f"stats_{ip_ver}_0_{node}"),
        )
    else:
        simple_str = '0'
        markup.row(
            InlineKeyboardButton("To Simple Mode | 显示简洁模式", callback_data=f"stats_{ip_ver}_1_{node}"),
        )
    if ip_ver == '4':
        markup.row(
            InlineKeyboardButton("✅ IPv4", callback_data=f"stats_4_{simple_str}_{node}"),
            InlineKeyboardButton("IPv6", callback_data=f"stats_6_{simple_str}_{node}"),
        )
    elif ip_ver == '6':
        markup.row(
            InlineKeyboardButton("IPv4", callback_data=f"stats_4_{simple_str}_{node}"),
            InlineKeyboardButton("✅ IPv6", callback_data=f"stats_6_{simple_str}_{node}"),
        )
    for k, v in config.SERVER.items():
        if k == node:
            markup.row(InlineKeyboardButton(f'✅ {v}', callback_data=f"stats_{ip_ver}_{simple_str}_{k}"))
        else:
            markup.row(InlineKeyboardButton(v, callback_data=f"stats_{ip_ver}_{simple_str}_{k}"))
    return markup


def get_stats_text(ip_ver, simple, node):
    data, update_time = tools.get_stats()
    if isinstance(data[node], dict):
        time_delta = int(time.time()) - update_time
        data = data[node][ip_ver]
        if data:
            total_routes = sum(i[2] for i in data)
            if simple:
                mnt_len = min(max(len(i[1]) for i in data), 14)
                msg = f"IPv{ip_ver} Preferred Route Count".center(22 + mnt_len) + '\n'
                msg += config.SERVER[node].center(22 + mnt_len) + '\n'
                msg += f'updated {time_delta}s ago'.rjust(22 + mnt_len) + '\n\n'
                msg += f"Rank {'ASN':10} {'MNT':{mnt_len}} Count"
            else:
                mnt_len = min(max(len(i[1]) for i in data), 20)
                msg = f"IPv{ip_ver} Preferred Route Count".center(33 + mnt_len) + '\n'
                msg += config.SERVER[node].center(33 + mnt_len) + '\n'
                msg += f'updated {time_delta}s ago'.rjust(33 + mnt_len) + '\n\n'
                msg += f"Rank  {'ASN':10}  {'MNT':{mnt_len}}  Count  Weight"

            rank_now = 0
            last_count = 0
            for index, (asn, mnt, count) in enumerate(data, 1):
                if count != last_count:
                    rank_now = index
                last_count = count
                if mnt == f'AS{asn}':
                    mnt = asn
                if len(mnt) > mnt_len:
                    mnt = mnt[: mnt_len - 3] + '...'
                if simple:
                    msg += f"\n{rank_now:>4} {asn:10} {mnt:{mnt_len}} {count:5}"
                else:
                    msg += f"\n{rank_now:>4}  {asn:10}  {mnt:{mnt_len}}  {count:5}  {count/total_routes:>6.2%}"
        else:
            max_len = max(len(config.SERVER[node]), 26)
            msg = f"IPv{ip_ver} Preferred Route Count".center(max_len) + '\n'
            msg += config.SERVER[node].center(max_len) + '\n'
            msg += f'updated {time_delta}s ago'.rjust(max_len) + '\n\n'
            msg += "No data available.".center(max_len) + '\n'
            msg += "暂无数据。".center(max_len)
        return f"```\n{msg}\n```", 'Markdown'
    else:
        return (
            f"Error encountered! Please contact {config.CONTACT} with the following information:\n"
            f"遇到错误！请携带下列信息联系 {config.CONTACT}\n\n"
            "```\n"
            f"{data[node]}\n"
            "```"
        ), 'HTML'


@bot.callback_query_handler(func=lambda call: call.data.startswith("stats_"))
def stats_callback_query(call):
    choice = call.data.split("_", 4)[1:4]
    choice[1] = bool(int(choice[1]))
    stats_text = get_stats_text(*choice)
    try:
        bot.edit_message_text(
            stats_text[0],
            parse_mode=stats_text[1],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=gen_stats_markup(*choice),
        )
    except BaseException:
        pass


@bot.message_handler(commands=['stats'], is_for_me=True)
def get_stats(message):
    init_arg = ('4', False, list(config.SERVER.keys())[0])
    stats_text = get_stats_text(*init_arg)
    bot.send_message(message.chat.id, stats_text[0], parse_mode=stats_text[1], reply_markup=gen_stats_markup(*init_arg))
