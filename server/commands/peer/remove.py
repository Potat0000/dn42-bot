from functools import partial

import base
import config
import requests
import tools
from base import bot, db, db_privilege
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['remove'], is_private_chat=True)
def remove_peer(message):
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
            'You will remove a peer with me through the following identity:\n'
            '你将通过以下身份删除一个与我的 Peer：\n'
            f'`{tools.get_asn_mnt_text(db[message.chat.id])}`\n'
            '\n'
            'If it is wrong, please use /cancel to interrupt the operation.\n'
            '如果有误请输入 /cancel 终止操作。\n'
            '\n'
            f'Any problems with the removal process, please contact {config.CONTACT}\n'
            f'删除过程中产生任何问题，请联系 {config.CONTACT}'
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )

    if offline_servers := set(config.SERVER.values()) - set(base.servers.values()):
        msg = 'The following servers are currently offline, please try again later:\n以下服务器目前处于离线状态，如有需要请稍后再试：'
        for i in offline_servers:
            msg += f'\n`{i}`'
        bot.send_message(
            message.chat.id,
            msg,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )

    removable = [base.servers[i] for i in peer_info.keys()]

    if len(removable) == 1:
        could_chosen = removable[0]
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
        remove_peer_choose(removable, could_chosen, message)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in removable:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            'Which node do you want to delete the information with?\n你想要删除与哪个节点的信息？',
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(remove_peer_choose, removable, None))


def remove_peer_choose(removable, chosen, message):
    if not chosen:
        chosen = message.text.strip()
    if chosen == '/cancel':
        bot.send_message(
            message.chat.id,
            'Current operation has been cancelled.\n当前操作已被取消。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if chosen not in removable:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in removable:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ('Invalid input, please try again. Use /cancel to interrupt the operation.\n' '输入不正确，请重试。使用 /cancel 终止操作。'),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(remove_peer_choose, removable, None))
        return

    chosen = next(k for k, v in base.servers.items() if v == chosen)
    code = tools.gen_random_code(32)
    if db[message.chat.id] // 10000 == 424242:
        bot.send_message(
            message.chat.id,
            (
                f'Peer information with `{base.servers[chosen]}` will be deleted (including BGP Sessions and WireGuard tunnels), and you can always re-create it using /peer.\n'
                f'将要删除与 `{base.servers[chosen]}` 的 Peer 信息（包括 BGP Session 和 WireGuard 隧道），你可以随时使用 /peer 重新建立。\n\n'
                'If you want to modify Peer information, you can use the /modify command instead of deleting and recreating.\n'
                '如果你想要修改 Peer 信息，可以使用 /modify 命令，而无需删除再重建。'
            ),
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        bot.send_message(
            message.chat.id,
            (
                f'Peer information with `{base.servers[chosen]}` will be deleted (including BGP Sessions and WireGuard tunnels).\n'
                f'将要删除与 `{base.servers[chosen]}` 的 Peer 信息（包括 BGP Session 和 WireGuard 隧道）。\n\n'
                'If you want to modify Peer information, you can use the /modify command instead of deleting and recreating.\n'
                '如果你想要修改 Peer 信息，可以使用 /modify 命令，而无需删除再重建。\n\n'
                '**Attention 注意**\n\n'
                'Your ASN is not in standard DN42 format (`AS424242xxxx`), so it cannot be auto-peered\n'
                '你的 ASN 不是标准 DN42 格式 (`AS424242xxxx`)，因此无法进行 AutoPeer\n'
                f'After deleting peer information, you need to contact {config.CONTACT} for manual operation if you need to re-peer.\n'
                f'删除 Peer 信息后，如需重新 Peer，需要联系 {config.CONTACT} 进行人工操作。'
            ),
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
    msg = bot.send_message(
        message.chat.id,
        (
            'Enter the following random code to confirm the deletion.\n'
            '输入以下随机码以确认删除。\n'
            '\n'
            f'`{code}`\n'
            '\n'
            'All other inputs indicate the cancellation of the operation.\n'
            '所有其他输入表示取消操作。'
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(remove_peer_confirm, code, chosen))


def remove_peer_confirm(code, region, message):
    if message.text.strip() == code:
        try:
            if region in config.HOSTS:
                api = config.HOSTS[region]
            else:
                api = f'{region}.{config.ENDPOINT}'
            r = requests.post(
                f'http://{api}:{config.API_PORT}/remove',
                data=str(db[message.chat.id]),
                headers={'X-DN42-Bot-Api-Secret-Token': config.API_TOKEN},
                timeout=10,
            )
            if r.status_code != 200:
                raise RuntimeError
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
        if db[message.chat.id] // 10000 == 424242:
            bot.send_message(
                message.chat.id,
                (
                    'Peer information has been deleted.\n'
                    'Peer 信息已删除。\n'
                    '\n'
                    'You can always re-create it using /peer.\n'
                    '你可以随时使用 /peer 重新建立。'
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            bot.send_message(
                message.chat.id,
                (
                    'Peer information has been deleted.\n'
                    'Peer 信息已删除。\n'
                    '\n'
                    f'Contact {config.CONTACT} if you need to re-peer.\n'
                    f'如需重新 Peer 请联系 {config.CONTACT}'
                ),
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove(),
            )
        for i in db_privilege - {message.chat.id}:
            bot.send_message(
                i,
                (
                    '*[Privilege]*\n'
                    'Peer Removed!   有 Peer 被删除！\n'
                    f'`{tools.get_asn_mnt_text(db[message.chat.id])}`\n'
                    f'`{base.servers[region]}`'
                ),
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove(),
            )
    else:
        bot.send_message(
            message.chat.id,
            'Current operation has been cancelled.\n当前操作已被取消。',
            reply_markup=ReplyKeyboardRemove(),
        )
