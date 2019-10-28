# -*- coding: utf-8 -*-

import copy
import logging
import os
from queue import Queue
import sys
import time
import traceback
import threading

from flask import Flask, request
from flask_apscheduler import APScheduler
from googletrans import Translator
import requests
import telegram
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler,\
    MessageHandler, Filters, CallbackQueryHandler

from tgproovl.extendedpersistence import ExtendedPersistence
from tgproovl.tgclient import TgClient
from tgproovl.tgproovlworker import TgproovlWorker


APP_CONFIG = os.environ.get('TGBOT_CONFIG', 'config.MainConfig')
PASSWORD, CONFIG, USERS, NEW_USER, SMS, PHONES_MENU, NEW_PHONE, PHONE_EDIT,\
    NEW_REPLY, SET_PHONE_PROPERTY = range(10)
SMS_STATUS_RU = {
    'Sent': 'Отправлено',
    'Fail': 'Ошибка',
    'Delivered': 'Доставлено',
    'Undelivered': 'Не доставлено',
}


app = Flask(__name__)
scheduler = APScheduler()
app.config.from_object(APP_CONFIG)
app.bot = telegram.Bot(app.config['TELEGRAM_TOKEN'])
app.translator = Translator()
app.bot_persistence = ExtendedPersistence(filename=app.config['PERSISTENCE_PATH'])
app.dispatcher = Dispatcher(bot=app.bot, update_queue=None,
                            workers=app.config['TELEGRAM_WORKERS'],
                            persistence=app.bot_persistence, use_context=True)
app.bot.setWebhook(url='https://%s%s%s' % (app.config['SERVER_NAME'],
                                           app.config['APPLICATION_ROOT'],
                                           app.config['TELEGRAM_TOKEN']))
app.human = TgClient(app.config['TELEGRAM_API_ID'],
                     app.config['TELEGRAM_API_HASH'],
                     use_message_database=False, tdlib_verbosity=2,
                     phone=app.config['TELEGRAM_PHONE'],
                     database_encryption_key='abret' + app.config['TELEGRAM_PHONE'] + 'bgty',
                     system_version='Linux',
                     library_path='/tmp/td/tdlib/lib/libtdjson.so.1.5.0')
lock = threading.Lock()
logger = logging.getLogger(__name__)
app.queue = Queue(maxsize=1000)
app.worker = TgproovlWorker(app.queue)


@app.route(app.config['APPLICATION_ROOT'] + 'healthcheck')
def smoke_test():
    return 'OK'


def remove_chat(update):
    chat_id = update['chat_id']
    receiver = update['receiver']
    sender = update['sender']
    result = app.human._send_data({'@type': 'searchChatMembers',
                                   'limit': 100,
                                   'chat_id': chat_id})
    try:
        result.wait(timeout=5)
    except TimeoutError:
        pass
    if result.update and result.update.ID == 'chatMembers':
        users = set()
        for member in result.update.members:
            users.add(member.user_id)
        if app.bot_persistence.state['self'] in users:
            users.discard(app.bot_persistence.state['self'])
            users.add(app.bot_persistence.state['self'])
        error = False
        for user_id in users:
            result = app.human._send_data({
                '@type': 'setChatMemberStatus',
                'user_id': user_id,
                'chat_id': chat_id,
                'status': {'@type': 'chatMemberStatusLeft'}})
            try:
                result.wait(timeout=5)
            except TimeoutError:
                pass
            if not result.update:
                error = True
                break
        if not error:
            result = app.human._send_data({
                '@type': 'deleteChatHistory',
                'chat_id': chat_id,
                'remove_from_chat_list': 1})
            try:
                result.wait(timeout=5)
            except TimeoutError:
                pass
            if result.update:
                with lock:
                    app.bot_persistence.state['phones'][receiver]['chats'].pop(sender, None)
                app.bot_persistence.save_state()
            return True
    else:
        if result.error == True and result.error_info['message'] == 'Chat not found':
            with lock:
                app.bot_persistence.state['phones'][receiver]['chats'].pop(sender, None)
            app.bot_persistence.save_state()
            return True
    return False


def send_bot_message(update):
    logger.debug('Update send_bot_messaage: %s', update)
    message = update.get('message', None)
    chat_id = update.get('chat_id', None)
    text = update['text']
    reply_markup = update.get('reply_markup', telegram.ReplyKeyboardRemove())
    reply_to_message_id = update.get('reply_to_message_id', None)
    parse_mode = update.get('parse_mode', None)
    try:
        if message:
            message.reply_text(text, reply_markup=reply_markup,
                               parse_mode=parse_mode)
        else:
            app.bot.send_message(chat_id=chat_id, reply_markup=reply_markup,
                                 parse_mode=parse_mode, text=text,
                                 reply_to_message_id=reply_to_message_id)
    except telegram.error.Unauthorized:
        pass
    except Exception:
        if chat_id != app.config['TELEGRAM_DEVELOPER']:
            app.queue.put((send_bot_message, {
                'chat_id': app.config['TELEGRAM_DEVELOPER'],
                'text': "Ошибка отправки сообщения на канал {0}\n{1}".format(chat_id, text),
                'parse_mode': telegram.ParseMode.MARKDOWN
            }), timeout=10)
    return True


