from base import bot
from commands.help import send_welcome
from commands.peer.info import get_info
from commands.peer.peer import start_peer
from commands.user_manage.login import start_login
from commands.user_manage.whoami import whoami


@bot.message_handler(commands=['start'], is_private_chat=True)
def startup(message):
    try:
        command = message.text.split()[1]
        if command.startswith('whoami_'):
            whoami(message, *command[7:].split('_'))
        elif command == 'info':
            get_info(message)
        elif command.startswith('info_'):
            _, asn, node = command.split('_', 3)
            get_info(message, int(asn), node)
        elif command == 'login':
            start_login(message)
        elif command == 'peer':
            start_peer(message)
    except BaseException:
        send_welcome(message)
