# -*- coding: utf-8 -*-
import tools
from base import bot
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=['peer_list', 'peerlist'])
def route(message):
    try:
        asn = int(message.text.strip().split(" ")[1])
    except (ValueError, IndexError):
        command = message.text.strip().split(" ")[0]
        bot.reply_to(
            message,
            f"Usage: /{command} [asn]\n用法：/{command} [asn]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    peer_map = tools.get_map()[2]
    if asn not in peer_map:
        bot.reply_to(
            message,
            'No data available.\n暂无数据。',
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    msg = ''
    for peer_asn in sorted(peer_map[asn]):
        msg += f"{peer_asn:<10}  {tools.get_mnt_by_asn(peer_asn)}\n"
    bot.reply_to(
        message,
        f'```\n{msg}```',
        parse_mode='Markdown',
        reply_markup=tools.gen_peer_me_markup(message),
    )
