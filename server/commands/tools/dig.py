import shlex
import subprocess

import tools
from base import bot


@bot.message_handler(commands=['dig', 'nslookup'])
def dig(message):
    if len(message.text.split()) not in [2, 3]:
        bot.reply_to(
            message,
            'Usage: /dig [domain] {type}\n用法：/dig [domain] {type}',
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    dig_target = message.text.split()[1]
    dig_type = message.text.split()[2] if len(message.text.split()) == 3 else 'ANY'
    dig_type_whitelist = ['ANY', 'A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SOA', 'SRV', 'PTR']
    if dig_type not in dig_type_whitelist:
        bot.reply_to(
            message,
            'Only accept following types\n只接受以下类型的查询\n\n' + ', '.join(f'`{i}`' for i in dig_type_whitelist),
            parse_mode='Markdown',
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    dig_command = f'dig +noall +answer +comments +multiline {dig_target} {dig_type}'
    try:
        dig_result = (
            subprocess.run(
                shlex.split(dig_command),
                stdout=subprocess.PIPE,
                timeout=8,
            )
            .stdout.decode('utf-8')
            .strip()
        )
    except subprocess.TimeoutExpired:
        dig_result = 'Request timeout.\n请求超时。'
    except BaseException:
        dig_result = 'Something went wrong.\n发生了一些错误。'
    if not dig_result:
        dig_result = 'No result.\n没有结果。'
    if len(dig_result) > 4000:
        dig_result = tools.split_long_msg(dig_result)
        last_msg = message
        for index, m in enumerate(dig_result):
            if index < len(dig_result) - 1:
                last_msg = bot.reply_to(
                    last_msg,
                    f'```DigResult\n{m}```To be continued...',
                    parse_mode='Markdown',
                    reply_markup=tools.gen_peer_me_markup(message),
                )
            else:
                bot.reply_to(
                    last_msg,
                    f'```DigResult\n{m}```',
                    parse_mode='Markdown',
                    reply_markup=tools.gen_peer_me_markup(message),
                )
    else:
        bot.reply_to(
            message,
            f'```DigResult\n{dig_result}```',
            parse_mode='Markdown',
            reply_markup=tools.gen_peer_me_markup(message),
        )
