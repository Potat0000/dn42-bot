import math
from datetime import datetime, timezone
from ipaddress import IPv4Network, IPv6Network, ip_address

import base
import config
import tools
from base import bot, db, db_privilege
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove


# https://stackoverflow.com/a/14822210
def convert_size(size_bytes):
    if size_bytes == 0:
        return '0B'
    size_name = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return '%s %s' % (s, size_name[i])


# https://stackoverflow.com/a/13756038
def td_format(td_object):
    seconds = int(td_object.total_seconds())
    if seconds <= 0:
        return 'now'
    periods = [
        # ('year', 60 * 60 * 24 * 365),
        # ('month', 60 * 60 * 24 * 30),
        ('day', 60 * 60 * 24),
        ('hour', 60 * 60),
        ('minute', 60),
        ('second', 1),
    ]
    strings = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            has_s = 's' if period_value > 1 else ''
            strings.append('%s %s%s' % (period_value, period_name, has_s))
    return ', '.join(strings) + ' ago'


def basic_info(asn, endpoint, pubkey, v6, v4):
    text = (
        '    ASN:\n'
        f'        AS{asn}\n'
        '    Endpoint:\n'
        f'        {endpoint}\n'
        '    WireGuard Public Key:\n'
        f'        {pubkey}\n'
        '    DN42 Address:\n'
    )
    ipv6_space = ''
    try:
        if ip_address(v6) in IPv6Network('fc00::/7'):
            text += f'        IPv6 ULA: {v6}/128\n'
            ipv6_space = ' ' * 4
    except BaseException:
        pass
    try:
        if ip_address(v6) in IPv6Network('fe80::/64'):
            text += f'        IPv6 Link-Local: {v6}/64\n'
            ipv6_space = ' ' * 11
    except BaseException:
        pass
    try:
        if any(ip_address(v4) in n for n in [IPv4Network('172.20.0.0/14'), IPv4Network('10.127.0.0/16')]):
            text += f'        IPv4: {ipv6_space}{v4}/32\n'
    except BaseException:
        pass
    return text


def gen_info_markup(chatid, asn, node, available_node, session_name):
    markup = InlineKeyboardMarkup()
    if config.LG_DOMAIN:
        if len(session_name) == 2:
            session_name = '_'.join(session_name[0].split('_')[:-1])
            url_prefix = f'{config.LG_DOMAIN}/detail/{node}/{session_name}'
            markup.row(
                InlineKeyboardButton(text='Looking Glass (IPv4)', url=f'{url_prefix}_v4'),
                InlineKeyboardButton(text='Looking Glass (IPv6)', url=f'{url_prefix}_v6'),
            )
        elif len(session_name) == 1:
            markup.row(
                InlineKeyboardButton(text='Looking Glass', url=f'{config.LG_DOMAIN}/detail/{node}/{session_name[0]}')
            )
    if len(available_node) != 1:
        for node_name in available_node:
            selected = '✅ ' if node_name == node else ''
            markup.row(
                InlineKeyboardButton(
                    text=f'{selected}{base.servers[node_name]}', callback_data=f'info_{asn}_{node_name}'
                )
            )
    else:
        markup.row(InlineKeyboardButton(text='Refresh | 刷新', callback_data=f'info_{asn}_{node}'))
    if chatid in db_privilege and db[chatid] != asn:
        if not node:
            node = ''
        markup.row(
            InlineKeyboardButton(
                'Switch to it | 切换至该身份',
                url=f'https://t.me/{bot.get_me().username}?start=whoami_{asn}_{node}',
            )
        )
    return markup


