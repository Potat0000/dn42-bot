# -*- coding: utf-8 -*-
import re
import socket
import string

import config
from base import bot, db_privilege
from IPy import IP
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


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
    if peer_info['Request-LinkLocal'] != 'Not required due to not use LLA as IPv6':
        markup.add(KeyboardButton(peer_info['Request-LinkLocal']))
    else:
        markup.add(KeyboardButton("Auto"))
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
    if message.text.strip().lower() != "auto":
        try:  # Test for IPv6
            socket.inet_pton(socket.AF_INET6, message.text.strip())
            if IP(message.text.strip()) not in IP("fe80::/64"):
                raise ValueError
        except (socket.error, ValueError):
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton("Auto"))
            msg = bot.send_message(
                message.chat.id,
                (
                    "Invalid DN42 IPv6 Link-Local address, please try again. Use /cancel to interrupt the operation.\n"
                    "输入不是有效的 DN42 IPv6 Link-Local 地址，请重试。使用 /cancel 终止操作。"
                ),
                reply_markup=markup,
            )
            return 'post_request_linklocal', peer_info, msg
        peer_info["Request-LinkLocal"] = message.text.strip()
    else:
        peer_info["Request-LinkLocal"] = "Not specified"
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
    msg = bot.send_message(
        message.chat.id,
        (
            "Input your clearnet address for WireGuard tunnel, without port.\n"
            "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
            "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
            "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
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
                return str(IP(address))
        except socket.error:
            try:  # Test for IPv6
                socket.inet_pton(socket.AF_INET6, address)
                if any(IP(address) in i for i in IPv6_Bogon):
                    return None
                else:
                    return str(IP(address))
            except socket.error:
                if not re.search('[a-zA-Z]', address):
                    return None
                try:  # Test for domain
                    if test_clearnet(socket.gethostbyname(address)) is not None:
                        return address
                except socket.error:
                    return None

    if message.text.strip().lower() != "none":
        if test_clearnet(message.text.strip()):
            peer_info["Clearnet"] = test_clearnet(message.text.strip())
        else:
            if message.chat.id not in db_privilege:
                msg = bot.send_message(
                    message.chat.id,
                    (
                        "Invalid or unreachable clearnet address, please try again.\n"
                        "输入不是有效的公网地址或该地址不可达，请重试。\n"
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
                        "Invalid or unreachable clearnet address.\n"
                        "输入不是有效的公网地址或该地址不可达。\n"
                        "Use the privilege to continue the process. Use /cancel to exit if there is a mistake.\n"
                        "使用特权，流程继续。如确认有误使用 /cancel 退出。"
                    ),
                    parse_mode='Markdown',
                    reply_markup=ReplyKeyboardRemove(),
                )
                peer_info["Clearnet"] = message.text.strip()
        return 'pre_clearnet_port', peer_info, message
    else:
        if message.chat.id in db_privilege:
            return 'pre_port_myside', peer_info, message
        else:
            return 'pre_pubkey', peer_info, message


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