@scheduler.task('interval', id='get_sms', seconds=10, coalesce=False)
def check_sms_and_chats():
    now = int(time.time())
    if not app.bot_persistence.state \
            or 'phones' not in app.bot_persistence.state \
            or 'sms' not in app.bot_persistence.state:
        logger.warn('skipping SMS and Chats check')
        return
    logger.info('Running SMS and Chats check')
    for receiver in app.bot_persistence.state['phones']:
        for sender in app.bot_persistence.state['phones'][receiver]['chats']:
            chat = app.bot_persistence.state['phones'][receiver]['chats'][sender]
            if chat['last_message'] + app.config['CHAT_HALF_TIMEOUT'] < now:
                if 'try' not in chat:
                    with lock:
                        chat['try'] = 1
                    app.queue.put((send_bot_message, {
                        'chat_id': chat['chat_id'],
                        'text': 'В чате давно не было новых сообщений. Жду ещё {0} секунд и закрываю'.format(app.config['CHAT_HALF_TIMEOUT']),
                        'parse_mode': telegram.ParseMode.MARKDOWN
                    }), timeout=10)
                    continue
            if chat['last_message'] + app.config['CHAT_HALF_TIMEOUT'] * 2 < now:
                app.queue.put((remove_chat, {
                    'chat_id': chat['chat_id'],
                    'receiver': receiver,
                    'sender': sender,
                }), timeout=10)
    to_remove = []
    for _id in app.bot_persistence.state['sms']:
        sms = app.bot_persistence.state['sms'][_id]
        if sms['timestamp'] + app.config['SMS_HALF_TIMEOUT'] < now:
            if 'try' not in sms:
                with lock:
                    sms['try'] = 1
                if ('incoming' not in app.bot_persistence.state['phones'][sms['from']]['chats'][sms['to']]
                    or app.bot_persistence.state['phones'][sms['from']]['chats'][sms['to']]['incoming'] < 2) \
                        and sms['status'] != 'Delivered':
                    if sms['to'] in app.bot_persistence.state['phones'][sms['from']]['chats']:
                        app.queue.put((send_bot_message, {
                            'chat_id': app.bot_persistence.state['sms'][_id]['chat_id'],
                            'reply_to_message_id': sms['reply_to_message_id'],
                            'text': 'Сообщение до сих пор со статусом *{0}*'.format(SMS_STATUS_RU.get(sms['status'], sms['status'])),
                            'parse_mode': telegram.ParseMode.MARKDOWN
                        }), timeout=10)
        if sms['timestamp'] + app.config['SMS_HALF_TIMEOUT'] * 2 < now:
            to_remove.append(_id)
    for item in to_remove:
        with lock:
            app.bot_persistence.state['sms'].pop(item, None)
    app.bot_persistence.save_state()
    logger.debug('state: %s', app.bot_persistence.state)
    logger.info('SMS and Chats check ended')


def init_receiver(phone):
    if phone not in app.bot_persistence.state['phones']:
        with lock:
            app.bot_persistence.state['phones'][phone] = {
                'nick': phone,
                'site': '',
                'regulars': {},
                'replies': {},
                'chats': {},
            }
        app.bot_persistence.save_state()


def send_sms(_from, to, text, tariff=app.config['PROOVL_TARIFF']):
    r = requests.post('https://tv.localix.ru/tgproovl/send.php',  # 'https://www.proovl.com/api/balance.php',
                      params={'user': app.config['PROOVL_USER'],
                              'token': app.config['PROOVL_TOKEN'],
                              'route': tariff,
                              'from': _from,
                              'to': to,
                              'text': text})
    if 200 <= r.status_code <= 299:
        x = r.text.split(";")
        message_id = x[1].replace('"', '')
        status = x[0].replace('"', '')
    else:
        status = 'Error'
        message_id = r.reason
    return status, message_id


def esc_yml(text):
    return str(text).translate({
        ord('_'): '＿',
        ord('*'): '⁎',
        ord('['): '\\[',
        ord(']'): '\\]',
        ord('('): '\\(',
        ord(')'): '\\)',
        ord('`'): '\\`',
    })


def process_status(update):
    token = update.get('token', None)
    _from = update.get('from', None)
    _id = update.get('id', None)
    to = update.get('to', None)
    text = update.get('text', None)
    status = update.get('status', None)
    if _id in app.bot_persistence.state['sms'] \
            and app.bot_persistence.state['sms'][_id]['to'] in \
            app.bot_persistence.state['phones'][
                app.bot_persistence.state['sms'][_id]['from']]['chats']:
        app.bot.edit_message_text(
            chat_id=app.bot_persistence.state['sms'][_id]['chat_id'],
            message_id=app.bot_persistence.state['sms'][_id]['message_id'],
            text='Сообщение *{0}* доставлено со статусом *{1}*'.format(
                esc_yml(_id),
                esc_yml(SMS_STATUS_RU.get(status, status))),
            parse_mode=telegram.ParseMode.MARKDOWN
        )
        with lock:
            app.bot_persistence.state['sms'][_id]['status'] = status
            app.bot_persistence.state['sms'][_id]['timestamp'] = int(time.time())
        if status != 'Delivered' and app.bot_persistence.state['sms'][_id]['tariff'] == 2:
            sms = copy.copy(app.bot_persistence.state['sms'][_id])
            res = app.bot.send_message(
                chat_id=app.bot_persistence.state['sms'][_id]['chat_id'],
                text="Отравка сообщения \"*{0}*\""
                     " провалилась со статусом *{1}*.\n"
                     "Пробую отправить с более дорогим тарифом".format(esc_yml(sms['text']), esc_yml(SMS_STATUS_RU.get(status, status))),
                parse_mode=telegram.ParseMode.MARKDOWN)
            with lock:
                app.bot_persistence.state['sms'].pop(_id, None)
                sms['tariff'] = 1
                app.bot_persistence.state['phones'][sms['from']]['chats'][sms['to']]['tariff'] = 1
            status, message_id = send_sms(sms['from'], sms['to'], sms['text'], 1)
            res = app.bot.send_message(chat_id=sms['chat_id'],
                                       reply_to_message_id=res.message_id,
                                       text='Сообщение *{0}* отправлено со статусом *{1}*'.
                                       format(esc_yml(message_id), esc_yml(SMS_STATUS_RU.get(status, status))),
                                       parse_mode=telegram.ParseMode.MARKDOWN)
            with lock:
                sms['message_id'] = res.message_id
                sms['remote_id'] = message_id
                sms['status'] = status
                app.bot_persistence.state['sms'][message_id] = sms
        app.bot_persistence.save_state()
    else:
        print('Unknown message ID {0} updated with state {1}'.format(_id, status))
    return True


