import pickle

import tools
from base import bot, db, db_privilege
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['whoami'], is_private_chat=True)
def whoami(message, new_asn=None, info_node=None):
    if new_asn and message.chat.id not in db_privilege:
        if message.chat.id not in db:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton(text='Login now | 立即登录', url=f'https://t.me/{bot.get_me().username}?start=login')
            )
        else:
            markup = ReplyKeyboardRemove()
        bot.send_message(
            message.chat.id,
            "You are not allowed to switch to other's ASN directly.\n你无权直接切换至他人的 ASN。",
            reply_markup=markup,
        )
    elif message.chat.id not in db:
        tools.gen_login_message(message)
    elif message.chat.id in db_privilege:
        if not new_asn and len(message.text.split()) == 2:
            new_asn = message.text.split()[1]
        new_asn = tools.extract_asn(new_asn, privilege=True)
        if new_asn:
            db[message.chat.id] = new_asn
            with open('./user_db.pkl', 'wb') as f:
                pickle.dump((db, db_privilege), f)
            if not info_node:
                info_node = ''
            markup = InlineKeyboardMarkup()
            markup.row_width = 1
            markup.add(
                InlineKeyboardButton(
                    'Show info | 查看信息',
                    url=f'https://t.me/{bot.get_me().username}?start=info_{new_asn}_{info_node}',
                )
            )
        else:
            markup = ReplyKeyboardRemove()
        bot.send_message(
            message.chat.id,
            '*[Privilege]*\nCurrent login user:\n当前登录用户：\n' f'`{tools.get_asn_mnt_text(db[message.chat.id])}`',
            parse_mode='Markdown',
            reply_markup=markup,
        )
    else:
        bot.send_message(
            message.chat.id,
            'Current login user:\n当前登录用户：\n' f'`{tools.get_asn_mnt_text(db[message.chat.id])}`',
            reply_markup=ReplyKeyboardRemove(),
        )
