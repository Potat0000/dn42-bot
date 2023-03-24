# Yet Another Telegram DN42 Bot

## Features

- Tools
  - [x] Ping
  - [x] TCPing
  - [x] Traceroute
  - [x] Route
  - [x] Whois
- User Manage
  - [x] Login
  - [x] Logout
  - [x] Whoami
- Peer
  - [x] New peer
  - [x] Modify peer
  - [x] Remove peer
  - [x] Peer info
- Statistics
  - [x] DN42 global ranking
  - [x] DN42 user basic info & statistics
  - [x] Peer situation of a user
  - [x] Preferred routes ranking

## Deployment

The project is divided into two parts: server and agent, which can be deployed separately and have independent `requirements.txt`.

### Server

The server directory contains the code for the tg-bot server.

#### Config

Config items are located at `server/config.py`.

| Config Key          | Description                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------- |
| BOT_TOKEN           | Token of Telegram Bot                                                                    |
| BOT_USERNAME        | The Telegram username of this bot                                                        |
| CONTACT             | Contact information for yourself                                                         |
| DN42_ASN            | Your DN42 ASN                                                                            |
| WELCOME_TEXT        | The text shows at the top of /help command                                               |
| WHOIS_ADDRESS       | The address of whois server                                                              |
| ROA_PATH            | The path of ROA file. The first element is ROA4 and the second is ROA6.                  |
| DN42_ONLY           | Whether the tool commands (ping, traceroute, etc.) only allow DN42 networks.             |
| ENDPOINT            | Server name domain suffixes                                                              |
| API_PORT            | Agent API Port                                                                           |
| API_TOKEN           | Agent API Token                                                                          |
| SERVER              | A dict. The keys are the actual server names while the values are the display names.     |
| WEBHOOK_URL         | (Optional) Webhook URL to regist to Telegram. Disable webhook by set it to empty string. |
| WEBHOOK_LISTEN_HOST | (Required if webhook enabled) The listen host for webhook                                |
| WEBHOOK_LISTEN_PORT | (Required if webhook enabled) The listen port for webhook                                |
| LG_DOMAIN           | (Optional) URL of looking glass. Support bird-lg's URL format.                           |
| PRIVILEGE_CODE      | (Optional) Privilege code                                                                |
| SINGLE_PRIVILEGE    | (Optional) Whether to disable the privilege code when a privileged user already logs in. |
| SENTRY_DSN          | (Optional) Sentry DSN. Leave empty to disable Sentry exception tracking.                 |

#### Email-sending function

You should implement a `send_email(asn, mnt, code, email)` function in `config.py` and do the email sending in that function. If the send meets an error, a `RuntimeError` should be raised, otherwise, the send will be considered successful.

#### Privilege code

Privilege code login is provided for network operators.

When logging in, you can enter the Privilege Code when selecting email to log in as a privileged user.

Privileged users can use `/whoami <New AS>` to directly modify their identity, unlock additional settings in `/peer`, remove some restrictions, and receive notifications when others create or delete peers.

### Agent

The agent directory contains the code for the "agent" for tg-bot server.

#### Config

Config items are located at `agent/agent_config.json`.

| Config Key                 | Description                                                   |
| -------------------------- | ------------------------------------------------------------- |
| PORT                       | API Port                                                      |
| SECRET                     | API Token                                                     |
| OPEN                       | Whether open peer                                             |
| MAX_PEERS                  | Maximum number of Peer (0 for no limit)                       |
| NET_SUPPORT                | IP protocol stack supported by this agent.                    |
| EXTRA_MSG                  | Extra message of this agent.                                  |
| MY_DN42_LINK_LOCAL_ADDRESS | The DN42 IPv6 Link-Local Address of this agent.               |
| MY_DN42_ULA_ADDRESS        | The DN42 IPv6 ULA Address of this agent.                      |
| MY_DN42_IPv4_ADDRESS       | The DN42 IPv4 Address of this agent.                          |
| MY_WG_PUBLIC_KEY           | The WireGuard Public Key of this agent.                       |
| SENTRY_DSN                 | Sentry DSN. Leave empty to disable Sentry exception tracking. |

## Have a try

My bot is deployed at [@Potat0_DN42_Bot](https://t.me/Potat0_DN42_Bot). Welcome to peer with me!