def sms_reply_keyboard(receiver):
    keyboard = []
    buttons = []
    for reply in app.bot_persistence.state['phones'][receiver]['replies']:
        buttons.append(telegram.InlineKeyboardButton(reply,
                                                     callback_data=reply))
        if len(buttons) >= 2:
            keyboard.append(buttons)
            buttons = []
    if len(buttons) > 0:
        keyboard.append(buttons)
    return telegram.InlineKeyboardMarkup(keyboard)


def process_incoming_sms(update):
    token = update.get('token', None)
    _from = update.get('from', None)
    _id = update.get('id', None)
    to = update.get('to', None)
    text = update.get('text', None)
    status = update.get('status', None)
    init_state()
    init_receiver(to)
    translation = app.translator.translate(text, dest='ru')
    if translation.text != text:
        text = "_{0}_\nПеревод (c *{1}* на ru): *{2}*".format(esc_yml(text), esc_yml(translation.src), esc_yml(translation.text))
    else:
        text = '*{0}*'.format(esc_yml(text))
    if _from not in app.bot_persistence.state['phones'][to]['chats']:
        users = set([app.bot_persistence.state['bot_id']])
        nicks = set([app.bot_persistence.state['bot_username']])
        for user_id in app.bot_persistence.state['operators'].keys():
            nicks.add(app.bot_persistence.state['operators'][user_id]['username'])
            users.add(user_id)
        users.discard(app.bot_persistence.state['self'])
        user_ids = [app.bot_persistence.state['self']]
        user_ids.extend(users)
        for nick in nicks:
            result = app.human._send_data({'@type': 'searchPublicChat',
                                           'username': '@{0}'.format(nick)})
            try:
                result.wait(timeout=5)
            except TimeoutError:
                pass
        for user in user_ids:
            result = app.human._send_data({'@type': 'getUser',
                                           'user_id': user})
            try:
                result.wait(timeout=5)
            except TimeoutError:
                pass
        title = '{0} → {1}'.format(_from, to)
        result = app.human._send_data({'@type': 'createNewBasicGroupChat',
                                       'title': title,
                                       'user_ids': user_ids})
        try:
            result.wait(timeout=5)
        except TimeoutError:
            pass
        if result.update and result.update['@type'] == 'chat':
            with lock:
                app.bot_persistence.state['phones'][to]['chats'][_from] = {
                    'last_message': int(time.time()),
                    'tariff': app.config['PROOVL_TARIFF'],
                    'incoming': 1,
                    'message': text,
                }
                app.bot_persistence.state['phones'][to]['chats'][_from]['chat_id'] = result.update['id']
            app.bot_persistence.save_state()
            app.human._send_data({'@type': 'setChatDescription',
                                  'chat_id': result.update['id'],
                                  'description': title})
        else:
            app.queue.put((send_bot_message, {
                'chat_id': app.config['TELEGRAM_DEVELOPER'],
                'text': "Ошибка создания канала!\nСообщение от *{0}* для *{1}*\n{2}".format(esc_yml(_from), esc_yml(to), text),
                'parse_mode': telegram.ParseMode.MARKDOWN
            }), timeout=10)
    else:
        with lock:
            app.bot_persistence.state['phones'][to]['chats'][_from]['last_message'] = int(time.time())
            app.bot_persistence.state['phones'][to]['chats'][_from].pop('try', None)
            if 'incoming' in app.bot_persistence.state['phones'][to]['chats'][_from]:
                app.bot_persistence.state['phones'][to]['chats'][_from]['incoming'] += 1
            else:
                app.bot_persistence.state['phones'][to]['chats'][_from]['incoming'] = 1
        app.bot_persistence.save_state()
        app.queue.put((send_bot_message, {
            'chat_id': app.bot_persistence.state['phones'][to]['chats'][_from]['chat_id'],
            'text': text,
            'reply_markup': sms_reply_keyboard(to),
            'parse_mode': telegram.ParseMode.MARKDOWN
        }), timeout=10)
    return True


@app.route(app.config['APPLICATION_ROOT'] + 'incoming_sms', methods=['POST'])
def proovl_webhook():
    token = request.values.get('token')
    _from = request.values.get('from')
    _id = request.values.get('id')
    to = request.values.get('to')
    text = request.values.get('text')
    status = request.values.get('status')
    logger.debug('From: %s, to: %s, msg_id: %s, status: %s, text: %s', _from, _id, to, text, status)
    payload = {
        'token': token,
        'from': _from,
        'to': to,
        'text': text,
        'status': status,
        'id': _id,
    }
    if status:
        app.queue.put((process_status, payload), timeout=10)
    else:
        app.queue.put((process_incoming_sms, payload), timeout=10)
    return 'OK'


@app.route(app.config['APPLICATION_ROOT'] + app.config['TELEGRAM_TOKEN'],
           methods=['POST'])
def telegram_webhook():
    payload = request.get_json(force=True)
    logger.debug('Webhook payload: %s', payload)
    update = telegram.update.Update.de_json(payload, app.bot)
    app.dispatcher.process_update(update)
    return 'OK'


def save_state(context, new_state):
    context.chat_data['state'] = new_state
    return new_state


def menu_keyboard(context):
    back = telegram.InlineKeyboardButton('🔙 Назад', callback_data='Назад')
    if 'state' not in context.chat_data or \
            context.chat_data['state'] in [CONFIG, PASSWORD]:
        back = telegram.InlineKeyboardButton('🚪 Выход', callback_data='Выход')
    return telegram.InlineKeyboardMarkup([
        [telegram.InlineKeyboardButton('💰 Баланс', callback_data='Баланс'),
         telegram.InlineKeyboardButton('📞 Номера телефонов',
                                       callback_data='Номера телефонов')],
        [telegram.InlineKeyboardButton('Администраторы',
                                       callback_data='Администраторы'),
         telegram.InlineKeyboardButton('Операторы',
                                       callback_data='Операторы')],
        [back]])


