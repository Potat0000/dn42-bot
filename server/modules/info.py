# -*- coding: utf-8 -*-
from datetime import datetime, timezone

import config
import tools
from base import bot, db
from IPy import IP
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def basic_info(asn, endpoint, pubkey, v6, v4):
    text = (
        "    ASN:\n"
        f"        AS{asn}\n"
        "    Endpoint:\n"
        f"        {endpoint}\n"
        "    WireGuard Public Key:\n"
        f"        {pubkey}\n"
        "    DN42 Address:\n"
    )
    ipv6_space = ""
    try:
        if IP(v6) in IP("fc00::/7"):
            text += f"        IPv6 ULA: {v6}/128\n"
            ipv6_space = " " * 4
    except BaseException:
        pass
    try:
        if IP(v6) in IP("fe80::/64"):
            text += f"        IPv6 Link-Local: {v6}/64\n"
            ipv6_space = " " * 11
    except BaseException:
        pass
    try:
        if IP(v4) in IP("172.20.0.0/14"):
            text += f"        IPv4: {ipv6_space}{v4}/32\n"
    except BaseException:
        pass
    return text


def gen_info_markup(node, available_node, session_name):
    markup = InlineKeyboardMarkup()
    if config.LG_DOMAIN:
        if len(session_name) == 2:
            session_name = '_'.join(session_name[0].split('_')[:-1])
            url_prefix = f"{config.LG_DOMAIN}/detail/{node}/{session_name}"
            markup.row(
                InlineKeyboardButton(text='Looking Glass (IPv4)', url=f'{url_prefix}_v4'),
                InlineKeyboardButton(text='Looking Glass (IPv6)', url=f'{url_prefix}_v6'),
            )
        elif len(session_name) == 1:
            markup.row(
                InlineKeyboardButton(
                    text='Looking Glass',
                    url=f'{config.LG_DOMAIN}/detail/{node}/{session_name[0]}',
                )
            )
    if len(available_node) >= 2:
        for node_name in available_node:
            if node_name == node:
                markup.row(
                    InlineKeyboardButton(
                        text=f'✅ {config.SERVER[node_name]}',
                        callback_data=f"info_{node_name}",
                    )
                )
            else:
                markup.row(
                    InlineKeyboardButton(
                        text=config.SERVER[node_name],
                        callback_data=f"info_{node_name}",
                    )
                )
    return markup


def get_info_text(chatid, node):
    if chatid not in db:
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(
                text='Login now | 立即登录',
                url=f"https://t.me/{config.BOT_USERNAME}?start=login",
            )
        )
        return (
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            None,
            markup,
        )
    asn = db[chatid]
    all_peers = tools.get_info(asn)
    available_node = all_peers.keys()
    if not all_peers:
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(
                text='Peer now | 立即 Peer',
                url=f"https://t.me/{config.BOT_USERNAME}?start=peer",
            )
        )
        return (
            "You are not peer with me yet, you can use /peer to start.\n你还没有与我 Peer，可以使用 /peer 开始。",
            None,
            markup,
        )
    if node is None:
        if len(available_node) == 1:
            node = list(available_node)[0]
        else:
            return (
                "Select an available node from the list below to get information\n从下方列表中选择一个可用节点以获取信息",
                None,
                gen_info_markup('', available_node, []),
            )

    if node not in all_peers:
        return (
            "Node does not exist, please select another available node\n节点不存在，请选择其他可用节点",
            None,
            gen_info_markup('', available_node, []),
        )

    peer_info = all_peers[node]
    if not isinstance(peer_info, dict):
        return (
            chatid,
            (
                f"{config.SERVER[node]}:\n"
                f"Error occurred. Please contact {config.CONTACT} with following message.\n"
                f"遇到错误。请联系 {config.CONTACT} 并附带下述结果。\n"
                f"<code>{peer_info}</code>"
            ),
            "HTML",
            gen_info_markup('', available_node, []),
        )

    detail_text = "Node:\n"
    detail_text += f"    {config.SERVER[node]}\n"
    detail_text += "Information on your side:\n"
    detail_text += basic_info(
        db[chatid],
        peer_info['clearnet'],
        peer_info['pubkey'],
        peer_info['v6'],
        peer_info['v4'],
    )
    detail_text += "Information on my side:\n"
    detail_text += basic_info(
        config.DN42_ASN,
        f"{node}.{config.ENDPOINT}:{peer_info['port']}",
        peer_info['my_pubkey'],
        peer_info['my_v6'] if peer_info['v6'] else '',
        peer_info['my_v4'] if peer_info['v4'] else '',
    )

    if peer_info['wg_last_handshake'] == 0:
        detail_text += "WireGuard Status:\n" "    Latest handshake:\n" "        Never\n" "    Transfer:\n"
    else:
        latest_handshake = datetime.fromtimestamp(peer_info['wg_last_handshake'], tz=timezone.utc)
        latest_handshake_td = tools.td_format(datetime.now(tz=timezone.utc) - latest_handshake)
        latest_handshake = latest_handshake.isoformat().replace('+00:00', 'Z')
        detail_text += (
            "WireGuard Status:\n"
            "    Latest handshake:\n"
            f"        {latest_handshake}\n"
            f"        {latest_handshake_td}\n"
            "    Transfer:\n"
        )
    transfer = [tools.convert_size(i) for i in peer_info['wg_transfer']]
    detail_text += f"        {transfer[0]} received, {transfer[1]} sent\n"

    detail_text += "Bird Status:\n" f"    {peer_info['session']}\n"
    if len(peer_info['bird_status']) == 1:
        bird_status = list(peer_info['bird_status'].values())[0]
        detail_text += f"    {bird_status[0]}\n"
        if bird_status[1]:
            detail_text += f"    {bird_status[1]}\n"
        if len(bird_status[2]) == 2:
            detail_text += f"    IPv4\n        {bird_status[2]['4']}\n"
            detail_text += f"    IPv6\n        {bird_status[2]['6']}\n"
        elif bird_status[2]:
            detail_text += f"    {list(bird_status[2].values())[0]}\n"
    else:
        for session in ('4', '6'):
            bird_status = [v for k, v in peer_info['bird_status'].items() if k.endswith(session)][0]
            detail_text += f"    IPv{session}:\n"
            detail_text += f"        {bird_status[0]}\n"
            if bird_status[1]:
                detail_text += f"        {bird_status[1]}\n"
            if session in bird_status[2]:
                detail_text += f"        {bird_status[2][session]}\n"

    detail_text += "Contact:\n" f"    {tools.get_mnt_by_asn(db[chatid])}\n" f"    {peer_info['desc']}\n"

    return (
        f"```\n{detail_text.strip()}```",
        "Markdown",
        gen_info_markup(node, available_node, peer_info['session_name']),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("info_"))
def info_callback_query(call):
    node = call.data.split("_", 2)[1]
    info_text = get_info_text(call.message.chat.id, node)
    try:
        bot.edit_message_text(
            info_text[0],
            parse_mode=info_text[1],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=info_text[2],
        )
    except BaseException:
        pass


@bot.message_handler(commands=['info'], is_private_chat=True)
def get_info(message):
    info_text = get_info_text(message.chat.id, None)
    bot.send_message(message.chat.id, info_text[0], parse_mode=info_text[1], reply_markup=info_text[2])