def get_info_text(chatid, asn, node):
    if asn and chatid not in db_privilege:
        if chatid not in db:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton(text='Login now | 立即登录', url=f'https://t.me/{bot.get_me().username}?start=login')
            )
            return 'You are not allowed to view information of other ASN.\n你无权查看其他 ASN 的信息。', markup
        elif asn != db[chatid]:
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton(text='Show my info | 显示我的信息', callback_data=f'info_{db[chatid]}_'))
            return 'You are not allowed to view information of other ASN.\n你无权查看其他 ASN 的信息。', markup
    elif chatid not in db:
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(text='Login now | 立即登录', url=f'https://t.me/{bot.get_me().username}?start=login')
        )
        return 'You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login', markup
    elif not asn:
        asn = db[chatid]
    all_peers = tools.get_info(asn)
    available_node = all_peers.keys()
    if not all_peers:
        if asn == db[chatid] or chatid not in db_privilege:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton(text='Peer now | 立即 Peer', url=f'https://t.me/{bot.get_me().username}?start=peer')
            )
            return (
                'You are not peer with me yet, you can use /peer to start.\n你还没有与我 Peer，可以使用 /peer 开始。',
                markup,
            )
        else:
            return (
                '*[Privilege]*\n'
                'This user has no peer at the moment, may have been deleted already.\n'
                '该用户目前无 Peer，可能已经被对方删除',
                None,
            )
    if not node:
        if len(available_node) == 1:
            node = list(available_node)[0]
        else:
            return (
                'Select an available node from the list below to get information\n从下方列表中选择一个可用节点以获取信息',
                gen_info_markup(chatid, asn, '', available_node, []),
            )

    if node not in all_peers:
        return (
            'Node does not exist, please select another available node\n节点不存在，请选择其他可用节点',
            gen_info_markup(chatid, asn, '', available_node, []),
        )

    peer_info = all_peers[node]
    if not isinstance(peer_info, dict):
        return (
            (
                f'{base.servers[node]}:\n'
                f'Error occurred. Please contact {config.CONTACT} with following message.\n'
                f'遇到错误。请联系 {config.CONTACT} 并附带下述结果。\n'
                f'`{peer_info}`'
            ),
            gen_info_markup(chatid, asn, '', available_node, []),
        )

    detail_text = 'Node:\n'
    detail_text += f'    {base.servers[node]}\n'
    detail_text += 'Information on your side:\n'
    detail_text += basic_info(
        asn,
        peer_info['clearnet'],
        peer_info['pubkey'],
        peer_info['v6'],
        peer_info['v4'],
    )
    detail_text += 'Information on my side:\n'
    detail_text += basic_info(
        config.DN42_ASN,
        f"{node}.{config.ENDPOINT}:{peer_info['port']}",
        peer_info['my_pubkey'],
        peer_info['my_v6'] if peer_info['v6'] else '',
        peer_info['my_v4'] if peer_info['v4'] else '',
    )

    if peer_info['wg_last_handshake'] == 0:
        detail_text += 'WireGuard Status:\n' '    Latest handshake:\n' '        Never\n' '    Transfer:\n'
    else:
        latest_handshake = datetime.fromtimestamp(peer_info['wg_last_handshake'], tz=timezone.utc)
        latest_handshake_td = td_format(datetime.now(tz=timezone.utc) - latest_handshake)
        latest_handshake = latest_handshake.isoformat().replace('+00:00', 'Z')
        detail_text += (
            'WireGuard Status:\n'
            '    Latest handshake:\n'
            f'        {latest_handshake}\n'
            f'        {latest_handshake_td}\n'
            '    Transfer:\n'
        )
    transfer = [convert_size(i) for i in peer_info['wg_transfer']]
    detail_text += f'        {transfer[0]} received, {transfer[1]} sent\n'

    detail_text += 'Bird Status:\n' f"    {peer_info['session']}\n"
    if len(peer_info['bird_status']) == 1:
        bird_status = list(peer_info['bird_status'].values())[0]
        detail_text += f'    {bird_status[0]}\n'
        if bird_status[1]:
            detail_text += f'    {bird_status[1]}\n'
        if len(bird_status[2]) == 2:
            detail_text += f"    IPv4\n        {bird_status[2]['4']}\n"
            detail_text += f"    IPv6\n        {bird_status[2]['6']}\n"
        elif bird_status[2]:
            detail_text += f'    {list(bird_status[2].values())[0]}\n'
    else:
        for session in ('4', '6'):
            bird_status = [v for k, v in peer_info['bird_status'].items() if k.endswith(session)][0]
            detail_text += f'    IPv{session}:\n'
            detail_text += f'        {bird_status[0]}\n'
            if bird_status[1]:
                detail_text += f'        {bird_status[1]}\n'
            if session in bird_status[2]:
                detail_text += f'        {bird_status[2][session]}\n'

    if tools.get_whoisinfo_by_asn(asn).lower() == peer_info['desc'].lower():
        detail_text += 'Contact:\n' f"    {peer_info['desc']}\n"
    else:
        detail_text += 'Contact:\n' f"    {peer_info['desc']}\n"
        detail_text += f'    ({tools.get_whoisinfo_by_asn(asn)})\n'

    return (
        f'```Info\n{detail_text.strip()}```',
        gen_info_markup(chatid, asn, node, available_node, peer_info['session_name']),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('info_'))
def info_callback_query(call):
    _, asn, node = call.data.split('_', 3)
    info_text = get_info_text(call.message.chat.id, int(asn), node)
    try:
        bot.edit_message_text(
            info_text[0],
            parse_mode='Markdown',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=info_text[1],
        )
    except BaseException:
        pass


@bot.message_handler(commands=['info'], is_private_chat=True)
def get_info(message, asn=None, node=None):
    if offline_servers := set(config.SERVERS.values()) - set(base.servers.values()):
        msg = 'The following servers are currently offline, please try again later:\n以下服务器目前处于离线状态，如有需要请稍后再试：'
        for i in offline_servers:
            msg += f'\n`{i}`'
        bot.send_message(
            message.chat.id,
            msg,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
    if not asn and message.chat.id in db_privilege and len(t := message.text.split()) == 2:
        asn = tools.extract_asn(t[1], privilege=True)
    info_text = get_info_text(message.chat.id, asn, node)
    bot.send_message(message.chat.id, info_text[0], parse_mode='Markdown', reply_markup=info_text[1])