def init_state():
    if not app.bot_persistence.state:
        me = app.bot.get_me()
        owner = app.bot.get_chat(app.config['TELEGRAM_OWNER'])
        app.human._send_data({'@type': 'getUser', 'user_id': me.id})
        root = {
            'id': owner.id,
            'name': owner.first_name,
            'username': owner.username
        }
        state = {
            'phones': {},
            'sms': {},
            'admins': {
                owner.id: root,
            },
            'operators': {
                owner.id: root,
            },
            'self': owner.id,
            'bot_id': me.id,
            'bot_username': me.username,
        }
        app.bot_persistence.update_state(state)


def start(update, context):
    init_state()
    user = update.message.from_user
    if user.id in app.bot_persistence.state['admins']:
        app.queue.put((send_bot_message, {
            'message': update.message,
            'text': '{0}, снова привет!'.format(user.first_name),
            'reply_markup': menu_keyboard(context)
        }), timeout=10)
        return save_state(context, CONFIG)
    app.queue.put((send_bot_message, {
        'message': update.message,
        'text': 'Впервые вижу'
    }), timeout=10)
    return save_state(context, PASSWORD)


def handle_password(update, context):
    if update.message.text == app.config['BOT_PASSWORD']:
        app.bot.deleteMessage(chat_id=update.message.chat.id,
                              message_id=update.message.message_id)
        user = update.message.from_user
        with lock:
            app.bot_persistence.state['admins'][user.id] = {
                'id': user.id,
                'name': user.first_name,
                'username': user.username
            }
        app.bot_persistence.save_state()
        app.queue.put((send_bot_message, {
            'message': update.message,
            'text': 'Привет, {0}'.format(user.first_name),
            'reply_markup': menu_keyboard(context)
        }), timeout=10)
        return save_state(context, CONFIG)
    else:
        app.queue.put((send_bot_message, {
            'message': update.message,
            'text': 'Пока!'
        }), timeout=10)
    return ConversationHandler.END


def handle_cancel_query(update, context):
    if update.message:
        message = update.message
    else:
        message = update.callback_query.message
    app.queue.put((send_bot_message, {
        'message': message,
        'text': 'Береги себя!',
    }), timeout=10)
    return ConversationHandler.END


def handle_balance(update, context):
    r = requests.get('https://www.proovl.com/api/balance.php',
                     params={'user': app.config['PROOVL_USER'],
                             'token': app.config['PROOVL_TOKEN']})
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': 'Баланс: {0}'.format(r.text),
        'reply_markup': menu_keyboard(context)
    }), timeout=10)
    return save_state(context, CONFIG)


def handle_back(update, context):
    if context.chat_data['state'] == CONFIG:
        return handle_cancel_query(update, context)
    if context.chat_data['state'] == USERS:
        save_state(context, CONFIG)
        app.queue.put((send_bot_message, {
            'message': update.callback_query.message,
            'text': 'Основное меню',
            'reply_markup': menu_keyboard(context)
        }), timeout=10)
        return CONFIG
    return handle_cancel_query(update, context)


def add_phone_keyboard():
    button_list = [
        [telegram.InlineKeyboardButton('➕ Добавить номер', callback_data='Добавить номер')],
    ]
    for phone in app.bot_persistence.state['phones']:
        button_list.append([telegram.InlineKeyboardButton('📝 {0}'.format(phone),
                                                          callback_data='Изменить {0}'.format(phone)),
                            telegram.InlineKeyboardButton('❌ {0}'.format(phone),
                                                          callback_data='Удалить {0}'.format(phone))])
    button_list.append([telegram.InlineKeyboardButton('🔙 Назад',
                                                      callback_data='Назад'),
                        telegram.InlineKeyboardButton('🚪 Выход',
                                                      callback_data='Выход')])
    return telegram.InlineKeyboardMarkup(button_list)


def handle_back_query(update, context):
    if context.chat_data['state'] == PHONES_MENU:
        save_state(context, CONFIG)
        app.queue.put((send_bot_message, {
            'message': update.callback_query.message,
            'text': 'Основное меню',
            'reply_markup': menu_keyboard(context)
        }), timeout=10)
        return CONFIG
    elif context.chat_data['state'] == PHONE_EDIT:
        app.queue.put((send_bot_message, {
            'message': update.callback_query.message,
            'text': 'Редактирование номеров телефонов',
            'reply_markup': add_phone_keyboard()
        }), timeout=10)
        return save_state(context, PHONES_MENU)
    return handle_cancel_query(update, context)


def user_keyboard(context):
    if context.chat_data['user_type'] == 'Администраторы':
        add_user_menu = 'Добавить администратора'
        state_field = 'admins'
    else:
        add_user_menu = 'Добавить оператора'
        state_field = 'operators'
    menu = [[telegram.InlineKeyboardButton('➕ ' + add_user_menu,
                                           callback_data=add_user_menu)]]
    for user in app.bot_persistence.state[state_field]:
        button = 'Удалить ' + \
                 app.bot_persistence.state[state_field][user]['name']
        menu.append([telegram.InlineKeyboardButton('❌ ' + button,
                                           callback_data=button)])
    menu.append([telegram.InlineKeyboardButton('🔙 Назад',
                                               callback_data='Назад'),
                 telegram.InlineKeyboardButton('🚪 Выход',
                                               callback_data='Выход')])
    return telegram.InlineKeyboardMarkup(menu)


