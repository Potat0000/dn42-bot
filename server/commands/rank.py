# -*- coding: utf-8 -*-
import time

import tools
from base import bot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


PAGE_SIZE = 30

rank_type_dict = {
    'jerry': 'Jerry-like',
    'peer': 'Peer count',
    'closeness': 'Closeness',
    'betweenness': 'Betweenness',
}


def gen_rank_markup(page, rank_type):
    markup = InlineKeyboardMarkup()
    total = len(tools.get_rank()[0]['peer'])
    last_page = (total - 1) // PAGE_SIZE
    if page == 0:
        markup.row(
            InlineKeyboardButton(" ", callback_data=' '),
            InlineKeyboardButton(str(page + 1), callback_data=' '),
            InlineKeyboardButton("➡️", callback_data=f"rank_1_{rank_type}"),
        )
    elif page == last_page:
        markup.row(
            InlineKeyboardButton("⬅️", callback_data=f"rank_{page-1}_{rank_type}"),
            InlineKeyboardButton(str(page + 1), callback_data=' '),
            InlineKeyboardButton(" ", callback_data=' '),
        )
    else:
        markup.row(
            InlineKeyboardButton("⬅️", callback_data=f"rank_{page-1}_{rank_type}"),
            InlineKeyboardButton(str(page + 1), callback_data=' '),
            InlineKeyboardButton("➡️", callback_data=f"rank_{page+1}_{rank_type}"),
        )
    for k, v in rank_type_dict.items():
        if k == rank_type:
            markup.row(InlineKeyboardButton(f'✅ {v}', callback_data=f"rank_0_{k}"))
        else:
            markup.row(InlineKeyboardButton(v, callback_data=f"rank_0_{k}"))
    return markup


def get_rank_text(page, rank_type):
    data, update_time = tools.get_rank()
    time_delta = int(time.time()) - update_time
    data = data[rank_type][PAGE_SIZE * page : PAGE_SIZE * (page + 1)]
    if data:
        mnt_len = 20
        #  59  65043       ICVPN-DREILAENDERECK     20
        #  29  4242421288  NICHONET-42            43
        msg = "DN42 Global Rank".center(25 + mnt_len) + '\n'
        msg += rank_type_dict[rank_type].center(25 + mnt_len) + '\n'
        msg += f'updated {time_delta}s ago'.rjust(25 + mnt_len) + '\n\n'
        msg += f"Rank  {'ASN':10}  {'MNT':{mnt_len}}  Value"
        for rank, asn, mnt, value in data:
            if len(mnt) > mnt_len:
                mnt = mnt[: mnt_len - 3] + '...'
            if isinstance(value, float):
                msg += f"\n{rank:>4}  {asn:<10}  {mnt:{mnt_len}} {value:.{5-len(str(int(value)))}f}"
            else:
                msg += f"\n{rank:>4}  {asn:<10}  {mnt:{mnt_len}} {value:>6}"
    else:
        max_len = max(len(rank_type_dict[rank_type]), 16)
        msg = "DN42 Global Rank".center(max_len) + '\n'
        msg += rank_type_dict[rank_type].center(max_len) + '\n'
        msg += f'updated {time_delta}s ago'.rjust(max_len) + '\n\n'
        msg += "No data available.".center(max_len) + '\n'
        msg += "暂无数据。".center(max_len)
    return f"```\n{msg}\n```", 'Markdown'


@bot.callback_query_handler(func=lambda call: call.data.startswith("rank_"))
def rank_callback_query(call):
    choice = call.data.split("_", 4)[1:3]
    choice[0] = int(choice[0])
    rank_text = get_rank_text(*choice)
    try:
        bot.edit_message_text(
            rank_text[0],
            parse_mode=rank_text[1],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=gen_rank_markup(*choice),
        )
    except BaseException:
        pass


@bot.message_handler(commands=['rank'])
def get_rank(message):
    init_arg = (0, 'jerry')
    rank_text = get_rank_text(*init_arg)
    bot.send_message(message.chat.id, rank_text[0], parse_mode=rank_text[1], reply_markup=gen_rank_markup(*init_arg))
