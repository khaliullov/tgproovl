Telegram bot for Proovl
=======================

Telegram bot for Proovl is a bot that receives and sends SMS via proovl.com
API. It uses two accounts: Telegram bot and human Telegram account.
Telegram Bot API is used for almost all functions, human account is only
required for chats creation, setting theirs descriptions, setting chats topics,
deleting chats after no new SMS in chat.

Workflow:

On each incoming SMS bot creates new chat named `<from> → <to>`. In this chat
operator could respond to this messages simply be sending text to the chat.
After defined timeout chat automatically destroyed.

Incoming SMS are received by webhooks configured in Proovl account for each
number (something like
[https://bot.example.com/tgproovl/incoming_sms](https://bot.example.com/tgproovl/incoming_sms)).

[proovl docs](https://www.proovl.com/ru/sms-api)


Table of Contents
-----------------

   * [App configuration](#app-configuration)
   * [Starting locally](#starting-locally)
   * [Proovl configuration](#proovl-configuration)
   * [Bot configuration](#bot-configuration)
   * [Deployment via Helm onto Kubernetes](#deployment-via-helm-onto-kubernetes)

App configuration
-----------------

There are a lot of different settings to configure bot logic and credentials
(see tgproovl/config.py for details).

- `TGPROOVL_URL_PATH_PREFIX` - URL path root for webhooks, default is `/`. Is a
path prefix for callbacks `incoming_sms` and Telegram updates.
- `TGPROOVL_URL_SCHEME` - bot URL scheme, by default is `https`, but it could
be `http` if TLS is not configured.
- `TGPROOVL_URL_HOST` - domain where bot is hosted.
- `TGPROOVL_TELEGRAM_TOKEN` - Telegram bot token, in format
`<digits>:<base64>`.
- `TGPROOVL_PERSISTENCE_PATH` - path for storing bot state (configured phone
numbers and quick replies on incoming SMS), by default is
`/mnt/tgproovl.state`.
- `TGPROOVL_TELEGRAM_WORKERS` - TDLib workers count, by defaul `4`.
- `TGPROOVL_BOT_PASSWORD` - bot password for becoming admin from casual
account. Invoke `/start` and private chat with bot and then type this password.
- `TGPROOVL_SECRET_KEY` - secret key for Flask.
- `TGPROOVL_PROOVL_USER` - user for Proovl API.
- `TGPROOVL_PROOVL_TOKEN` - token for Proovl API.
- `TGPROOVL_PROOVL_TARIFF` - default SMS tariff. By default is `2` (economy).
- `TGPROOVL_PROOVL_API_PREFIX` - Proovl API prefix. Default
`https://www.proovl.com/api/`.
- `TGPROOVL_TELEGRAM_DEVELOPER` - Telegram account ID for sending crash
reports.
- `TGPROOVL_TELEGRAM_OWNER` - Telegram account ID used for creating chats, etc.
This account also main Administrator and Operator. So it could configure quick
replyies and so on without authenticating. Also as soon as it manages chats it
also considered as Operator: this account will be present in all new chats for
processing incoming SMS.
- `TGPROOVL_TELEGRAM_PHONE` - Phone number of Telegram Owner, for
authenticating purposes. On first start bot will ask for code (and password)
via private messages to Owner. Owner should respond with `/setcode 54321` or
`/setpassword <Owner account password>`. Note: due Telegram limitations code
should sent in reversed order, for example if code is `01234` then reply
command should be `/setcode 43210`.
- `TGPROOVL_TELEGRAM_API_ID` - Telegram App api_id from
[https://my.telegram.org/](https://my.telegram.org/). 
- `TGPROOVL_TELEGRAM_API_HASH` - Telegram App api_hah also from the previously
mentioned site.
- `TGPROOVL_SMS_HALF_TIMEOUT` - Time for monitoring that SMS was delivered to
the recipient. By default is `900` seconds. When fired bot notificates operator
that SMS still not delivered. Ignored that recipient responds with second or
next SMS.
- `TGPROOVL_CHAT_HALF_TIMEOUT` - timeout for alerting operators about that chat
has outdated. By default `1800`. On the second time closes and deletes chat.
- `TGPROOVL_TDLIB_PATH` - TDLib JSON library path, on the prebuild image it is
located in `/usr/lib/libtdjson.so.1.5.1`
- `TGPROOVL_TDLIB_ENCRYPTION_KEY` - 20 characters long encryption key for TDLib
database.
- `TDLIB_FILES_DIRECTORY` - path for storing TDLib database and files.

Starting locally
----------------

It is possible to run bot locally on the laptop, using `Docker` and `Vagrant`.
To do so, create `.env` file (see `.env.dist` as example). Fill all fields.
Then:

    vagrant up
    vagrant ssh
    make run

this brings up `Flask` app and exposes 8080 port by default. You should
manually configure your router, nginx to receive requests from Internet.

Proovl configuration
--------------------

Each Proovl's number should be manually configured.
Open [Numbers](https://www.proovl.com/console/index.php?option=numbers) section 
and configure each number that you have: set `Forward all Inbound Messages to`
to `URL` and `Forward all Inbound Messages to the following` to
`<TGPROOVL_URL_SCHEME>://<TGPROOVL_URL_HOST><TGPROOVL_URL_PATH_PREFIX>/incoming_sms`.
Also, the same URL should be configured in
[API](https://www.proovl.com/console/index.php?option=api) section for 
`URL for delivery reports` field.

Bot configuration
-----------------

Each new number automatically added to bot's configuration on new SMS. But it
possible to add them manually, set `nick` for each number and quick replies.
Write `/start` private message to bot. Authenticate yourself if needed with
`<TGPROOVL_BOT_PASSWORD>`. After that you can see Proovl balance, add/remove
adminstators or/and operators and edit numbers. Each number could have `nick` -
virtual user with whom other end chats. Also each number could have `site` -
it could be social network account link. And also each number could have quick
replies, for example: `greeting` - `Hello, I am Diego, 23 y.o. SF, CA.`, etc.

Deployment via Helm onto Kubernetes
-----------------------------------

1. Build and publish Docker image into your k8s registry.
2. Create `values.yaml` with your configuration.

Example:

    image: "<you registry and path>/tgproovl"
    imagePullSecrets: "regred"
    urlPathPrefix: "/tgproovl/"
    urlHost: "<bot domain for webhooks and incoming SMS>"
    secretKey: "<Flask SECRET_KEY>"
    botPassword: "<very secret bot password to auth>"
    proovlUser: "<proovl API login>"
    proovlToken: "<proovl API token>"
    telegramToken: "<telegram bot token>"
    telegramDeveloper: "<telegram ID to send crash reports>"
    telegramOwner: "<main admin account for creating chats>"
    telegramApiId: <App api_id of telegram client>
    telegramApiHash: "<App api_hash of telegram client>"
    telegramPhone: "<main accounts phone for auth>"
    tdlibPath: "/usr/lib/libtdjson.so.1.5.1"
    tdlibEncryptionKey: "<20 chars encryption key>"
    tdlibFilesDirectory: "/mnt/.tdlib_files/<phone>/"

3. Install or upgrade you Helm Chart.

Run install:

    helm install ./k8s -n tgproovl -f values.yaml

or upgrade:

    helm upgrade tgproovl ./k8s -i -f values.yaml

4. Configure Ingress. 

The last thing is to manually configure your Ingress:

    apiVersion: extensions/v1beta1
    kind: Ingress
    metadata:
      name: docker-registry
      annotations:
        kubernetes.io/ingress.class: nginx
        nginx.ingress.kubernetes.io/worker-shutdown-timeout: "60"
        nginx.ingress.kubernetes.io/proxy-body-size: "0"
        certmanager.k8s.io/issuer: letsencrypt-prod
    spec:
      tls:
      - hosts:
        - bot.example.com
      rules:
        - host: bot.example.com
          http:
            paths:
            - backend:
                serviceName: tgproovl-svc
                servicePort: 8080
              path: /tgproovl

To apply run:

    kubectl apply -f ingress.yaml