def handle_users(update, context):
    context.chat_data['user_type'] = update.callback_query.data
    if context.chat_data['user_type'] == 'Администраторы':
        reply = 'Управление администраторами'
    else:
        reply = 'Управление операторами'
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': reply,
        'reply_markup': user_keyboard(context)
    }), timeout=10)
    return save_state(context, USERS)


def handle_add_user(update, context):
    if context.chat_data['user_type'] == 'Администраторы':
        reply = 'Введите ник нового администратора, например: @shishkova'
    else:
        reply = 'Введите ник нового оператора, например: @timati'
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': reply
    }), timeout=10)
    return save_state(context, NEW_USER)


def handle_set_user(update, context):
    if context.chat_data['user_type'] == 'Администраторы':
        user_type = 'администратор'
        state_field = 'admins'
    else:
        user_type = 'оператор'
        state_field = 'operators'
    nick = update.message.text
    result = app.human._send_data({'@type': 'searchPublicChat',
                                   'username': nick})
    try:
        result.wait(timeout=5)
    except TimeoutError:
        pass
    if not result.update or result.update['@type'] != 'chat':
        result = 'Пользователь с ником {0} не найден'.format(nick)
    else:
        user = {
            'id': result.update['id'],
            'name': result.update['title'],
            'username': nick.lstrip('@'),
        }
        app.human._send_data({'@type': 'getUser', 'user_id': user['id']})
        if user['id'] in app.bot_persistence.state[state_field]:
            result = 'Пользователь с ником {0} уже {1}'.format(nick, user_type)
        else:
            result = 'Пользователь с ником {0} теперь {1}!'.format(nick, user_type)
            with lock:
                app.bot_persistence.state[state_field][user['id']] = user
            app.bot_persistence.save_state()
    app.queue.put((send_bot_message, {
        'message': update.message,
        'text': result,
        'reply_markup': user_keyboard(context)
    }), timeout=10)
    return save_state(context, USERS)


def find_user_by_field(group, field, value):
    for user_id in app.bot_persistence.state[group]:
        if app.bot_persistence.state[group][user_id][field] == value:
            return user_id
    return None


def handle_del_user(update, context):
    if context.chat_data['user_type'] == 'Администраторы':
        user_type = 'администратор'
        state_field = 'admins'
    else:
        user_type = 'оператор'
        state_field = 'operators'
    nick = context.matches[0].group(1)
    user_id = find_user_by_field(state_field, 'name', nick)
    if app.bot_persistence.state['self'] == user_id:
        result = 'Нельзя удалить основного {0}а'.format(user_type)
    else:
        with lock:
            app.bot_persistence.state[state_field].pop(user_id, None)
        app.bot_persistence.save_state()
        result = '{0} больше не {1}!'.format(nick, user_type)
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': result,
        'reply_markup': user_keyboard(context)
    }), timeout=10)
    return save_state(context, USERS)


def handle_phones(update, context):
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': 'Редактирование номеров телефонов',
        'reply_markup': add_phone_keyboard()
    }), timeout=10)
    return save_state(context, PHONES_MENU)


def handle_chat_start(update, context):
    init_state()
    context.chat_data['chat_id'] = update.message.chat.id
    chat = app.bot.get_chat(context.chat_data['chat_id'])
    title = chat.description or update.message.chat.title
    if not chat.description:
        app.human._send_data({'@type': 'setChatDescription',
                              'chat_id': context.chat_data['chat_id'],
                              'description': title})
    context.chat_data['sender'] = title.split(' ')[0]
    context.chat_data['receiver'] = title.split(' ')[-1]
    init_receiver(context.chat_data['receiver'])
    with lock:
        if context.chat_data['sender'] in app.bot_persistence.state['phones'][context.chat_data['receiver']]['regulars']:
            app.bot_persistence.state['phones'][context.chat_data['receiver']]['regulars'][context.chat_data['sender']] += 1
        else:
            app.bot_persistence.state['phones'][context.chat_data['receiver']]['regulars'][context.chat_data['sender']] = 1
        if context.chat_data['sender'] not in app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats']:
            app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']] = {}
        app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']].update({
            'chat_id': context.chat_data['chat_id'],
            'sender': context.chat_data['sender'],
            'receiver': context.chat_data['receiver'],
            'last_message': int(time.time()),
            'tariff': app.config['PROOVL_TARIFF'],
        })
    app.bot_persistence.save_state()
    text = 'Абоненту: *{0}*'.format(esc_yml(context.chat_data['receiver']))
    if app.bot_persistence.state['phones'][context.chat_data['receiver']]['nick'] != context.chat_data['receiver']:
        app.human._send_data({'@type': 'setChatTitle',
                              'chat_id': context.chat_data['chat_id'],
                              'title': '{0} → {1}'.format(context.chat_data['sender'],
                                                          app.bot_persistence.state['phones'][context.chat_data['receiver']]['nick'])})
        text = "На номер: *{0}*\nАбоненту: *{1}*".format(esc_yml(context.chat_data['receiver']),
                                                         esc_yml(app.bot_persistence.state['phones'][context.chat_data['receiver']]['nick']))
    if app.bot_persistence.state['phones'][context.chat_data['receiver']]['site']:
        text += "\nСайт: *{0}*".format(app.bot_persistence.state['phones'][context.chat_data['receiver']]['site'])
    app.queue.put((send_bot_message, {
        'chat_id': context.chat_data['chat_id'],
        'text': text,
        'parse_mode': telegram.ParseMode.MARKDOWN
    }), timeout=10)
    text = "Пишет: *{0}* (уже *{1}-й* раз)".format(esc_yml(context.chat_data['sender']),
                                                 esc_yml(app.bot_persistence.state['phones'][context.chat_data['receiver']]['regulars'][context.chat_data['sender']]))
    if len(app.bot_persistence.state['phones'][context.chat_data['receiver']]['replies']):
        text += "\nБыстрые ответы:"
        for reply in app.bot_persistence.state['phones'][context.chat_data['receiver']]['replies']:
            if app.bot_persistence.state['phones'][context.chat_data['receiver']]['replies'][reply]:
                text += "\n*{0}*: {1}".format(esc_yml(reply),
                                              esc_yml(app.bot_persistence.state['phones'][context.chat_data['receiver']]['replies'][reply]))
    app.queue.put((send_bot_message, {
        'chat_id': context.chat_data['chat_id'],
        'text': text,
        'parse_mode': telegram.ParseMode.MARKDOWN
    }), timeout=10)
    if 'message' in app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']]:
        app.queue.put((send_bot_message, {
            'chat_id': context.chat_data['chat_id'],
            'text': app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']]['message'],
            'parse_mode': telegram.ParseMode.MARKDOWN,
            'reply_markup': sms_reply_keyboard(context.chat_data['receiver']),
        }), timeout=10)
        with lock:
            app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']].pop('message', None)
        app.bot_persistence.save_state()
    return save_state(context, SMS)


