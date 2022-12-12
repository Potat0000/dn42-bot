# -*- coding: utf-8 -*-
import json
import socket
import string
from functools import partial

import config
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


@bot.message_handler(commands=['peer'], is_private_chat=True)
def start_peer(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "Login with /login first!\n请先使用 /login 登录！",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    peer_info = tools.get_info(db[message.chat.id])
    could_peer = [config.SERVER[i] for i in set(config.SERVER.keys()) - set(peer_info.keys())]
    if could_peer == []:
        bot.send_message(
            message.chat.id,
            (
                "You already peer with all my nodes.\n"
                "你已经和我的所有节点 Peer 了。\n"
                "\n"
                "Use /info for more information.\n"
                "使用 /info 查看更多信息。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if (db[message.chat.id] // 10000 != 424242) and (message.chat.id not in db_privilege):
        bot.send_message(
            message.chat.id,
            (
                f"Your ASN is not in standard DN42 format (<code>AS424242xxxx</code>), so it cannot be auto-peered, please contact {config.CONTACT} for manual peer.\n"
                f"你的 ASN 不是标准 DN42 格式 (<code>AS424242xxxx</code>)，因此无法进行 AutoPeer，请联系 {config.CONTACT} 进行人工 Peer。"
            ),
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    bot.send_message(
        message.chat.id,
        (
            "You will peer with me through the following identity:\n"
            "你将通过以下身份与我 Peer：\n"
            f"<code>AS{db[message.chat.id]}</code>\n"
            "\n"
            "If it is wrong, please use /cancel to interrupt the operation.\n"
            "如果有误请输入 /cancel 终止操作。\n"
            "\n"
            f"Any problems with the AutoPeer process, please contact {config.CONTACT}\n"
            f"AutoPeer 过程中产生任何问题，请联系 {config.CONTACT}"
        ),
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    for i in could_peer:
        markup.add(KeyboardButton(i))
    msg = bot.send_message(
        message.chat.id,
        "Which of my nodes do you want to peer with?\n你想要与我的哪个节点 Peer？",
        reply_markup=markup,
    )
    bot.register_next_step_handler(msg, partial(peer_node_choose, could_peer))


def peer_node_choose(could_peer, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip() not in could_peer:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in could_peer:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_node_choose, could_peer))
        return

    peer_info = {
        "Region": next(k for k, v in config.SERVER.items() if v == message.text.strip()),
        "ASN": db[message.chat.id],
        "Channel": None,
        "MP-BGP": "Not supported",
        "ENH": None,
        "IPv6": "Not enabled",
        "IPv4": "Not enabled",
        "Request-LinkLocal": "Not required due to not use LLA as IPv6",
        "Clearnet": None,
        "PublicKey": None,
        "Port": None,
        "Contact": None,
    }
    if db[message.chat.id] // 10000 == 424242:
        peer_info["Port"] = str(peer_info['ASN'])[-5:]

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 3
    markup.add(KeyboardButton("IPv6 & IPv4"), KeyboardButton("IPv6 only"), KeyboardButton("IPv4 only"))
    msg = bot.send_message(
        message.chat.id,
        "What routes do you want to transmit with me?\n你想和我传递哪些路由？",
        reply_markup=markup,
    )
    bot.register_next_step_handler(msg, partial(peer_session_type, peer_info))


def ask_ipv6(message, peer_info):
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
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_ipv6_input, peer_info))


def ask_ipv4(message, peer_info):
    msg = bot.send_message(
        message.chat.id,
        ("Input your DN42 IPv4 address, without `/L` suffix.\n" "请输入你的 DN42 IPv4 地址，不包含 `/L` 后缀。"),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_ipv4_input, peer_info))


def peer_session_type(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if (
        message.text.strip().lower() == "ipv6 & ipv4"
        or message.text.strip().lower() == "ipv6 and ipv4"
        or message.text.strip().lower() == "both"
    ):
        peer_info["Channel"] = "IPv6 & IPv4"

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            "Do you support Multiprotocol BGP?\n你支持多协议 BGP 吗？",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_support, peer_info))
    elif message.text.strip().lower() == "ipv6 only" or message.text.strip().lower() == "ipv6":
        peer_info["Channel"] = "IPv6 only"
        ask_ipv6(message, peer_info)
    elif message.text.strip().lower() == "ipv4 only" or message.text.strip().lower() == "ipv4":
        peer_info["Channel"] = "IPv4 only"
        ask_ipv4(message, peer_info)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 3
        markup.add(KeyboardButton("IPv6 & IPv4"), KeyboardButton("IPv6 only"), KeyboardButton("IPv4 only"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, peer_session_type)


def peer_mpbgp_support(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip().lower() == "yes":

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("IPv6"), KeyboardButton("IPv4"))
        msg = bot.send_message(
            message.chat.id,
            ("What address do you want to use to establish an MP-BGP session with me?\n" "你想使用什么地址与我建立多协议 BGP 会话？"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_type, peer_info))
    elif message.text.strip().lower() == "no":
        ask_ipv6(message, peer_info)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_support, peer_info))


