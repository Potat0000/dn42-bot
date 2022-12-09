# -*- coding: utf-8 -*-
from datetime import datetime, timezone

import config
import tools
from base import bot, db
from IPy import IP
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['info', 'status'], is_for_me=True, is_private_chat=True)
def get_info(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    asn = db[message.chat.id]
    all_peers = tools.get_info(asn)
    if not all_peers:
        bot.send_message(
            message.chat.id,
            ("You are not peer with me yet, you can use /peer to start.\n" "你还没有与我 Peer，可以使用 /peer 开始。"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

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

    for region, peer_info in all_peers.items():
        if not isinstance(peer_info, dict):
            bot.send_message(
                message.chat.id,
                (
                    f"{config.SERVER[region]}:\n"
                    f"Error occurred. Please contact {config.CONTACT} with following message.\n"
                    f"遇到错误。请联系 {config.CONTACT} 并附带下述结果。\n"
                    f"<code>{peer_info}</code>"
                ),
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
            continue

        detail_text = "Information on your side:\n"
        detail_text += basic_info(
            db[message.chat.id],
            peer_info['clearnet'],
            peer_info['pubkey'],
            peer_info['v6'],
            peer_info['v4'],
        )
        detail_text += "Information on my side:\n"
        detail_text += basic_info(
            config.DN42_ASN,
            f"{region}.{config.ENDPOINT}:{peer_info['port']}",
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

        detail_text += "Contact:\n" f"    {tools.get_mnt_by_asn(db[message.chat.id])}\n" f"    {peer_info['desc']}\n"

        if config.LG_DOMAIN:
            if len(peer_info['session_name']) == 2:
                session_name = '_'.join(peer_info['session_name'][0].split('_')[:-1])
                url_prefix = f"{config.LG_DOMAIN}/detail/{region}/{session_name}"
                button_list = [
                    [
                        InlineKeyboardButton(text='Looking Glass (IPv4)', url=f'{url_prefix}_v4'),
                        InlineKeyboardButton(text='Looking Glass (IPv6)', url=f'{url_prefix}_v6'),
                    ],
                ]
            else:
                button_list = [
                    [
                        InlineKeyboardButton(
                            text='Looking Glass',
                            url=f'{config.LG_DOMAIN}/detail/{region}/{peer_info["session_name"][0]}',
                        )
                    ]
                ]
            markup = InlineKeyboardMarkup(button_list)
        else:
            markup = ReplyKeyboardRemove()

        bot.send_message(
            message.chat.id,
            (
                f"{config.SERVER[region]}:\n"
                f"```\n{detail_text}```\n"
                "Click the button below to view Looking Glass.\n"
                "点击下方按钮查看 Looking Glass。"
            ),
            parse_mode="Markdown",
            reply_markup=markup,
        )
