import pickle

import config
import tools
from base import bot, db, db_privilege
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['whoami'], is_private_chat=True)
def whoami(message, new_asn=None, info_node=None):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    markup = ReplyKeyboardRemove()
    if message.chat.id in db_privilege:
        text = "*[Privilege]*\n"
        if not new_asn and len(message.text.split()) == 2:
            new_asn = message.text.split()[1]
        if new_asn:
            try:
                db[message.chat.id] = int(new_asn)
                with open('./user_db.pkl', 'wb') as f:
                    pickle.dump((db, db_privilege), f)
            except BaseException:
                pass
            else:

                def gen_privilege_markup():
                    if info_node:
                        info_node_text = f'_{info_node}'
                    else:
                        info_node_text = ''
                    markup = InlineKeyboardMarkup()
                    markup.row_width = 1
                    markup.add(
                        InlineKeyboardButton(
                            "Show info | 查看信息",
                            url=f"https://t.me/{config.BOT_USERNAME}?start=info{info_node_text}",
                        )
                    )
                    return markup

                markup = gen_privilege_markup()
    else:
        text = ""
    text += "Current login user:\n当前登录用户：\n" f"`{tools.get_asn_mnt_text(db[message.chat.id])}`"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
