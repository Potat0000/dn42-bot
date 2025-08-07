import json
import socket
import string
from ipaddress import IPv4Network, IPv6Network, ip_address
from time import sleep

import base
import config
import requests
import tools
from base import bot, db, db_privilege
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def pre_region(message, peer_info):
    peered = set(tools.get_info(db[message.chat.id]).keys())
    pre_peer_info = tools.get_from_agent('pre_peer', None)
    could_peer = []
    msg = ''
    peer_info['Region'] = {}
    for k in config.SERVERS:
        msg += f'- `{config.SERVERS[k]}`\n'
        try:
            v = pre_peer_info[k]
        except KeyError:
            msg += '  Server offline, please try again later.\n' '  服务器离线，请稍后重试。\n\n'
            continue
        try:
            if v.status != 200:
                raise RuntimeError
            data = json.loads(v.text)
        except BaseException:
            msg += '  Server error, please try again later.\n' '  服务器错误，请稍后重试。\n\n'
            continue
        if 'backup' in peer_info and peer_info['backup']['Region'] == k:
            msg += '  ℹ️ Current Node\n'
        elif k in peered:
            msg += '  ℹ️ Already Peered\n'
        if data['open']:
            msg += '  ✔️ Open For Peer\n'
        else:
            msg += '  ❌ Not Open For Peer\n'
        if data['max'] == 0:
            msg += f'  ✔️ Capacity: {data["existed"]} / Unlimited\n'
        else:
            if data['existed'] < data['max']:
                msg += f'  ✔️ Capacity: {data["existed"]} / {data["max"]}\n'
            else:
                msg += f'  ❌ Capacity: {data["existed"]} / {data["max"]}\n'
        if data['net_support']['ipv4']:
            if data['net_support']['ipv4_nat']:
                msg += '  ⚠️ IPv4: Behind NAT\n'
            else:
                msg += '  ✔️ IPv4: Yes\n'
        else:
            msg += '  ⚠️ IPv4: No\n'
        if data['net_support']['ipv6']:
            msg += '  ✔️ IPv6: Yes\n'
        else:
            msg += '  ⚠️ IPv6: No\n'
        if not data['net_support']['cn']:
            msg += '  ⚠️ Not allowed to peer with Chinese Mainland\n'
        if data['msg']:
            msg += f'  {data["msg"]}\n'
        msg += '\n'
        if data['open'] and k not in peered and (data['max'] == 0 or data['existed'] < data['max']):
            could_peer.append(k)
            peer_info['Region'][base.servers[k]] = (k, data['lla'], data['net_support'])
    msg = bot.send_message(
        message.chat.id,
        f'Node List 节点列表\n{msg.strip()}',
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    if not could_peer:
        bot.send_message(
            message.chat.id,
            'No node is available for peering at the moment.\n' '目前没有节点可供 Peer。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if len(could_peer) == 1:
        bot.send_message(
            message.chat.id,
            (
                f'Only one available node, automatically select `{base.servers[could_peer[0]]}`\n'
                f'只有一个可选节点，自动选择 `{base.servers[could_peer[0]]}`\n'
                '\n'
                'If not wanted, use /cancel to interrupt the operation.\n'
                '如非所需，使用 /cancel 终止操作。'
            ),
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
        return post_region(message, peer_info, base.servers[could_peer[0]])
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in could_peer:
            markup.add(KeyboardButton(base.servers[i]))
        msg = bot.send_message(
            message.chat.id,
            'Which node do you want to choose?\n你想选择哪个节点？',
            reply_markup=markup,
        )
        return 'post_region', peer_info, msg


def post_region(message, peer_info, chosen=None):
    if not chosen:
        chosen = message.text.strip()
    if chosen not in peer_info['Region']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in peer_info['Region']:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_region', peer_info, msg
    peer_info['Provide-LinkLocal'] = peer_info['Region'][chosen][1]
    peer_info['Net_Support'] = peer_info['Region'][chosen][2]
    peer_info['Region'] = peer_info['Region'][chosen][0]
    return 'pre_session_type', peer_info, message


def pre_session_type(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 3
    markup.add(KeyboardButton('IPv6 & IPv4'), KeyboardButton('IPv6 only'), KeyboardButton('IPv4 only'))
    msg = bot.send_message(
        message.chat.id,
        'What routes do you want to transmit with me?\n你想和我传递哪些路由？',
        reply_markup=markup,
    )
    return 'post_session_type', peer_info, msg


def post_session_type(message, peer_info):
    if (
        message.text.strip().lower() == 'ipv6 & ipv4'
        or message.text.strip().lower() == 'ipv6 and ipv4'
        or message.text.strip().lower() == 'both'
    ):
        peer_info['Channel'] = 'IPv6 & IPv4'
        return 'pre_mpbgp_support', peer_info, message
    elif message.text.strip().lower() == 'ipv6 only' or message.text.strip().lower() == 'ipv6':
        peer_info['Channel'] = 'IPv6 only'
        peer_info['MP-BGP'] = 'Not supported'
        peer_info['ENH'] = None
        return 'pre_ipv6', peer_info, message
    elif message.text.strip().lower() == 'ipv4 only' or message.text.strip().lower() == 'ipv4':
        peer_info['Channel'] = 'IPv4 only'
        peer_info['MP-BGP'] = 'Not supported'
        peer_info['ENH'] = None
        peer_info['IPv6'] = 'Not enabled'
        return 'pre_ipv4', peer_info, message
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 3
        markup.add(KeyboardButton('IPv6 & IPv4'), KeyboardButton('IPv6 only'), KeyboardButton('IPv4 only'))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_session_type', peer_info, msg


def pre_mpbgp_support(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 2
    markup.add(KeyboardButton('Yes'), KeyboardButton('No'))
    msg = bot.send_message(
        message.chat.id,
        'Do you support Multi-Protocol BGP?\n你支持多协议 BGP 吗？',
        reply_markup=markup,
    )
    return 'post_mpbgp_support', peer_info, msg


def post_mpbgp_support(message, peer_info):
    if message.text.strip().lower() == 'yes':
        return 'pre_mpbgp_type', peer_info, message
    elif message.text.strip().lower() == 'no':
        peer_info['MP-BGP'] = 'Not supported'
        peer_info['ENH'] = None
        return 'pre_ipv6', peer_info, message
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton('Yes'), KeyboardButton('No'))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_mpbgp_support', peer_info, msg


def pre_mpbgp_type(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 2
    markup.add(KeyboardButton('IPv6'), KeyboardButton('IPv4'))
    msg = bot.send_message(
        message.chat.id,
        ('What address do you want to use to establish an MP-BGP session with me?\n' '你想使用什么地址与我建立多协议 BGP 会话？'),
        reply_markup=markup,
    )
    return 'post_mpbgp_type', peer_info, msg


def post_mpbgp_type(message, peer_info):
    if message.text.strip().lower() == 'ipv6':
        peer_info['MP-BGP'] = 'IPv6'
        return 'pre_enh', peer_info, message
    elif message.text.strip().lower() == 'ipv4':
        peer_info['MP-BGP'] = 'IPv4'
        peer_info['ENH'] = None
        return 'pre_ipv6', peer_info, message
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton('IPv6'), KeyboardButton('IPv4'))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_mpbgp_type', peer_info, msg


def pre_enh(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 2
    markup.add(KeyboardButton('Yes'), KeyboardButton('No'))
    msg = bot.send_message(
        message.chat.id,
        'Do you support Extended Next Hop?\n你支持扩展的下一跳吗？',
        reply_markup=markup,
    )
    return 'post_enh', peer_info, msg


def post_enh(message, peer_info):
    if message.text.strip().lower() == 'yes':
        peer_info['ENH'] = True
        peer_info['IPv4'] = 'Not required due to Extended Next Hop'
    elif message.text.strip().lower() == 'no':
        peer_info['ENH'] = False
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton('Yes'), KeyboardButton('No'))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_enh', peer_info, msg
    return 'pre_ipv6', peer_info, message


def pre_ipv6(message, peer_info):
    if peer_info['IPv6'] != 'Not enabled':
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(peer_info['IPv6']))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(
        message.chat.id,
        (
            'Input your DN42 IPv6 address.\n'
            '请输入你的 DN42 IPv6 地址。\n'
            '\n'
            'Both Link-Local and ULA address are support. Link-Local is preferred for Bird users while ULA is preferred for other BGP clients.\n'
            'Link-Local 和 ULA 地址均支持。Bird 用户首选 Link-Local，其他 BGP 客户端首选 ULA。'
        ),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_ipv6', peer_info, msg


def post_ipv6(message, peer_info):
    msg = message.text.strip()
    if '/' in msg:
        try:
            int(msg.rsplit('/', 1)[1])
            msg = msg.rsplit('/', 1)[0]
        except ValueError:
            pass
    try:  # Test for IPv6
        socket.inet_pton(socket.AF_INET6, msg)
        if ip_address(msg) not in IPv6Network('fc00::/7') and ip_address(msg) not in IPv6Network('fe80::/64'):
            raise ValueError
    except (socket.error, OSError, ValueError):
        msg = bot.send_message(
            message.chat.id,
            (
                'Invalid DN42 IPv6 address, please try again. Use /cancel to interrupt the operation.\n'
                '输入不是有效的 DN42 IPv6 地址，请重试。使用 /cancel 终止操作。'
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return 'post_ipv6', peer_info, msg
    peer_info['IPv6'] = msg
    if ip_address(peer_info['IPv6']) in IPv6Network('fe80::/64'):
        return 'pre_request_linklocal', peer_info, message
    else:
        peer_info['Request-LinkLocal'] = 'Not required due to not use LLA as IPv6'
        if peer_info['Channel'] == 'IPv6 & IPv4' and peer_info['ENH'] is not True:
            return 'pre_ipv4', peer_info, message
        else:
            peer_info['IPv4'] = 'Not enabled'
            return 'pre_clearnet', peer_info, message


def pre_request_linklocal(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    if peer_info['Request-LinkLocal'] != 'Not required due to not use LLA as IPv6':
        markup.add(KeyboardButton(peer_info['Request-LinkLocal']))
    else:
        markup.add(KeyboardButton(peer_info['Provide-LinkLocal']))
    msg = bot.send_message(
        message.chat.id,
        (
            'Link-Local address detected. You can enter the address required on my side as needed.\n'
            '检测到 Link-Local 地址。你可以按需输入所需的我这边的地址。\n\n'
            "Make modifications only if you know exactly what it is and are convinced it's needed, otherwise please directly select the option below.\n"
            '仅在你明确知道这是什么并且确信有必要时再做出修改，否则请直接选择下方的选项。'
        ),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_request_linklocal', peer_info, msg


def post_request_linklocal(message, peer_info):
    msg = message.text.strip()
    if '/' in msg:
        try:
            int(msg.rsplit('/', 1)[1])
            msg = msg.rsplit('/', 1)[0]
        except ValueError:
            pass
    try:  # Test for IPv6
        socket.inet_pton(socket.AF_INET6, msg)
        if ip_address(msg) not in IPv6Network('fe80::/64'):
            raise ValueError
    except (socket.error, OSError, ValueError):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        if peer_info['Request-LinkLocal'] != 'Not required due to not use LLA as IPv6':
            markup.add(KeyboardButton(peer_info['Request-LinkLocal']))
        else:
            markup.add(KeyboardButton(peer_info['Provide-LinkLocal']))
        msg = bot.send_message(
            message.chat.id,
            (
                'Invalid DN42 IPv6 Link-Local address, please try again. Use /cancel to interrupt the operation.\n'
                '输入不是有效的 DN42 IPv6 Link-Local 地址，请重试。使用 /cancel 终止操作。\n\n'
                "Make modifications only if you know exactly what it is and are convinced it's needed, otherwise please directly select the option below.\n"
                '仅在你明确知道这是什么并且确信有必要时再做出修改，否则请直接选择下方的选项。'
            ),
            reply_markup=markup,
        )
        return 'post_request_linklocal', peer_info, msg
    peer_info['Request-LinkLocal'] = msg
    if peer_info['Channel'] == 'IPv6 & IPv4' and peer_info['ENH'] is not True:
        return 'pre_ipv4', peer_info, message
    else:
        peer_info['IPv4'] = 'Not enabled'
        return 'pre_clearnet', peer_info, message


def pre_ipv4(message, peer_info):
    if peer_info['IPv4'] != 'Not enabled':
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(peer_info['IPv4']))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(
        message.chat.id,
        ('Input your DN42 IPv4 address.\n' '请输入你的 DN42 IPv4 地址。'),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_ipv4', peer_info, msg


def post_ipv4(message, peer_info):
    msg = message.text.strip()
    if '/' in msg:
        try:
            int(msg.rsplit('/', 1)[1])
            msg = msg.rsplit('/', 1)[0]
        except ValueError:
            pass
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, msg)
        if not any(ip_address(msg) in n for n in [IPv4Network('172.20.0.0/14'), IPv4Network('10.127.0.0/16')]):
            raise ValueError
    except (socket.error, OSError, ValueError):
        msg = bot.send_message(
            message.chat.id,
            (
                'Invalid DN42 IPv4 address, please try again. Use /cancel to interrupt the operation.\n'
                '输入不是有效的 DN42 IPv4 地址，请重试。使用 /cancel 终止操作。'
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return 'post_ipv4', peer_info, msg
    peer_info['IPv4'] = msg
    return 'pre_clearnet', peer_info, message


def pre_clearnet(message, peer_info):
    if peer_info['Clearnet']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        endpoint = peer_info['Clearnet'].split(':')
        peer_info['ClearnetPort'] = endpoint[-1]
        endpoint = ':'.join(endpoint[:-1])
        if endpoint[0] == '[' and endpoint[-1] == ']':
            endpoint = endpoint[1:-1]
        markup.add(KeyboardButton(endpoint))
    else:
        markup = ReplyKeyboardRemove()
    if peer_info['Net_Support']['ipv4'] and peer_info['Net_Support']['ipv6']:
        msg = ('You can use IPv4 or IPv6 to establish a tunnel with me.', '你可以使用 IPv4 或者 IPv6 与我建立隧道。')
    elif peer_info['Net_Support']['ipv4']:
        msg = ('You can only use IPv4 to establish a tunnel with me.', '你只能使用 IPv4 与我建立隧道。')
    elif peer_info['Net_Support']['ipv6']:
        msg = ('You can only use IPv6 to establish a tunnel with me.', '你只能使用 IPv6 与我建立隧道。')
    if peer_info['Net_Support']['ipv4'] and peer_info['Net_Support']['ipv4_nat']:
        msg = (
            msg[0] + ' Since my IPv4 is behind NAT, you are required to provide a clearnet address.',
            msg[1] + '由于我的 IPv4 位于 NAT 之后，所以需要你提供公网地址。',
        )
    msg = msg[0] + '\n' + msg[1]
    if peer_info['Net_Support']['ipv6'] or (
        peer_info['Net_Support']['ipv4'] and not peer_info['Net_Support']['ipv4_nat']
    ):
        if config.ALLOW_NO_CLEARNET:
            msg += (
                '\n\n'
                "If you don't have a clearnet address or is behind NAT, please enter `none`\n"
                '如果你没有公网地址，或你的服务器在 NAT 网络中，请输入 `none`'
            )
        elif message.chat.id in db_privilege:
            msg += (
                '\n\n'
                '*[Privilege]*\n'
                "If your peer don't have a clearnet address or is behind NAT, please enter `none`\n"
                '如果对方没有公网地址，或对方的服务器在 NAT 网络中，请输入 `none`'
            )
            if isinstance(markup, ReplyKeyboardRemove):
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row_width = 1
            markup.add(KeyboardButton('none'))
        else:
            msg += (
                '\n\n'
                f"If you don't have a clearnet address or is behind NAT, please contact {config.CONTACT}\n"
                f'如果你没有公网地址，或你的服务器在 NAT 网络中，请联系 {config.CONTACT}'
            )
    msg = bot.send_message(
        message.chat.id,
        ('Input your clearnet address for WireGuard tunnel.\n' '请输入你用于 WireGurad 隧道的公网地址。\n\n' f'{msg}'),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_clearnet', peer_info, msg


def post_clearnet(message, peer_info):
    if (
        (config.ALLOW_NO_CLEARNET or message.chat.id in db_privilege)
        and message.text.strip().lower() == 'none'
        and (
            peer_info['Net_Support']['ipv6']
            or (peer_info['Net_Support']['ipv4'] and not peer_info['Net_Support']['ipv4_nat'])
        )
    ):
        peer_info['Clearnet'] = None
        if message.chat.id in db_privilege:
            return 'pre_port_myside', peer_info, message
        else:
            return 'pre_pubkey', peer_info, message

    if message.text.strip().count(':') == 1:
        domain_part, port_part = message.text.strip().rsplit(':', 1)
        try:
            assert ':' not in domain_part
            assert 0 < int(port_part) <= 65535
            peer_info['ClearnetPort'] = port_part
            bot.send_message(
                message.chat.id,
                f'Port number `{port_part}` detected, automatically separated.\n'
                f'识别到端口号 `{port_part}`，已自动分离。\n\n'
                f'If this is not the correct port number, please try to restart the process, do not include the port number here, and contact {config.CONTACT} for help to improve the recognition accuracy.\n'
                f'识别可能有误。如果这不是正确的端口号，请尝试重新开始流程，在此处输入时不要包含端口号，并联系 {config.CONTACT} 以帮助提升识别准确性。\n',
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove(),
            )
        except (ValueError, AssertionError):
            pass
    else:
        domain_part = message.text.strip()

    msg = None
    if test_result := tools.test_ip_domain(domain_part):
        if test_result.clearnet:
            if (test_result.ipv4 and not test_result.ipv6) and not peer_info['Net_Support']['ipv4']:
                msg = 'IPv4 is not supported on this node', '该节点不支持IPv4'
            elif (test_result.ipv6 and not test_result.ipv4) and not peer_info['Net_Support']['ipv6']:
                msg = 'IPv6 is not supported on this node', '该节点不支持IPv6'
            else:
                msg = None
                if not peer_info['Net_Support']['cn'] and (
                    (test_result.ipv4 and any(ip_address(test_result.ipv4) in i for i in base.ChinaIPv4))
                    or (test_result.ipv6 and any(ip_address(test_result.ipv6) in i for i in base.ChinaIPv6))
                ):
                    msg = (
                        'Peering with Chinese Mainland is not allowed on this node',
                        '该节点不允许与中国大陆 Peer',
                        (
                            'Please note that do NOT try to bypass this restriction. Even if you successfully make the bot record your address for now, your data will be dropped by the firewall.\n'
                            '请注意，不要尝试绕过该限制。即使你现在成功让 Bot 记录了你的地址，与你的数据也会被防火墙丢弃。\n\n'
                        ),
                    )
                if not msg:
                    peer_info['Clearnet'] = test_result.raw
                    if all(i in '0123456789ABCDEFabcdef:' for i in peer_info['Clearnet']):
                        peer_info['Clearnet'] = f"[{peer_info['Clearnet']}]"
        else:
            msg = 'Invalid or unreachable clearnet address', '输入不是有效的公网地址或该地址不可达'
    else:
        msg = 'Invalid or unreachable clearnet address', '输入不是有效的公网地址或该地址不可达'
    if msg:
        if message.chat.id not in db_privilege:
            if len(msg) == 2:
                msg = f'{msg[0]}, please try again.\n{msg[1]}，请重试。\n\n'
            elif len(msg) == 3:
                msg = f'{msg[0]}, please try again.\n{msg[1]}，请重试。\n\n{msg[2]}'
            msg = bot.send_message(
                message.chat.id,
                (
                    f'{msg}'
                    f'The check procedure may sometimes be wrong, if it is confirmed to be valid, just resubmit. If the error keeps occurring please contact {config.CONTACT}\n'
                    f'判定程序可能出错。如果确认有效，重新提交即可。重复出错请联系 {config.CONTACT}\n\n'
                    'Use /cancel to interrupt the operation.\n'
                    '使用 /cancel 终止操作。'
                ),
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='Markdown',
            )
            return 'post_clearnet', peer_info, msg
        else:
            bot.send_message(
                message.chat.id,
                (
                    '*[Privilege]*\n'
                    f'{msg[0]}.\n'
                    f'{msg[1]}。\n\n'
                    'Use the privilege to continue the process. Use /cancel to exit if there is a mistake.\n'
                    '使用特权，流程继续。如确认有误使用 /cancel 退出。'
                ),
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove(),
            )
            peer_info['Clearnet'] = domain_part
    return 'pre_clearnet_port', peer_info, message


def pre_clearnet_port(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    if port := peer_info.pop('ClearnetPort', None):
        markup.add(KeyboardButton(port))
        if port != str(config.DN42_ASN % 100000):
            markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
    else:
        markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
    msg = bot.send_message(
        message.chat.id,
        'Input your port for WireGuard tunnel.\n请输入你用于 WireGurad 隧道的端口。',
        reply_markup=markup,
    )
    return 'post_clearnet_port', peer_info, msg


def post_clearnet_port(message, peer_info):
    try:
        port = int(message.text.strip())
        if not (0 < port <= 65535):
            raise ValueError
    except ValueError:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
        msg = bot.send_message(
            message.chat.id,
            (
                'Invalid port, please try again. Use /cancel to interrupt the operation.\n'
                '输入不是有效的端口，请重试。使用 /cancel 终止操作。'
            ),
            reply_markup=markup,
        )
        return 'post_clearnet_port', peer_info, msg
    peer_info['Clearnet'] += f':{message.text.strip()}'
    if message.chat.id in db_privilege:
        return 'pre_port_myside', peer_info, message
    else:
        return 'pre_pubkey', peer_info, message


def pre_port_myside(message, peer_info):
    text = '*[Privilege]*\n' 'Enter the port number provided to your peer\n' '请输入给对方提供的端口号'
    if peer_info['Port']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(str(peer_info['Port'])))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)
    return 'post_port_myside', peer_info, msg


def post_port_myside(message, peer_info):
    try:
        port = int(message.text.strip())
        if not (0 < port <= 65535):
            raise ValueError
    except ValueError:
        if peer_info['Port']:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton(str(peer_info['Port'])))
        else:
            markup = ReplyKeyboardRemove()
        msg = bot.send_message(
            message.chat.id,
            (
                'Invalid port, please try again. Use /cancel to interrupt the operation.\n'
                '输入不是有效的端口，请重试。使用 /cancel 终止操作。'
            ),
            reply_markup=markup,
        )
        return 'post_port_myside', peer_info, msg
    peer_info['Port'] = message.text.strip()
    return 'pre_pubkey', peer_info, message


def pre_pubkey(message, peer_info):
    if peer_info['PublicKey']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(peer_info['PublicKey']))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(
        message.chat.id,
        'Input your WireGuard public key\n请输入你的 WireGuard 公钥',
        reply_markup=markup,
    )
    return 'post_pubkey', peer_info, msg


def post_pubkey(message, peer_info):
    if len(message.text.strip()) != 44 or message.text.strip()[-1] != '=':
        msg = bot.send_message(
            message.chat.id,
            (
                'Invalid public key, please try again. Use /cancel to interrupt the operation.\n'
                '输入不是有效的公钥，请重试。使用 /cancel 终止操作。'
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return 'post_pubkey', peer_info, msg
    peer_info['PublicKey'] = message.text.strip()
    return 'pre_contact', peer_info, message


def pre_contact(message, peer_info):
    button = []
    contact = peer_info['Contact']
    if contact:
        button.append(contact)
        if contact.startswith('@'):
            contact = contact[1:]
    if message.from_user.username and message.from_user.username != contact:
        button.append('@' + message.from_user.username)
    if message.chat.id in db_privilege and tools.get_whoisinfo_by_asn(db[message.chat.id]) not in button:
        button.append(tools.get_whoisinfo_by_asn(db[message.chat.id]))
    if button:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in button:
            markup.add(KeyboardButton(i))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(
        message.chat.id,
        ('Input your contact information (Telegram or Email)\n' '请输入你的联系方式（Telegram 或 Email）'),
        reply_markup=markup,
    )
    return 'post_contact', peer_info, msg


def post_contact(message, peer_info):
    allowed_punctuation = '!#$%&()*+,-./:;<=>?@[]^_{|}~'
    if message.text.strip() == '' or any(
        c not in (string.ascii_letters + string.digits + allowed_punctuation + ' ') for c in message.text.strip()
    ):
        msg = bot.send_message(
            message.chat.id,
            (
                'Only non-empty strings which contain only upper and lower case letters, numbers, spaces and the following special symbols are accepted.\n'
                '只接受仅由大小写英文字母、数字、空格及以下特殊符号组成的非空字符串。\n'
                '\n'
                f'`{allowed_punctuation}`\n'
                '\n'
                'Please try again. Use /cancel to interrupt the operation.\n'
                '请重试。使用 /cancel 终止操作。'
            ),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown',
        )
        return 'post_contact', peer_info, msg
    peer_info['Contact'] = message.text.strip()
    return 'pre_confirm', peer_info, message


def post_confirm(message, peer_info):
    progress_type = peer_info.pop('ProgressType')
    info_text = peer_info.pop('InfoText').strip()
    old_region = peer_info.pop('OldRegion', None)
    if (whoisinfo := tools.get_whoisinfo_by_asn(db[message.chat.id])).lower() != peer_info['Contact'].lower():
        info_text += f'\n    ({whoisinfo})\n'
    check_text = message.text.strip()
    if check_text.lower() != 'yes':
        bot.send_message(
            message.chat.id,
            'Current operation has been cancelled.\n当前操作已被取消。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    try:
        if peer_info['Region'] in config.HOSTS:
            api = config.HOSTS[peer_info['Region']]
        else:
            api = f'{peer_info["Region"]}.{config.ENDPOINT}'
        r = requests.post(
            f'http://{api}:{config.API_PORT}/peer',
            data=json.dumps(peer_info),
            headers={'X-DN42-Bot-Api-Secret-Token': config.API_TOKEN},
            timeout=10,
        )
        if r.status_code == 503:
            bot.send_message(
                message.chat.id,
                (
                    'This node is not open for peer, or has reached its maximum peer capacity.\n'
                    '该节点暂未开放 Peer，或已达最大 Peer 容量。'
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        elif r.status_code != 200:
            raise RuntimeError
        if progress_type == 'modify':
            sleep(1)
            if old_region == peer_info['Region']:
                r = requests.post(
                    f'http://{api}:{config.API_PORT}/restart',
                    data=str(db[message.chat.id]),
                    headers={'X-DN42-Bot-Api-Secret-Token': config.API_TOKEN},
                    timeout=10,
                )
                if r.status_code != 200:
                    bot.send_message(
                        message.chat.id,
                        (
                            f'The peer information has been modified but failed to restart the service. Please use /restart to restart it manually. If the problem persists, please contact {config.CONTACT}\n'
                            f'Peer 信息已修改，但服务重启失败，请手工使用 /restart 重启。如果问题依旧，请联系 {config.CONTACT}'
                        ),
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return
            else:
                if old_region in config.HOSTS:
                    old_region_api = config.HOSTS[old_region]
                else:
                    old_region_api = f'{old_region}.{config.ENDPOINT}'
                r = requests.post(
                    f'http://{old_region_api}:{config.API_PORT}/remove',
                    data=str(db[message.chat.id]),
                    headers={'X-DN42-Bot-Api-Secret-Token': config.API_TOKEN},
                    timeout=10,
                )
                if r.status_code != 200:
                    bot.send_message(
                        message.chat.id,
                        (
                            f'The peer for the new region has been added but failed to remove the one in the origin region. Please use /remove to remove it manually. If the problem persists, please contact {config.CONTACT}\n'
                            f'新位置的配置已生效，但旧位置的配置删除失败，请手工使用 /remove 删除。如果问题依旧，请联系 {config.CONTACT}'
                        ),
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return
    except BaseException:
        bot.send_message(
            message.chat.id,
            (
                f'Error encountered, please try again. If the problem remains, please contact {config.CONTACT}\n'
                f'遇到错误，请重试。如果问题依旧，请联系 {config.CONTACT}'
            ),
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if progress_type == 'peer':
        msg_text = 'Peer has been created\nPeer 已建立'
    elif progress_type == 'modify':
        msg_text = 'Peer information has been modified\nPeer 信息已修改'
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(
            'Show info | 查看信息',
            url=f"https://t.me/{bot.get_me().username}?start=info_{peer_info['ASN']}_{peer_info['Region']}",
        )
    )
    bot.send_message(message.chat.id, msg_text, reply_markup=markup)

    if progress_type == 'peer':
        msg_text = 'New Peer!   新 Peer！\n'
    elif progress_type == 'modify':
        msg_text = 'Peer Modified!   Peer 信息修改！\n'
    text = f'*[Privilege]*\n{msg_text}```PrivilegeNote\n{info_text}```'
    markup2 = InlineKeyboardMarkup()
    markup2.row_width = 1
    markup2.add(
        InlineKeyboardButton(
            'Switch to it | 切换至该身份',
            url=f"https://t.me/{bot.get_me().username}?start=whoami_{peer_info['ASN']}_{peer_info['Region']}",
        )
    )
    markup2.add(
        InlineKeyboardButton(
            'Show info | 查看信息',
            url=f"https://t.me/{bot.get_me().username}?start=info_{peer_info['ASN']}_{peer_info['Region']}",
        )
    )
    for i in db_privilege - {message.chat.id}:
        if peer_info['ASN'] == db[i]:
            bot.send_message(i, text + 'Already as this user 已在该身份', parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(i, text, parse_mode='Markdown', reply_markup=markup2)
