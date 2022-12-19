# -*- coding: utf-8 -*-
import tools
from base import bot
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=['stats'])
def route(message):
    try:
        asn = int(message.text.strip().split(" ")[1])
    except (ValueError, IndexError):
        bot.reply_to(
            message,
            "Usage: /stats [asn]\n用法：/stats [asn]",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    data = tools.get_map()[1]
    if not data:
        bot.send_message(
            message.chat.id, 'No data available.\n暂无数据。', parse_mode='Markdown', reply_markup=tools.gen_peer_me_markup(message)
        )
        return
    mnt = tools.get_mnt_by_asn(asn)
    try:
        centrality = next(i for i in data['jerry'] if i[1] == asn)
        centrality = f'{centrality[3]:.4f}  #{centrality[0]}'
    except StopIteration:
        centrality = "N/A"
    try:
        closeness = next(i for i in data['closeness'] if i[1] == asn)
        closeness = f'{closeness[3]:.5f}  #{closeness[0]}'
    except StopIteration:
        closeness = "N/A"
    try:
        betweenness = next(i for i in data['betweenness'] if i[1] == asn)
        betweenness = f'{betweenness[3]:.5f}  #{betweenness[0]}'
    except StopIteration:
        betweenness = "N/A"
    try:
        peer = next(i for i in data['peer'] if i[1] == asn)
        peer = f'{str(peer[3]).ljust(7)}  #{peer[0]}'
    except StopIteration:
        peer = "N/A"
    msg = (
        f'asn          {asn}\n'
        f'mnt          {mnt}\n'
        f'centrality   {centrality}\n'
        f'closeness    {closeness}\n'
        f'betweenness  {betweenness}\n'
        f'peer count   {peer}\n'
    )
    bot.send_message(message.chat.id, f'```\n{msg}```', parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