def peer_mpbgp_type(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip().lower() == "ipv6":
        peer_info["MP-BGP"] = "IPv6"

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            "Do you support Extended Next Hop?\n你支持扩展的下一跳吗？",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_enh_support, peer_info))
    elif message.text.strip().lower() == "ipv4":
        peer_info["MP-BGP"] = "IPv4"
        ask_ipv6(message, peer_info)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("IPv6"), KeyboardButton("IPv4"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_type, peer_info))


def peer_enh_support(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
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
        bot.register_next_step_handler(msg, partial(peer_enh_support, peer_info))
        return
    ask_ipv6(message, peer_info)


def peer_ipv6_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
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
        bot.register_next_step_handler(msg, partial(peer_ipv6_input, peer_info))
        return
    peer_info["IPv6"] = message.text.strip()
    if IP(message.text.strip()) in IP("fe80::/64"):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton("Auto"))
        msg = bot.send_message(
            message.chat.id,
            (
                "Link-Local address detected. You can enter the address required on my side as needed, without `/L` suffix.\n"
                "检测到 Link-Local 地址。你可以按需输入所需的我这边的地址，不包含 `/L` 后缀。\n\n"
                "If you don't know what this is, or don't need to specify it, select `Auto`.\n"
                "如果你不知道这是什么，或者不需要指定，请选择 `Auto`。"
            ),
            parse_mode="Markdown",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_request_linklocal_input, peer_info))
    else:
        if peer_info["Channel"] == "IPv6 & IPv4" and peer_info["ENH"] is not True:
            ask_ipv4(message, peer_info)
        else:
            msg = bot.send_message(
                message.chat.id,
                (
                    "Input your clearnet address for WireGuard tunnel, without port.\n"
                    "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
                    "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
                    "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
                ),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )
            bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))


def peer_request_linklocal_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
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
            bot.register_next_step_handler(msg, partial(peer_request_linklocal_input, peer_info))
            return
        peer_info["Request-LinkLocal"] = message.text.strip()
    else:
        peer_info["Request-LinkLocal"] = "Not specified"
    if peer_info["Channel"] == "IPv6 & IPv4" and peer_info["ENH"] is not True:
        ask_ipv4(message, peer_info)
    else:
        msg = bot.send_message(
            message.chat.id,
            (
                "Input your clearnet address for WireGuard tunnel, without port.\n"
                "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
                "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
                "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))


def peer_ipv4_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
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
        bot.register_next_step_handler(msg, partial(peer_ipv4_input, peer_info))
        return
    peer_info["IPv4"] = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        (
            "Input your clearnet address for WireGuard tunnel, without port.\n"
            "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
            "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
            "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
        ),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))


def peer_clearnet_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if message.text.strip().lower() != "none":
        if tools.test_clearnet(message.text.strip()):
            peer_info["Clearnet"] = tools.test_clearnet(message.text.strip())
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
                bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))
                return
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
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
        msg = bot.send_message(
            message.chat.id,
            "Input your port for WireGuard tunnel.\n请输入你用于 WireGurad 隧道的端口。",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_port_input, peer_info))
    else:
        if message.chat.id in db_privilege:
            text = "*[Privilege]*\n" "Enter the port number you provided to your peer-er\n" "请输入你给对方提供的端口号"
            if peer_info["Port"]:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row_width = 1
                markup.add(KeyboardButton(str(peer_info['Port'])))
            else:
                markup = ReplyKeyboardRemove()
            msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler(msg, partial(peer_myside_port_input_admin, peer_info))
        else:
            msg = bot.send_message(
                message.chat.id,
                "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
                reply_markup=ReplyKeyboardRemove(),
            )
            bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))


