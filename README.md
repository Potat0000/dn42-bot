# Yet Another Telegram DN42 Bot

The project is divided into two parts: server and proxy, which can be deployed separately and have independent `requirements.txt`.

## Server

The server directory contains the code for the tg-bot server.

### Config

Config items are located at `server/config.py`.

| Config Key          | Description                                                                          |
| ------------------- | ------------------------------------------------------------------------------------ |
| BOT_TOKEN           | Token of Telegram Bot                                                                |
| BOT_USERNAME        | The Telegram username of this bot                                                    |
| CONTACT             | Contact information for yourself                                                     |
| DN42_ASN            | Your DN42 ASN                                                                        |
| WELCOME_TEXT        | The text shows at the top of /help command                                           |
| ENDPOINT            | Server name domain suffixes                                                          |
| API_PORT            | Proxy API Port                                                                       |
| API_TOKEN           | Proxy API Token                                                                      |
| SERVER              | A dict. The keys are the actual server names while the valuse are the display names. |
| WEBHOOK_URL         | Webhook URL to regist to Telegram                                                    |
| WEBHOOK_LISTEN_HOST | The listen host for webhook                                                          |
| WEBHOOK_LISTEN_PORT | The listen port for webhook                                                          |
| LG_DOMAIN           | (Optional) URL of looking glass. Support bird-lg's URL format.                       |
| PRIVILEGE_CODE      | (Optional) Privilege code                                                            |

### Email-sending function

You should implement a `send_email(asn, mnt, code, email)` function in `config.py` and do the email sending in that function. If the send meets an error, a `RuntimeError` should be raised, otherwise the send will be considered successful.

### Privilege code

Privilege code login is provided for administrator's convenience.

Privilege users can use `/whoami <New AS>` to directly modify their identity, unlock additional settings in `/peer`, remove some restrictions, and receive notifications when others create or delete peers.

## Proxy

The proxy directory contains the code for the "proxy" for tg-bot server.

### Config

Config items are located at `proxy/proxy_config.json`.

| Config Key                 | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| PORT                       | API Port                                             |
| SECRET                     | API Token                                            |
| MY_DN42_LINK_LOCAL_ADDRESS | The DN42 IPv6 Link-Local Address of this proxy node. |
| MY_DN42_ULA_ADDRESS        | The DN42 IPv6 ULA Address of this proxy node.        |
| MY_DN42_IPv4_ADDRESS       | The DN42 IPv4 Address of this proxy node.            |
| MY_WG_PUBLIC_KEY           | The WireGuard Public Key of this proxy node.         |
