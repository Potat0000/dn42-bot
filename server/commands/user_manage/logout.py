import pickle

import tools
from base import bot, db, db_privilege
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=['logout'], is_private_chat=True)
def start_logout(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            'You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login',
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        text = (
            f'You have logged out as `{tools.get_asn_mnt_text(db[message.chat.id])}`.\n'
            f'你已经退出 `{tools.get_asn_mnt_text(db[message.chat.id])}` 身份。'
        )
        db.pop(message.chat.id)
        if message.chat.id in db_privilege:
            db_privilege.remove(message.chat.id)
            text = '*[Privilege]*\n' + text
        with open('./user_db.pkl', 'wb') as f:
            pickle.dump((db, db_privilege), f)
        bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