def handle_chat_stop(update, context):
    #app.bot_persistence.state['phones'][context.chat_data[
    #    'receiver']]['chats'].pop(context.chat_data['sender'], None)
    #app.bot_persistence.update_state(app.bot_persistence.state)
    return ConversationHandler.END


@app.route(app.config['APPLICATION_ROOT'] + 'send.php', methods=['POST'])
def fake_send_sms():
    token = request.values.get('token')
    from_ = request.values.get('from')
    id_ = request.values.get('id')
    to = request.values.get('to')
    text = request.values.get('text')
    status = request.values.get('status')
    #return 'Sent;' + text
    return 'Sent;1'
    return 'Error;Проверка ошибки'


def real_handle_sms(message, context):
    tariff = app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']]['tariff']
    sms = {
        'reply_to_message': message.message_id,
        'text': message.text,
        'from': context.chat_data['receiver'],
        'to': context.chat_data['sender'],
        'chat_id': context.chat_data['chat_id'],
        'tariff': tariff,
        'timestamp': int(time.time()),
    }
    with lock:
        app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']]['last_message'] = int(time.time())
        app.bot_persistence.state['phones'][context.chat_data['receiver']]['chats'][context.chat_data['sender']].pop('try', None)
    status, message_id = send_sms(context.chat_data['receiver'],
                                  context.chat_data['sender'],
                                  message.text, tariff)
    if status == 'Error':
        app.queue.put((send_bot_message, {
            'message': message,
            'text': 'Ошибка при отправке сообщения: {0}'.format(message_id)
        }), timeout=10)
    else:
        res = message.reply_text('Сообщение *{0}* отправлено со статусом *{1}*'.format(message_id, SMS_STATUS_RU.get(status, status)),
                                 parse_mode=telegram.ParseMode.MARKDOWN)
        sms['remote_id'] = message_id
        sms['status'] = status
        sms['message_id'] = res.message_id
        sms['reply_to_message_id'] = message.message_id
        with lock:
            app.bot_persistence.state['sms'][message_id] = sms
    app.bot_persistence.save_state()
    return SMS


def handle_send_translate_query(update, context):
    command = context.matches[0].group(1)
    if command == 'Отправить':
        text = update.callback_query.message.text
    elif command in app.bot_persistence.state['phones'][context.chat_data['receiver']]['replies']:
        text = app.bot_persistence.state['phones'][context.chat_data['receiver']]['replies'][command]
    else:
        app.queue.put((send_bot_message, {
            'message': 'Неизвестная команда',
            'text': 'Введи новый номер телефона (например, 33666555777):'
        }), timeout=10)
        return SMS
    app.human._send_data({'@type': 'sendMessage',
                          'chat_id': context.chat_data['chat_id'],
                          'input_message_content': {
                              '@type': 'inputMessageText',
                              'text': {
                                  '@type': 'formattedText',
                                  'text': text
                              }
                          }})
    return SMS


def handle_add_phone_query(update, context):
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': 'Введи новый номер телефона (например, 33666555777):'
    }), timeout=10)
    return save_state(context, NEW_PHONE)


def handle_del_phone_query(update, context):
    phone = context.matches[0].group(1)
    # TODO: exit from all chats!!!
    app.bot_persistence.state['phones'].pop(phone, None)
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': 'Редактирование номеров телефонов',
        'reply_markup': add_phone_keyboard()
    }), timeout=10)
    return save_state(context, PHONES_MENU)


def handle_add_quick_reply_name_query(update, context):
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': 'Ввведи название быстрого ответа (например, 🗺 address, 💶 price, 🔑 intercom):'
    }), timeout=10)
    return save_state(context, NEW_REPLY)


def handle_add_quick_reply(update, context):
    text = update.message.text
    phone = context.chat_data['phone']
    if text in app.bot_persistence.state['phones'][phone].keys():
        app.queue.put((send_bot_message, {
            'message': update.message,
            'text': 'Это слово зарезервировано, попробуй другое'
        }), timeout=10)
        return save_state(context, NEW_REPLY)
    context.chat_data['reply'] = text
    app.queue.put((send_bot_message, {
        'message': update.message,
        'text': 'Введи быстрый ответ для {0}:'.format(text)
    }), timeout=10)
    return save_state(context, SET_PHONE_PROPERTY)


def edit_phone_keyboard(phone):
    button_list = [
        [telegram.InlineKeyboardButton('📝 псевдоним',
                                       callback_data='Изменить nick'),
         telegram.InlineKeyboardButton('📝 сайт',
                                       callback_data='Изменить site')],
        [telegram.InlineKeyboardButton('➕ Добавить быстрый ответ', callback_data='Добавить быстрый ответ')],
    ]
    for reply in app.bot_persistence.state['phones'][phone]['replies']:
        button_list.append([telegram.InlineKeyboardButton('📝 {0}'.format(reply),
                                                          callback_data='Изменить {0}'.format(reply)),
                            telegram.InlineKeyboardButton('❌ {0}'.format(reply),
                                                          callback_data='Забыть {0}'.format(reply))])
    button_list.append([telegram.InlineKeyboardButton('🔙 Назад',
                                                      callback_data='Назад'),
                        telegram.InlineKeyboardButton('🚪 Выход',
                                                      callback_data='Выход')])
    return telegram.InlineKeyboardMarkup(button_list)


