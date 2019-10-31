Telegram bot for proovl
=======================

[proovl docs](https://www.proovl.com/ru/sms-api)

## Deployment via Helm onto Kubernetes

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
    telegramApiId: <API ID of telegram client>
    telegramApiHash: "<API hash of telegram client>"
    telegramPhone: "<main accounts phone for auth>"
    tdlibPath: "/usr/lib/libtdjson.so.1.5.1"
    tdlibEncryptionKey: "<20 chars encryption key>"
    tdlibFilesDirectory: "/mnt/.tdlib_files/<phone>/"

3. Install or upgrade you Helm Chart.

Run install:

    helm install ./k8s -n tgproovl -f values.yaml

or upgrade:

    helm upgrade tgproovl ./k8s -i -f values.yaml