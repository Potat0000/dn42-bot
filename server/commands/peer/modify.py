from collections.abc import Iterable
from functools import partial

import base
import commands.peer.info_collect as info_collect
import config
import tools
from base import bot, db, db_privilege
from IPy import IP
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['modify'], is_private_chat=True)
def start_modify(message):
    step_manage('init', {}, None, message)


def step_manage(next_step, peer_info, stop_sign, message):
    def _call(func):
        if message:
            rtn = func(message, peer_info)
        else:
            rtn = func(peer_info)
        if rtn:
            if len(rtn) == 3:
                rtn_next_step, rtn_peer_info, rtn_msg = rtn
                rtn_stop_sign = stop_sign
            elif len(rtn) == 4:
                rtn_next_step, rtn_peer_info, rtn_msg, rtn_stop_sign = rtn
            if rtn_next_step.startswith('post_'):
                bot.register_next_step_handler(
                    rtn_msg, partial(step_manage, rtn_next_step, rtn_peer_info, rtn_stop_sign)
                )
            elif rtn_next_step.startswith('pre_'):
                step_manage(rtn_next_step, rtn_peer_info, rtn_stop_sign, rtn_msg)

    if message.text.strip() == '/cancel':
        bot.send_message(
            message.chat.id,
            'Current operation has been cancelled.\n当前操作已被取消。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if stop_sign:
        if (not isinstance(stop_sign, Iterable) and next_step == stop_sign) or (
            isinstance(stop_sign, Iterable) and next_step in stop_sign
        ):
            step_manage('pre_action_choose', peer_info, None, message)
            return
    if next_step in globals() and callable(globals()[next_step]):
        _call(globals()[next_step])
    else:
        _call(getattr(info_collect, next_step))


def get_diff_text(old_peer_info, peer_info):
    diff_text = ''

    def diff_print(item, prefix=''):
        nonlocal diff_text
        if peer_info[item] == old_peer_info[item]:
            diff_text += f'    {prefix}{peer_info[item]}\n'
        else:
            diff_text += f'    {prefix}{old_peer_info[item]}\n'
            diff_text += ' ' * (len(prefix) + 2) + '->\n'
            diff_text += ' ' * (len(prefix) + 4) + f'{peer_info[item]}\n'

    diff_text += 'Region:\n'
    if peer_info['Region'] == old_peer_info['Region']:
        diff_text += f"    {base.servers[peer_info['Region']]}\n"
    else:
        peer_info['Origin'] = old_peer_info['Region']
        diff_text += f"    {base.servers[old_peer_info['Region']]}\n"
        diff_text += '  ->\n'
        diff_text += f"    {base.servers[peer_info['Region']]}\n"
    diff_text += 'Basic:\n'
    diff_print('ASN', 'ASN:         ')
    diff_print('Channel', 'Channel:     ')
    diff_print('MP-BGP', 'MP-BGP:      ')
    diff_print('IPv6', 'IPv6:        ')
    diff_print('IPv4', 'IPv4:        ')
    diff_print('Request-LinkLocal', 'Request-LLA: ')
    diff_text += 'Tunnel:\n'
    diff_print('Clearnet', 'Endpoint:    ')
    diff_print('PublicKey', 'PublicKey:   ')
    diff_text += 'Contact:\n'
    diff_print('Contact')
    return diff_text


def init(message, peer_info):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            'You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    peer_info = tools.get_info(db[message.chat.id])
    if not peer_info:
        bot.send_message(
            message.chat.id,
            ('You are not peer with me yet, you can use /peer to start.\n' '你还没有与我 Peer，可以使用 /peer 开始。'),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    bot.send_message(
        message.chat.id,
        (
            'You will modify a peer with me through the following identity:\n'
            '你将通过以下身份修改一个与我的 Peer：\n'
            f'<code>{tools.get_asn_mnt_text(db[message.chat.id])}</code>\n'
            '\n'
            'If it is wrong, please use /cancel to interrupt the operation.\n'
            '如果有误请输入 /cancel 终止操作。\n'
            '\n'
            f'Any problems with the modification process, please contact {config.CONTACT}\n'
            f'修改过程中产生任何问题，请联系 {config.CONTACT}'
        ),
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )
    return 'pre_node_choose', peer_info, message


def pre_node_choose(message, peer_info):
    if len(peer_info) == 1:
        could_chosen = base.servers[list(peer_info.keys())[0]]
        bot.send_message(
            message.chat.id,
            (
                f'Only one available node, automatically select `{could_chosen}`\n'
                f'只有一个可选节点，自动选择 `{could_chosen}`\n'
                '\n'
                'If not wanted, use /cancel to interrupt the operation.\n'
                '如非所需，使用 /cancel 终止操作。'
            ),
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
        return post_node_choose(message, peer_info, could_chosen)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in peer_info:
            markup.add(KeyboardButton(base.servers[i]))
        msg = bot.send_message(
            message.chat.id,
            "Which node's peer information do you want to change?\n你想要修改哪个节点的 Peer 信息？",
            reply_markup=markup,
        )
        return 'post_node_choose', peer_info, msg


def post_node_choose(message, peer_info, chosen=None):
    if not chosen:
        chosen = message.text.strip()
    try:
        chosen = next(k for k, v in base.servers.items() if v == chosen)
    except StopIteration:
        chooseable = [base.servers[i] for i in tools.get_info(db[message.chat.id])]
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in chooseable:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_node_choose', peer_info, msg

    raw_info = tools.get_info(db[message.chat.id])
    if not isinstance(raw_info[chosen], dict):
        bot.send_message(
            message.chat.id,
            (
                f'Error encountered! Please contact {config.CONTACT} the following error message\n'
                f'遇到错误！请附带下属错误信息联系 {config.CONTACT}\n'
                f'<code>{raw_info[chosen]}</code>'
            ),
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    raw_info = raw_info[chosen]
    peer_info = {
        'Region': chosen,
        'ASN': db[message.chat.id],
        'Channel': None,
        'MP-BGP': 'Not supported',
        'ENH': None,
        'IPv6': raw_info['v6'] if raw_info['v6'] else 'Not enabled',
        'IPv4': raw_info['v4'] if raw_info['v4'] else 'Not enabled',
        'Request-LinkLocal': 'Not required due to not use LLA as IPv6',
        'Clearnet': raw_info['clearnet'],
        'PublicKey': raw_info['pubkey'],
        'Port': raw_info['port'],
        'Contact': raw_info['desc'],
        'Net_Support': raw_info['net_support'],
        'Provide-LinkLocal': raw_info['lla'],
    }
    if raw_info['v6'] and IP(raw_info['v6']) in IP('fe80::/64'):
        peer_info['Request-LinkLocal'] = raw_info['my_v6']
    if raw_info['session'] == 'IPv6 Session with IPv6 channel only':
        peer_info['Channel'] = 'IPv6 only'
    elif raw_info['session'] == 'IPv4 Session with IPv4 channel only':
        peer_info['Channel'] = 'IPv4 only'
    else:
        peer_info['Channel'] = 'IPv6 & IPv4'
        if raw_info['session'] == 'IPv6 Session with IPv6 & IPv4 Channels':
            peer_info['MP-BGP'] = 'IPv6'
            if peer_info['IPv4'] == 'Not enabled':
                peer_info['ENH'] = True
            else:
                peer_info['ENH'] = False
        elif raw_info['session'] == 'IPv4 Session with IPv6 & IPv4 Channels':
            peer_info['MP-BGP'] = 'IPv4'
    peer_info['backup'] = peer_info.copy()
    return 'pre_first_action_choose', peer_info, message


def pre_first_action_choose(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton('Region'), KeyboardButton('Clearnet Endpoint'))
    markup.row(KeyboardButton('Session Type'), KeyboardButton('WireGuard PublicKey'))
    markup.row(KeyboardButton('DN42 IP'), KeyboardButton('Contact'))
    markup.row(KeyboardButton('Finish modification'), KeyboardButton('Abort modification'))
    msg = bot.send_message(
        message.chat.id,
        (
            'Select the item to be modified:\n'
            '选择想要修改的内容：\n'
            '\n'
            '- `Region`\n'
            '  Migration to another node\n'
            '  迁移到另一节点\n'
            '- `Session Type`\n'
            '  Change BGP session type (MP-BGP, ENH)\n'
            '  修改 BGP 会话类型 (多协议 BGP、扩展的下一跳)\n'
            '- `DN42 IP`\n'
            '  Change DN42 IP (Include IPv6 & IPv4)\n'
            '  修改 DN42 IP 地址 (含 IPv6 及 IPv4)\n'
            '- `Clearnet Endpoint`\n'
            '  Change clearnet endpoint and port of WireGuard tunnel\n'
            '  修改用于 WireGurad 隧道的公网地址及端口\n'
            '- `WireGuard PublicKey`\n'
            '  Change public key of WireGuard tunnel\n'
            '  修改 WireGuard 公钥\n'
            '- `Contact`\n'
            '  Change contact\n'
            '  修改联系方式\n'
            '\n'
            '- `Finish modification`\n'
            '  Finish modification and submit\n'
            '  完成修改并提交\n'
            '- `Abort modification`\n'
            '  Abort modification (equivalent to /cancel)\n'
            '  放弃修改 (相当于 /cancel)\n'
        ),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_action_choose', peer_info, msg


def pre_action_choose(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton('Region'), KeyboardButton('Clearnet Endpoint'))
    markup.row(KeyboardButton('Session Type'), KeyboardButton('WireGuard PublicKey'))
    markup.row(KeyboardButton('DN42 IP'), KeyboardButton('Contact'))
    markup.row(KeyboardButton('Finish modification'), KeyboardButton('Abort modification'))

    diff_text = get_diff_text(peer_info['backup'], peer_info)
    msg = bot.send_message(
        message.chat.id,
        (
            'You have modified the following information\n'
            '已修改以下信息\n'
            '\n'
            f'```ModifiedInfo\n{diff_text}```\n'
            'You can continue to modify, or choose to `Finish modification` or `Abort modification`.\n'
            '你可以继续修改，或者选择 `Finish modification` 以提交，或者选择 `Abort modification` 放弃修改。\n'
        ),
        parse_mode='Markdown',
        reply_markup=markup,
    )
    return 'post_action_choose', peer_info, msg


def post_action_choose(message, peer_info):
    if message.text.strip() not in [
        'Region',
        'Session Type',
        'DN42 IP',
        'Clearnet Endpoint',
        'WireGuard PublicKey',
        'Contact',
        'Finish modification',
        'Abort modification',
    ]:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(KeyboardButton('Region'), KeyboardButton('Clearnet Endpoint'))
        markup.row(KeyboardButton('Session Type'), KeyboardButton('WireGuard PublicKey'))
        markup.row(KeyboardButton('DN42 IP'), KeyboardButton('Contact'))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        return 'post_action_choose', peer_info, msg
    if message.text.strip() == 'Region':
        if (db[message.chat.id] // 10000 != 424242) and (message.chat.id not in db_privilege):
            bot.send_message(
                message.chat.id,
                (
                    f'Your ASN is not in standard DN42 format (<code>AS424242xxxx</code>), so it cannot be auto-migrated, please contact {config.CONTACT} for manual handling.\n'
                    f'你的 ASN 不是标准 DN42 格式 (<code>AS424242xxxx</code>)，因此无法进行转移，请联系 {config.CONTACT} 进行人工处理。'
                ),
                parse_mode='HTML',
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        return 'pre_region', peer_info, message, 'pre_session_type'
    elif message.text.strip() == 'Session Type':
        return 'pre_session_type', peer_info, message, 'pre_clearnet'
    elif message.text.strip() == 'DN42 IP':
        if peer_info['Channel'] == 'IPv4 only':
            return 'pre_ipv4', peer_info, message, 'pre_clearnet'
        else:
            return 'pre_ipv6', peer_info, message, 'pre_clearnet'
    elif message.text.strip() == 'Clearnet Endpoint':
        return 'pre_clearnet', peer_info, message, 'pre_pubkey'
    elif message.text.strip() == 'WireGuard PublicKey':
        return 'pre_pubkey', peer_info, message, 'pre_contact'
    elif message.text.strip() == 'Contact':
        return 'pre_contact', peer_info, message, 'pre_confirm'
    elif message.text.strip() == 'Finish modification':
        return 'pre_confirm', peer_info, message
    elif message.text.strip() == 'Abort modification':
        bot.send_message(
            message.chat.id,
            'Abort modification, operation has been canceled.\n放弃修改，操作已取消。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return


def pre_confirm(message, peer_info):
    old_peer_info = peer_info.pop('backup')
    if old_peer_info == peer_info:
        msg = bot.send_message(
            message.chat.id,
            'No changes detected, operation cancelled.\n未检测到任何变更，操作已取消。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    diff_text = get_diff_text(old_peer_info, peer_info)
    msg = bot.send_message(
        message.chat.id,
        (
            'Please check all your information\n'
            '请确认你的信息\n'
            '\n'
            f'```ComfirmInfo\n{diff_text}```\n'
            'Please enter `yes` to confirm. All other inputs indicate the cancellation of the operation.\n'
            '确认无误请输入 `yes`，所有其他输入表示取消操作。'
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    peer_info['InfoText'] = diff_text
    peer_info['ProgressType'] = 'modify'
    return 'post_confirm', peer_info, msg
