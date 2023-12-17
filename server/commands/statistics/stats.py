# -*- coding: utf-8 -*-
import tools
from base import bot, db


@bot.message_handler(commands=['stats'])
def stats(message):
    try:
        asn = int(message.text.split()[1])
    except (ValueError, IndexError):
        if message.chat.type == 'private' and message.chat.id in db:
            asn = db[message.chat.id]
        else:
            bot.reply_to(
                message,
                "Usage: /stats [asn]\n用法：/stats [asn]",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
    data = tools.get_map()[1]
    if not data:
        bot.reply_to(
            message,
            'No data available.\n暂无数据。',
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    asn_list = [asn]
    if asn < 10000:
        asn_list.append(4242420000 + asn)
        asn_list.append(asn)
    elif 20000 <= asn < 30000:
        asn_list.append(4242400000 + asn)
        asn_list.append(asn)
    for asn in asn_list:
        mnt = tools.get_whoisinfo_by_asn(asn)
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
        if not centrality == closeness == betweenness == peer == "N/A":
            break
    msg = (
        f'asn          {asn}\n'
        f'mnt          {mnt}\n'
        f'centrality   {centrality}\n'
        f'closeness    {closeness}\n'
        f'betweenness  {betweenness}\n'
        f'peer count   {peer}\n'
    )
    bot.reply_to(
        message,
        f'```\n{msg}```',
        parse_mode='Markdown',
        reply_markup=tools.gen_peer_me_markup(message),
    )