def edit_phone_reply(phone):
    nick = app.bot_persistence.state['phones'][phone]['nick']
    site = app.bot_persistence.state['phones'][phone]['site']
    replies = app.bot_persistence.state['phones'][phone]['replies']
    text = "редактирование номера *{0}*\n"\
            "Псевдоним: *{1}*\n"\
            "Сайт: *{2}*".format(phone, nick, site)
    if len(replies):
        text += "\nБыстрые ответы:"
        for reply in replies:
            text += "\n*{0}*: {1}".format(reply, replies[reply])
    return text


def handle_add_phone(update, context):
    phone = update.message.text.lstrip('+')
    init_receiver(phone)
    context.chat_data['phone'] = phone
    app.queue.put((send_bot_message, {
        'message': update.message,
        'text': edit_phone_reply(phone),
        'parse_mode': telegram.ParseMode.MARKDOWN,
        'reply_markup': edit_phone_keyboard(phone)
    }), timeout=10)
    return save_state(context, PHONE_EDIT)


def handle_edit_phone_property_query(update, context):
    reply = context.matches[0].group(1)
    context.chat_data['reply'] = reply
    property_ru = {
        'site': 'сайт',
        'nick': 'псевдоним',
    }
    reply = property_ru.get(reply, reply)
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': 'Введи новый *{0}*:'.format(reply),
        'parse_mode': telegram.ParseMode.MARKDOWN
    }), timeout=10)
    return save_state(context, SET_PHONE_PROPERTY)


def handle_delete_phone_property_query(update, context):
    reply = context.matches[0].group(1)
    phone = context.chat_data['phone']
    with lock:
        app.bot_persistence.state['phones'][phone]['replies'].pop(reply, None)
    app.bot_persistence.save_state()
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': edit_phone_reply(phone),
        'parse_mode': telegram.ParseMode.MARKDOWN,
        'reply_markup': edit_phone_keyboard(phone)
    }), timeout=10)
    return save_state(context, PHONE_EDIT)


def handle_set_phone_property(update, context):
    text = update.message.text
    phone = context.chat_data['phone']
    reply = context.chat_data['reply']
    with lock:
        if reply in ['site', 'nick']:
            app.bot_persistence.state['phones'][phone][reply] = text
        else:
            app.bot_persistence.state['phones'][phone]['replies'][reply] = text
    app.bot_persistence.save_state()
    app.queue.put((send_bot_message, {
        'message': update.message,
        'text': edit_phone_reply(phone),
        'parse_mode': telegram.ParseMode.MARKDOWN,
        'reply_markup': edit_phone_keyboard(phone)
    }), timeout=10)
    return save_state(context, PHONE_EDIT)


def handle_edit_phone_query(update, context):
    phone = context.matches[0].group(1)
    context.chat_data['phone'] = phone
    app.queue.put((send_bot_message, {
        'message': update.callback_query.message,
        'text': edit_phone_reply(phone),
        'parse_mode': telegram.ParseMode.MARKDOWN,
        'reply_markup': edit_phone_keyboard(phone)
    }), timeout=10)
    return save_state(context, PHONE_EDIT)


def handle_translate(update, context):
    dest, text = update.message.text.split(' ', 1)
    dest = dest.lstrip('/')
    translation = app.translator.translate(text, src='ru', dest=dest)
    keyboard = None
    if translation.text != text:
        text = '*{1}*'.format(translation.dest, translation.text)
        keyboard = telegram.InlineKeyboardMarkup([[telegram.InlineKeyboardButton('Отправить',
                                                                                 callback_data='Отправить')]])
    else:
        text = 'Перевод такой же!'
    app.queue.put((send_bot_message, {
        'message': update.message,
        'text': text,
        'parse_mode': telegram.ParseMode.MARKDOWN,
        'reply_markup': keyboard
    }), timeout=10)
    return SMS


def handle_sms(update, context):
    return real_handle_sms(update.message, context)


def human_error_handler(update):
    if update['message'] == 'Database encryption key is needed: call checkDatabaseEncryptionKey first':
        app.human._send_encryption_key()
    elif update['message'] == 'Initialization parameters are needed: call setTdlibParameters first':
        app.human._set_initial_params()


def human_auth_state_handler(update):
    if update.authorization_state.ID == 'authorizationStateWaitPhoneNumber':
        app.human._send_phone_number_or_bot_token()
    elif update.authorization_state.ID == 'authorizationStateWaitEncryptionKey':
        app.human._send_encryption_key()
    elif update.authorization_state.ID == 'authorizationStateWaitTdlibParameters':
        app.human._set_initial_params()
    elif update.authorization_state.ID == 'authorizationStateWaitCode':
        app.bot.send_message(chat_id=app.config['TELEGRAM_OWNER'], text='code?')
    elif update.authorization_state.ID == 'authorizationStateWaitPassword':
        app.bot.send_message(chat_id=app.config['TELEGRAM_OWNER'], text='password?')
    elif update.authorization_state.ID == 'authorizationStateReady':
        app.human._complete_authorization()
        app.human._send_data({'@type': 'getUser',
                              'user_id': app.config['TELEGRAM_OWNER']})


def human_connection_state_handler(update):
    if update.state.ID == 'connectionStateReady':
        if app.human._authorized:
            app.human._send_data({'@type': 'getUser',
                                  'user_id': app.config['TELEGRAM_OWNER']})


