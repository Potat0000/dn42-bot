# -*- coding: utf-8 -*-
import json
import re
import socket
import string

import config
import dns.resolver as dns
import requests
import tools
from base import bot, db, db_privilege
from IPy import IP
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
    for k, v in pre_peer_info.items():
        msg += f'- `{config.SERVER[k]}`\n'
        try:
            if v.status != 200:
                raise RuntimeError
            data = json.loads(v.text)
        except BaseException:
            msg += '  `Server error, please try again later.`\n' '  `服务器错误，请稍后重试。`\n\n'
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
        if data['msg']:
            msg += f'  {data["msg"]}\n'
        msg += '\n'
        if data['open'] and k not in peered and (data['max'] == 0 or data['existed'] < data['max']):
            could_peer.append(k)
            peer_info['Region'][config.SERVER[k]] = (k, data['lla'], data['net_support'])
    msg = bot.send_message(
        message.chat.id,
        f"Node List 节点列表\n{msg.strip()}",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    if not could_peer:
        bot.send_message(
            message.chat.id,
            "No node is available for peering at the moment.\n" "目前没有节点可供 Peer。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    for i in could_peer:
        markup.add(KeyboardButton(config.SERVER[i]))
    msg = bot.send_message(
        message.chat.id,
        "Which node do you want to choose?\n你想选择哪个节点？",
        reply_markup=markup,
    )
    return 'post_region', peer_info, msg


def post_region(message, peer_info):
    if message.text.strip() not in peer_info['Region']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in peer_info['Region']:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        return 'post_region', peer_info, msg
    peer_info['Request-LinkLocal'] = peer_info['Region'][message.text.strip()][1]
    peer_info['Net_Support'] = peer_info['Region'][message.text.strip()][2]
    peer_info['Region'] = peer_info['Region'][message.text.strip()][0]
    return 'pre_session_type', peer_info, message


def pre_session_type(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 3
    markup.add(KeyboardButton("IPv6 & IPv4"), KeyboardButton("IPv6 only"), KeyboardButton("IPv4 only"))
    msg = bot.send_message(
        message.chat.id,
        "What routes do you want to transmit with me?\n你想和我传递哪些路由？",
        reply_markup=markup,
    )
    return 'post_session_type', peer_info, msg


def post_session_type(message, peer_info):

    if (
        message.text.strip().lower() == "ipv6 & ipv4"
        or message.text.strip().lower() == "ipv6 and ipv4"
        or message.text.strip().lower() == "both"
    ):
        peer_info["Channel"] = "IPv6 & IPv4"
        return 'pre_mpbgp_support', peer_info, message
    elif message.text.strip().lower() == "ipv6 only" or message.text.strip().lower() == "ipv6":
        peer_info["Channel"] = "IPv6 only"
        return 'pre_ipv6', peer_info, message
    elif message.text.strip().lower() == "ipv4 only" or message.text.strip().lower() == "ipv4":
        peer_info["Channel"] = "IPv4 only"
        return 'pre_ipv4', peer_info, message
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 3
        markup.add(KeyboardButton("IPv6 & IPv4"), KeyboardButton("IPv6 only"), KeyboardButton("IPv4 only"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        return 'post_session_type', peer_info, msg


def pre_mpbgp_support(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 2
    markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
    msg = bot.send_message(
        message.chat.id,
        "Do you support Multiprotocol BGP?\n你支持多协议 BGP 吗？",
        reply_markup=markup,
    )
    return 'post_mpbgp_support', peer_info, msg


def post_mpbgp_support(message, peer_info):
    if message.text.strip().lower() == "yes":
        return 'pre_mpbgp_type', peer_info, message
    elif message.text.strip().lower() == "no":
        return 'pre_ipv6', peer_info, message
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        return 'post_mpbgp_support', peer_info, msg


def pre_mpbgp_type(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 2
    markup.add(KeyboardButton("IPv6"), KeyboardButton("IPv4"))
    msg = bot.send_message(
        message.chat.id,
        ("What address do you want to use to establish an MP-BGP session with me?\n" "你想使用什么地址与我建立多协议 BGP 会话？"),
        reply_markup=markup,
    )
    return 'post_mpbgp_type', peer_info, msg


def post_mpbgp_type(message, peer_info):
    if message.text.strip().lower() == "ipv6":
        peer_info["MP-BGP"] = "IPv6"
        return 'pre_enh', peer_info, message
    elif message.text.strip().lower() == "ipv4":
        peer_info["MP-BGP"] = "IPv4"
        return 'pre_ipv6', peer_info, message
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("IPv6"), KeyboardButton("IPv4"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        return 'post_mpbgp_type', peer_info, msg


def pre_enh(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 2
    markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
    msg = bot.send_message(
        message.chat.id,
        "Do you support Extended Next Hop?\n你支持扩展的下一跳吗？",
        reply_markup=markup,
    )
    return 'post_enh', peer_info, msg


def post_enh(message, peer_info):
    if message.text.strip().lower() == "yes":
        peer_info["ENH"] = True
        peer_info["IPv4"] = "Not required due to Extended Next Hop"
    elif message.text.strip().lower() == "no":
        peer_info["ENH"] = False
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
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
            "Input your DN42 IPv6 address, without `/L` suffix.\n"
            "请输入你的 DN42 IPv6 地址，不包含 `/L` 后缀。\n"
            "\n"
            "Both Link-Local and ULA address are support. Link-Local is preferred for Bird users while ULA is preferred for other BGP clients.\n"
            "Link-Local 和 ULA 地址均支持。Bird 用户首选 Link-Local，其他 BGP 客户端首选 ULA。"
        ),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_ipv6', peer_info, msg


def post_ipv6(message, peer_info):
    try:  # Test for IPv6
        socket.inet_pton(socket.AF_INET6, message.text.strip())
        if IP(message.text.strip()) not in IP("fc00::/7") and IP(message.text.strip()) not in IP("fe80::/64"):
            raise ValueError
    except (socket.error, ValueError):
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid DN42 IPv6 address, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的 DN42 IPv6 地址，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return 'post_ipv6', peer_info, msg
    peer_info["IPv6"] = message.text.strip()
    if IP(message.text.strip()) in IP("fe80::/64"):
        return 'pre_request_linklocal', peer_info, message
    else:
        if peer_info["Channel"] == "IPv6 & IPv4" and peer_info["ENH"] is not True:
            return 'pre_ipv4', peer_info, message
        else:
            return 'pre_clearnet', peer_info, message


def pre_request_linklocal(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    markup.add(KeyboardButton(peer_info['Request-LinkLocal']))
    msg = bot.send_message(
        message.chat.id,
        (
            "Link-Local address detected. You can enter the address required on my side as needed, without `/L` suffix.\n"
            "检测到 Link-Local 地址。你可以按需输入所需的我这边的地址，不包含 `/L` 后缀。\n\n"
            "If you don't know what this is, or don't need to specify it, select the option below.\n"
            "如果你不知道这是什么，或者不需要指定，直接选择下方的选项。"
        ),
        parse_mode="Markdown",
        reply_markup=markup,
    )
    return 'post_request_linklocal', peer_info, msg


def post_request_linklocal(message, peer_info):
    try:  # Test for IPv6
        socket.inet_pton(socket.AF_INET6, message.text.strip())
        if IP(message.text.strip()) not in IP("fe80::/64"):
            raise ValueError
    except (socket.error, ValueError):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(peer_info['Request-LinkLocal']))
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid DN42 IPv6 Link-Local address, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的 DN42 IPv6 Link-Local 地址，请重试。使用 /cancel 终止操作。\n\n"
                "If you don't know what this is, or don't need to specify it, select the option below.\n"
                "如果你不知道这是什么，或者不需要指定，直接选择下方的选项。"
            ),
            reply_markup=markup,
        )
        return 'post_request_linklocal', peer_info, msg
    peer_info["Request-LinkLocal"] = message.text.strip()
    if peer_info["Channel"] == "IPv6 & IPv4" and peer_info["ENH"] is not True:
        return 'pre_ipv4', peer_info, message
    else:
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
        ("Input your DN42 IPv4 address, without `/L` suffix.\n" "请输入你的 DN42 IPv4 地址，不包含 `/L` 后缀。"),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_ipv4', peer_info, msg


def post_ipv4(message, peer_info):
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, message.text.strip())
        if IP(message.text.strip()) not in IP("172.20.0.0/14"):
            raise ValueError
    except (socket.error, ValueError):
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid DN42 IPv4 address, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的 DN42 IPv4 地址，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return 'post_ipv4', peer_info, msg
    peer_info["IPv4"] = message.text.strip()
    return 'pre_clearnet', peer_info, message


def pre_clearnet(message, peer_info):
    if peer_info['Clearnet']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        endpoint = peer_info['Clearnet'].split(':')
        peer_info['ClearnetPort'] = endpoint[-1]
        endpoint = ':'.join(endpoint[:-1])
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
        msg += (
            '\n\n'
            "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
            "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
        )
    msg = bot.send_message(
        message.chat.id,
        (
            "Input your clearnet address for WireGuard tunnel, without port.\n"
            "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
            f"{msg}"
        ),
        parse_mode="Markdown",
        reply_markup=markup,
    )
    return 'post_clearnet', peer_info, msg


def post_clearnet(message, peer_info):
    def test_clearnet(address):
        IPv4_Bogon = [
            IP('0.0.0.0/8'),
            IP('10.0.0.0/8'),
            IP('100.64.0.0/10'),
            IP('127.0.0.0/8'),
            IP('127.0.53.53'),
            IP('169.254.0.0/16'),
            IP('172.16.0.0/12'),
            IP('192.0.0.0/24'),
            IP('192.0.2.0/24'),
            IP('192.168.0.0/16'),
            IP('198.18.0.0/15'),
            IP('198.51.100.0/24'),
            IP('203.0.113.0/24'),
            IP('224.0.0.0/4'),
            IP('240.0.0.0/4'),
            IP('255.255.255.255/32'),
        ]
        IPv6_Bogon = [
            IP('::/128'),
            IP('::1/128'),
            IP('::ffff:0:0/96'),
            IP('::/96'),
            IP('100::/64'),
            IP('2001:10::/28'),
            IP('2001:db8::/32'),
            IP('fc00::/7'),
            IP('fe80::/10'),
            IP('fec0::/10'),
            IP('ff00::/8'),
            IP('2002::/24'),
            IP('2002:a00::/24'),
            IP('2002:7f00::/24'),
            IP('2002:a9fe::/32'),
            IP('2002:ac10::/28'),
            IP('2002:c000::/40'),
            IP('2002:c000:200::/40'),
            IP('2002:c0a8::/32'),
            IP('2002:c612::/31'),
            IP('2002:c633:6400::/40'),
            IP('2002:cb00:7100::/40'),
            IP('2002:e000::/20'),
            IP('2002:f000::/20'),
            IP('2002:ffff:ffff::/48'),
            IP('2001::/40'),
            IP('2001:0:a00::/40'),
            IP('2001:0:7f00::/40'),
            IP('2001:0:a9fe::/48'),
            IP('2001:0:ac10::/44'),
            IP('2001:0:c000::/56'),
            IP('2001:0:c000:200::/56'),
            IP('2001:0:c0a8::/48'),
            IP('2001:0:c612::/47'),
            IP('2001:0:c633:6400::/56'),
            IP('2001:0:cb00:7100::/56'),
            IP('2001:0:e000::/36'),
            IP('2001:0:f000::/36'),
            IP('2001:0:ffff:ffff::/64'),
        ]
        try:  # Test for IPv4
            socket.inet_pton(socket.AF_INET, address)
            if any(IP(address) in i for i in IPv4_Bogon):
                return None
            else:
                return str(IP(address)), 'ipv4'
        except socket.error:
            try:  # Test for IPv6
                socket.inet_pton(socket.AF_INET6, address)
                if any(IP(address) in i for i in IPv6_Bogon):
                    return None
                else:
                    return str(IP(address)), 'ipv6'
            except socket.error:  # Test for domain
                if not re.search('[a-zA-Z]', address):
                    return None
                support = None
                try:
                    if any(test_clearnet(i.address) for i in dns.resolve(address, 'A')):
                        support = 'ipv4'
                except dns.NoAnswer:
                    pass
                try:
                    if any(test_clearnet(i.address) for i in dns.resolve(address, 'AAAA')):
                        if support:
                            support = 'dual'
                        else:
                            support = 'ipv6'
                except dns.NoAnswer:
                    pass
                if support:
                    return address, support
                else:
                    return None

    if message.text.strip().lower() == "none" and (
        peer_info['Net_Support']['ipv6']
        or (peer_info['Net_Support']['ipv4'] and not peer_info['Net_Support']['ipv4_nat'])
    ):
        if message.chat.id in db_privilege:
            return 'pre_port_myside', peer_info, message
        else:
            return 'pre_pubkey', peer_info, message

    msg = None
    if test_result := test_clearnet(message.text.strip()):
        if test_result[1] == 'ipv4' and not peer_info['Net_Support']['ipv4']:
            msg = "IPv4 is not supported on this node", "该节点不支持IPv4"
        elif test_result[1] == 'ipv6' and not peer_info['Net_Support']['ipv6']:
            msg = "IPv6 is not supported on this node", "该节点不支持IPv6"
        else:
            peer_info["Clearnet"] = test_clearnet(message.text.strip())[0]
    else:
        msg = "Invalid or unreachable clearnet address", "输入不是有效的公网地址或该地址不可达"
    if msg:
        if message.chat.id not in db_privilege:
            msg = bot.send_message(
                message.chat.id,
                (
                    f"{msg[0]}, please try again.\n"
                    f"{msg[1]}，请重试。\n"
                    f"The check procedure may sometimes be wrong, if it is confirmed to be valid, just resubmit. If the error keeps occurring please contact {config.CONTACT}\n"
                    f"判定程序可能出错。如果确认有效，重新提交即可。重复出错请联系 {config.CONTACT}\n"
                    "Use /cancel to interrupt the operation.\n"
                    "使用 /cancel 终止操作。"
                ),
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return 'post_clearnet', peer_info, msg
        else:
            bot.send_message(
                message.chat.id,
                (
                    "*[Privilege]*\n"
                    f"{msg[0]}.\n"
                    f"{msg[1]}。\n"
                    "Use the privilege to continue the process. Use /cancel to exit if there is a mistake.\n"
                    "使用特权，流程继续。如确认有误使用 /cancel 退出。"
                ),
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove(),
            )
            peer_info["Clearnet"] = message.text.strip()
    return 'pre_clearnet_port', peer_info, message


def pre_clearnet_port(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    if port := peer_info.pop('ClearnetPort', None):
        markup.add(KeyboardButton(port))
    else:
        markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
    msg = bot.send_message(
        message.chat.id,
        "Input your port for WireGuard tunnel.\n请输入你用于 WireGurad 隧道的端口。",
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
                "Invalid port, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的端口，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=markup,
        )
        return 'post_clearnet_port', peer_info, msg
    peer_info["Clearnet"] += f":{message.text.strip()}"
    if message.chat.id in db_privilege:
        return 'pre_port_myside', peer_info, message
    else:
        return 'pre_pubkey', peer_info, message


def pre_port_myside(message, peer_info):
    text = "*[Privilege]*\n" "Enter the port number you provided to your peer-er\n" "请输入你给对方提供的端口号"
    if peer_info["Port"]:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(str(peer_info['Port'])))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
    return 'post_port_myside', peer_info, msg


def post_port_myside(message, peer_info):
    try:
        port = int(message.text.strip())
        if not (0 < port <= 65535):
            raise ValueError
    except ValueError:
        if peer_info["Port"]:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton(str(peer_info['Port'])))
        else:
            markup = ReplyKeyboardRemove()
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid port, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的端口，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=markup,
        )
        return 'post_port_myside', peer_info, msg
    peer_info["Port"] = message.text.strip()
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
        "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
        reply_markup=markup,
    )
    return 'post_pubkey', peer_info, msg


def post_pubkey(message, peer_info):
    if len(message.text.strip()) != 44 or message.text.strip()[-1] != '=':
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid public key, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的公钥，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return 'post_pubkey', peer_info, msg
    peer_info["PublicKey"] = message.text.strip()
    return 'pre_contact', peer_info, message


def pre_contact(message, peer_info):
    if peer_info['Contact']:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(peer_info['Contact']))
    else:
        markup = ReplyKeyboardRemove()
    msg = bot.send_message(
        message.chat.id,
        ("Input your contact information (Telegram or Email)\n" "请输入你的联系方式（Telegram 或 Email）"),
        reply_markup=markup,
    )
    return 'post_contact', peer_info, msg


def post_contact(message, peer_info):
    allowed_punctuation = "!#$%&()*+,-./:;<=>?@[]^_{|}~"
    if message.text.strip() == "" or any(
        c not in (string.ascii_letters + string.digits + allowed_punctuation + ' ') for c in message.text.strip()
    ):
        msg = bot.send_message(
            message.chat.id,
            (
                "Only non-empty strings which contain only upper and lower case letters, numbers, spaces and the following special symbols are accepted.\n"
                "只接受仅由大小写英文字母、数字、空格及以下特殊符号组成的非空字符串。\n"
                "\n"
                f"`{allowed_punctuation}`\n"
                "\n"
                "Please try again. Use /cancel to interrupt the operation.\n"
                "请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown",
        )
        return 'post_contact', peer_info, msg
    peer_info["Contact"] = message.text.strip()
    return 'pre_confirm', peer_info, message


def post_confirm(message, peer_info):
    progress_type = peer_info.pop('ProgressType')
    info_text = peer_info.pop('InfoText')
    if message.text.strip().lower() != "yes":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    try:
        r = requests.post(
            f"http://{peer_info['Region']}.{config.ENDPOINT}:{config.API_PORT}/peer",
            data=json.dumps(peer_info),
            headers={"X-DN42-Bot-Api-Secret-Token": config.API_TOKEN},
            timeout=10,
        )
        if r.status_code == 503:
            bot.send_message(
                message.chat.id,
                (
                    "This node is not open for peer, or has reached its maximum peer capacity.\n"
                    "该节点暂未开放 Peer，或已达最大 Peer 容量。"
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        elif r.status_code != 200:
            raise RuntimeError
    except BaseException:
        bot.send_message(
            message.chat.id,
            (
                f"Error encountered, please try again. If the problem remains, please contact {config.CONTACT}\n"
                f"遇到错误，请重试。如果问题依旧，请联系 {config.CONTACT}"
            ),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if progress_type == 'peer':
        msg_text = 'Peer has been created. Peer 已建立。\n'
    elif progress_type == 'modify':
        msg_text = 'Peer information has been modified. Peer 信息已修改。\n'
    bot.send_message(
        message.chat.id,
        (f"{msg_text}" "\n" "Use /info for related information.\n" "使用 /info 查看相关信息。"),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    if progress_type == 'peer':
        msg_text = 'New Peer!   新 Peer！\n'
    elif progress_type == 'modify':
        msg_text = 'Peer Modified!   Peer 信息修改！\n'
    for i in db_privilege - {message.chat.id}:
        text = "*[Privilege]*\n" f"{msg_text}" f"```\n{info_text}```"
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        if peer_info['ASN'] == db[i]:
            text += "\n\nAlready as this user 已在该身份"
            markup.add(
                InlineKeyboardButton(
                    "Show info | 查看信息",
                    url=f"https://t.me/{config.BOT_USERNAME}?start=info",
                )
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    "Switch to it | 切换至该身份",
                    url=f"https://t.me/{config.BOT_USERNAME}?start=whoami_{peer_info['ASN']}",
                )
            )
        bot.send_message(i, text, parse_mode="Markdown", reply_markup=markup)
