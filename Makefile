DEST := /opt/apps/tgproovl

-include .env

.PHONY: clean install run

all:

.env:
	@echo ".env file was not found, creating with defaults"
	cp .env.dist .env

venv/bin/python:
	virtualenv venv
	./venv/bin/pip install -r requirements.txt

run: venv/bin/python .env
	TGPROOVL_TELEGRAM_TOKEN=$(TGPROOVL_TELEGRAM_TOKEN) \
	TGPROOVL_URL_PATH_PREFIX=$(TGPROOVL_URL_PATH_PREFIX) \
	TGPROOVL_URL_HOST=$(TGPROOVL_URL_HOST) \
	TGPROOVL_CONFIG=$(TGPROOVL_CONFIG) \
	TGPROOVL_DEBUG=$(TGPROOVL_DEBUG) \
	TGPROOVL_PLUGIN_TESTERS=$(TGPROOVL_PLUGIN_TESTERS) \
	TGPROOVL_BOT_PASSWORD=$(TGPROOVL_BOT_PASSWORD) \
	TGPROOVL_PROOVL_USER=$(TGPROOVL_PROOVL_USER) \
	TGPROOVL_PROOVL_TOKEN=$(TGPROOVL_PROOVL_TOKEN) \
	TGPROOVL_TELEGRAM_CLI_HOST=$(TGPROOVL_TELEGRAM_CLI_HOST) \
	TGPROOVL_TELEGRAM_CLI_PORT=$(TGPROOVL_TELEGRAM_CLI_PORT) \
	TGPROOVL_TELEGRAM_PHONE=$(TGPROOVL_TELEGRAM_PHONE) \
	TGPROOVL_SMS_HALF_TIMEOUT=$(TGPROOVL_SMS_HALF_TIMEOUT) \
	TGPROOVL_CHAT_HALF_TIMEOUT=$(TGPROOVL_CHAT_HALF_TIMEOUT) \
	TGPROOVL_TELEGRAM_DEVELOPER=$(TGPROOVL_TELEGRAM_DEVELOPER) \
	TGPROOVL_TELEGRAM_OWNER=$(TGPROOVL_TELEGRAM_OWNER) \
	TGPROOVL_TELEGRAM_API_ID=$(TGPROOVL_TELEGRAM_API_ID) \
	TGPROOVL_TELEGRAM_API_HASH=$(TGPROOVL_TELEGRAM_API_HASH) \
		./venv/bin/python app.py

build-cli:
	docker build -t ubidots/telegram-cli -f ./telegram-cli/Dockerfile .

run-cli:
	docker run -d --rm -v /`pwd`/telegram-cli/:/home/telegramd/.telegram-cli/ \
	    -p 2391:2391 ubidots/telegram-cli telegram-cli --tcp-port 2391 --daemonize \
	    --disable-auto-accept --disable-readline --disable-output --disable-colors \
	    --accept-any-tcp --json -s /home/telegramd/.telegram-cli/init.lua

clean:
	rm -rf venv

install:
	virtualenv $(DEST)
	$(DEST)/bin/pip install -r requirements.txt
	$(DEST)/bin/python setup.py install