def human_incoming_handler(update):
    if update.ID == 'updateNewMessage' and update.message.ID == 'message' and \
            update.message.content.ID == 'messageText' and \
            update.message.content.text.ID == 'formattedText':
        text = update.message.content.text.text
        if text.startswith('На номер: '):
            app.human._send_data({'@type': 'pinChatMessage',
                                  'chat_id': update.message.chat_id,
                                  'message_id': update.message.id,
                                  'disable_notification': True})


def handle_human_init(update, context):
    text = update.message.text.lstrip('/set').split(' ', 1)
    app.bot.deleteMessage(chat_id=update.message.chat.id,
                          message_id=update.message.message_id)
    data = {'@type': 'checkAuthenticationPassword',
            text[0]: text[1]}
    if len(text) == 2:
        if text[0] == 'code':
            text[1] = text[1][len(text[1])::-1]
            data[text[0]] = text[1]
            data['@type'] = 'checkAuthenticationCode'
    app.human._send_data(data, result_id='updateAuthorizationState')
    return ConversationHandler.END


def handle_error(update, context):
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))
    payload = ""
    if update.effective_user:
        payload += f' с пользователем @{update.effective_user.username}'
    if update.effective_chat:
        payload += f' в чате *{update.effective_chat.title}*'
        if update.effective_chat.username:
            payload += f' (@{update.effective_chat.username})'
    if update.poll:
        payload += f' с poll id {update.poll.id}.'
    text = f"Эй!\nОшибка *{context.error}* случилась{payload}. полный traceback:\n\n```{trace}```"
    print(text)
    app.bot.send_message(chat_id=app.config['TELEGRAM_DEVELOPER'], text=text,
                         parse_mode=telegram.ParseMode.MARKDOWN)


if __name__ == "__main__":
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PASSWORD: [MessageHandler(Filters.text, handle_password)],
            CONFIG: [CallbackQueryHandler(handle_balance,
                                          pattern='^(Баланс)$'),
                     CallbackQueryHandler(handle_back,
                                          pattern='^(Назад|Выход)$'),
                     CallbackQueryHandler(handle_users,
                                          pattern='^(Администраторы)$'),
                     CallbackQueryHandler(handle_users,
                                          pattern='^(Операторы)$'),
                     CallbackQueryHandler(handle_phones,
                                          pattern='^(Номера телефонов)$')],
            USERS: [CallbackQueryHandler(handle_add_user,
                                         pattern='^Добавить (оператора|администратора)$'),
                    CallbackQueryHandler(handle_back, pattern='^(Назад)$'),
                    CallbackQueryHandler(handle_cancel_query, pattern='^(Выход)$'),
                    CallbackQueryHandler(handle_del_user,
                                         pattern='^Удалить (.+)$')],
            NEW_USER: [MessageHandler(Filters.text, handle_set_user)],
            PHONES_MENU: [CallbackQueryHandler(handle_back_query, pattern='^(Назад)$'),
                          CallbackQueryHandler(handle_cancel_query, pattern='^(Выход)$'),
                          CallbackQueryHandler(handle_add_phone_query, pattern='^(Добавить номер)$'),
                          CallbackQueryHandler(handle_edit_phone_query, pattern='^Изменить (.+)$'),
                          CallbackQueryHandler(handle_del_phone_query, pattern='^Удалить (.+)$')
                          ],
            NEW_PHONE: [MessageHandler(Filters.text, handle_add_phone)],
            NEW_REPLY: [MessageHandler(Filters.text, handle_add_quick_reply)],
            SET_PHONE_PROPERTY: [MessageHandler(Filters.text, handle_set_phone_property)],
            PHONE_EDIT: [CallbackQueryHandler(handle_edit_phone_property_query, pattern='^Изменить (.+)$'),
                         CallbackQueryHandler(handle_delete_phone_property_query, pattern='^Забыть (.+)$'),
                         CallbackQueryHandler(handle_add_quick_reply_name_query, pattern='^(Добавить быстрый ответ)$'),
                         CallbackQueryHandler(handle_back_query, pattern='^(Назад)$'),
                         CallbackQueryHandler(handle_cancel_query, pattern='^(Выход)$')]
        },
        fallbacks=[CommandHandler('cancel', handle_cancel_query)]
    )
    sms_handler = ConversationHandler(
        per_user=False,
        entry_points=[MessageHandler(Filters.status_update.chat_created | Filters.status_update.new_chat_members, handle_chat_start),
                      CommandHandler('help', handle_chat_start)],
        states={
            SMS: [MessageHandler(Filters.text, handle_sms),
                  CallbackQueryHandler(handle_send_translate_query,
                                       pattern='^(.+)$'),
                  CommandHandler(['fr', 'en', 'de'], handle_translate)],
        },
        fallbacks=[MessageHandler(Filters.status_update.left_chat_member, handle_chat_stop)]
    )
    app.dispatcher.add_handler(CommandHandler('setcode', handle_human_init))
    app.dispatcher.add_handler(CommandHandler('setpassword', handle_human_init))
    app.dispatcher.add_handler(conv_handler)
    app.dispatcher.add_handler(sms_handler)
    app.dispatcher.add_error_handler(handle_error)
    app.human.add_handler('error', human_error_handler)
    app.human.add_handler('updateAuthorizationState', human_auth_state_handler)
    app.human.add_handler('updateConnectionState',
                          human_connection_state_handler)
    app.human.add_message_handler(human_incoming_handler)
    app.human._send_encryption_key()
    scheduler.init_app(app)
    scheduler.start()
    app.worker.set_error_handler(send_bot_message, {'chat_id': app.config['TELEGRAM_DEVELOPER']})
    app.worker.run()
    app.run(host=app.config['FLASK_RUN_HOST'],
            port=app.config['FLASK_RUN_PORT'])