def peer_port_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

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
        bot.register_next_step_handler(msg, partial(peer_port_input, peer_info))
        return
    peer_info["Clearnet"] += f":{message.text.strip()}"
    if message.chat.id in db_privilege:
        text = "*[Privilege]*\n" "Enter the port number you provided to your peer-er\n" "请输入你给对方提供的端口号"
        if peer_info["Port"]:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton(str(peer_info['Port'])))
        else:
            markup = ReplyKeyboardRemove()
        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler(msg, partial(peer_myside_port_input_admin, peer_info))
    else:
        msg = bot.send_message(
            message.chat.id,
            "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))


def peer_myside_port_input_admin(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

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
        bot.register_next_step_handler(msg, partial(peer_myside_port_input_admin, peer_info))
        return
    peer_info["Port"] = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))


def peer_pubkey_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if len(message.text.strip()) != 44 or message.text.strip()[-1] != '=':
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid public key, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的公钥，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))
        return
    peer_info["PublicKey"] = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        ("Input your contact information (Telegram or Email)\n" "请输入你的联系方式（Telegram 或 Email）"),
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_contact_input, peer_info))


def peer_contact_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
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
        bot.register_next_step_handler(msg, partial(peer_contact_input, peer_info))
        return
    peer_info["Contact"] = message.text.strip()
    all_text = (
        "Region:\n"
        f"    {config.SERVER[peer_info['Region']]}\n"
        "Basic:\n"
        f"    ASN:         AS{peer_info['ASN']}\n"
        f"    Channel:     {peer_info['Channel']}\n"
        f"    MP-BGP:      {peer_info['MP-BGP']}\n"
        f"    IPv6:        {peer_info['IPv6']}\n"
        f"    IPv4:        {peer_info['IPv4']}\n"
        f"    Request-LLA: {peer_info['Request-LinkLocal']}\n"
        "Tunnel:\n"
        f"    Endpoint:    {peer_info['Clearnet']}\n"
        f"    PublicKey:   {peer_info['PublicKey']}\n"
        "Contact:\n"
        f"    {peer_info['Contact']}\n"
    )
    msg = bot.send_message(
        message.chat.id,
        (
            "Please check all your information\n"
            "请确认你的信息\n"
            "\n"
            f"```\n{all_text}```\n"
            "Please enter `yes` to confirm. 确认无误请输入 `yes`。\n"
            "All other inputs indicate the cancellation of the operation.\n"
            "所有其他输入表示取消操作。"
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_confirm, peer_info))


def peer_confirm(peer_info, message):
    if message.text.strip().lower() == "yes":
        try:
            r = requests.post(
                f"http://{peer_info['Region']}.{config.ENDPOINT}:{config.API_PORT}/peer",
                data=json.dumps(peer_info),
                headers={"X-DN42-Bot-Api-Secret-Token": config.API_TOKEN},
                timeout=10,
            )
            if r.status_code != 200:
                raise RuntimeError
            bot.send_message(
                message.chat.id,
                ("Peer has been created. Peer 已建立。\n" "\n" "Use /info for related information.\n" "使用 /info 查看相关信息。"),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )

            def gen_privilege_markup():
                markup = InlineKeyboardMarkup()
                markup.row_width = 1
                markup.add(
                    InlineKeyboardButton(
                        "Switch to it | 切换至该身份",
                        url=f"https://t.me/{config.BOT_USERNAME}?start=whoami_{peer_info['ASN']}",
                    )
                )
                return markup

            for i in db_privilege - {message.chat.id}:
                text = (
                    "*[Privilege]*\n"
                    "New Peer!   新 Peer！\n"
                    f"`{tools.get_asn_mnt_text(peer_info['ASN'])}`\n"
                    f"`{config.SERVER[peer_info['Region']]}`"
                )
                markup = ReplyKeyboardRemove()
                if peer_info['ASN'] == db[i]:
                    text += "\n\nAlready as this user 已在该身份"
                else:
                    markup = gen_privilege_markup()
                bot.send_message(i, text, parse_mode="Markdown", reply_markup=markup)
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
    else:
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
