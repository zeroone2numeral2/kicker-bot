import json
import logging
import logging.config
import re
from functools import wraps

from telegram import Update, TelegramError, Chat, ParseMode, Bot
from telegram.error import BadRequest
from telegram.ext import Updater, CommandHandler, CallbackContext, Filters, MessageHandler
from telegram.utils import helpers

from mwt import MWT
from config import config

updater = Updater(config.telegram.token, workers=0)


DEEPLINK_SUPERGROUPS_EXPLANATION = helpers.create_deep_linked_url(updater.bot.username, "supergroups")

SUPERGROUPS = """I see you're wondering why I left your chat, uh? Well it's not easy to explain, but I'll try my best.

I'm a bot that was built to let people leave groups without loosing the messages history.
When you leave a Telegram group (or when you are removed by an admin), you will loose access to the messages history \
in that chat. Luckily, bots can remove users by asking Telegram to kick them out of groups without wiping out the \
messages history, so they will still be able to access it even after they are removed. Pretty coool uh?
The sad part is that this works in "normal" groups only - that is, group chats that haven't been converted to \
supergroup yet.

<i>"What? My group is not a supergroup, I don't even know what a supergroup is"</i>, you might be thinking. \
Here comes the complicated part, but bear with me. In Telegram, there are two types of groups: the so-called \
"normal groups" (or "legacy groups"), and supergroups. When you create a Telegram group, you always create a \
<i>normal</i> group. Normal groups offer a limited set of features: when you use one of the features that are not \
supported by normal groups, the group is automatically upgraded to supergroup. This all happens silently \
and you won't even notice.

<i>"Okay, cool, thanks for the explanation. I still don't undesrtand how this has anything to do with you leaving\
 the group"</i>. Fair enough. \
It's actually pretty simple: the group has been converted to supergroup silently, and in supergroups, \
bots can't use that little \
trick to kick people and preserve their copy of the chat history. When you leave or are removed from \
a supergroup, there is no way to retain the chat history.

Worry not, though: you can use <a href="https://desktop.telegram.org">Telegram Desktop</a> to save a backup of \
your chats' histories before leaving them \
(<i>open a group > click on the group title > three dots menu > "export chat history"</i>)"""

TEXT_START = """Hello there 👋

I'm a simple bot that allows you to leave a group or kick people in a way that the leaving/kicked member doesn't loose \
their copy of the chat history. <a href="{}">I don't work in supergroups</a>: if you add me to a supergroup, \
I will leave it 😔

Only the group administrators can kick people, so <b>make sure to \
promote me after adding me to a chat!</b>

<b>Commands:</b>
• <code>!kickme</code>: the bot will kick you from the group, but you'll still be able to access your copy of the \
chat history
• <code>!kick</code> (admins only, in reply to another user): kick an user and let them keep their copy of the \
chat history

Commands work with the "<code>!</code>" and not with the classic "<code>/</code>" to avoid to trigger people's \
instinctive reaction to click on them

<a href="https://github.com/zeroone2numeral2/kicker-bot">⚙️ source code</a>""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)

TEXT_UPGRADE = """It looks like this group was upgraded to supergroup, but \
<a href="{}">I don't work in supergroups</a>. Bye 👋""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)

TEXT_ADDED_SUPERGROUP = """This group is a supergroup, but \
<a href="{}">I don't work in supergroups</a>. Bye 👋""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)

TEXT_COMMAND_SUPERGROUP = """It looks like this group is not a supergroup, but \
<a href="{}">I don't work in supergroups</a>. Bye 👋""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)


def load_logging_config(file_name='logging.json'):
    with open(file_name, 'r') as f:
        logging_config = json.load(f)

    logging.config.dictConfig(logging_config)


load_logging_config("logging.json")

logger = logging.getLogger(__name__)


def is_supergroup(chat: Chat):
    return str(chat.id).startswith("-100")


def supergroup_check(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        if update.effective_chat.id < 0 and is_supergroup(update.effective_chat):
            # chat is a supergroup: leave
            update.message.reply_html(TEXT_COMMAND_SUPERGROUP, disable_web_page_preview=True)
            update.effective_chat.leave()
            return

        return func(update, context, *args, **kwargs)

    return wrapped


@MWT(timeout=60 * 60)
def get_admin_ids(bot: Bot, chat_id: int):
    return [admin.user.id for admin in bot.get_chat_administrators(chat_id)]


def administrators(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        if update.effective_user.id not in get_admin_ids(context.bot, update.effective_chat.id):
            logger.debug("admin check failed")
            return

        return func(update, context, *args, **kwargs)

    return wrapped


def kick_user(update: Update, user_id: int):
    error_message = None

    try:
        update.effective_chat.kick_member(user_id, revoke_messages=False)
        success = True
    except (TelegramError, BadRequest) as e:
        logger.error("error while kicking: %s", e.message)
        # possible errors:
        # - bot has not the permission to kick members
        # - bot is trying to kick an user that is no longer part of the group
        # - bot is tryng to kick an administrator with higher rank
        error_lower = e.message.lower()
        success = False
        error_message = "Error: <code>{}</code>".format(e.message)

        if error_lower == "chat_admin_required":
            error_message = "⚠️ <i>either I'm not an administrator, or the user I have to kick is an administrator too</i>"
        elif error_lower == "user_not_participant":
            error_message = "⚠️ <i>the user is not a member of this group</i>"

    return success, error_message


def delete_messages(messages):
    for message in messages:
        # noinspection PyBroadException
        try:
            message.delete()
        except Exception:
            pass


@administrators
@supergroup_check
def on_kick_command(update: Update, context: CallbackContext):
    logger.debug("!kick command")

    user_to_kick = update.effective_message.reply_to_message.from_user.id
    if user_to_kick == updater.bot.id:
        update.message.reply_html("Just remove me manually")
        return

    success, reason = kick_user(update, user_to_kick)

    if success:
        delete_messages([update.message])
    else:
        update.message.reply_html(reason)


@supergroup_check
def on_kickme_command(update: Update, context: CallbackContext):
    logger.debug("!kickme command")

    user_to_kick = update.effective_user.id

    success, reason = kick_user(update, user_to_kick)

    if success:
        delete_messages([update.message])
    else:
        update.message.reply_html(reason)


def on_new_chat_member(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        if member.id == updater.bot.id and is_supergroup(update.effective_chat):
            logger.debug("bot added to a supergroup")

            update.message.reply_html(TEXT_ADDED_SUPERGROUP, disable_web_page_preview=True)
            update.effective_chat.leave()
            return


def on_migrate(update: Update, context: CallbackContext):
    logger.debug("chat migrated")

    new_supergroup_id = update.message.migrate_to_chat_id
    context.bot.send_message(new_supergroup_id, TEXT_UPGRADE, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    context.bot.leave_chat(new_supergroup_id, updater.bot.id)


def on_supergroups_deeplink(update: Update, context: CallbackContext):
    logger.debug("supergroups deeplink")

    update.message.reply_html(SUPERGROUPS, disable_web_page_preview=True)


def on_start_command(update: Update, context: CallbackContext):
    logger.debug("/start or /help")

    update.message.reply_html(TEXT_START, disable_web_page_preview=True)


def main():
    kick_re = re.compile(r"^!kick(?:$|\b).*", re.IGNORECASE)
    kickme_re = re.compile(r"^!kickme(?:$|\b).*", re.IGNORECASE)

    on_supergroups_deeplink_handler = CommandHandler("start", on_supergroups_deeplink, Filters.regex("supergroups"))
    on_start_command_handler = CommandHandler(["start", "help"], on_start_command, Filters.chat_type.private)
    on_kick_command_handler = MessageHandler(Filters.chat_type.groups & Filters.reply & Filters.regex(kick_re), on_kick_command)
    on_kickme_command_handler = MessageHandler(Filters.chat_type.groups & Filters.regex(kickme_re), on_kickme_command)
    on_new_chat_member_handler = MessageHandler(Filters.status_update.new_chat_members, on_new_chat_member)
    on_migrate_handler = MessageHandler(Filters.status_update.migrate, on_migrate)

    updater.dispatcher.add_handler(on_supergroups_deeplink_handler)  # needs to be added before "on_start_command_handler"
    updater.dispatcher.add_handler(on_start_command_handler)
    updater.dispatcher.add_handler(on_kick_command_handler)
    updater.dispatcher.add_handler(on_kickme_command_handler)
    updater.dispatcher.add_handler(on_new_chat_member_handler)
    updater.dispatcher.add_handler(on_migrate_handler)

    updater.bot.set_my_commands([])

    logger.info("running as @%s", updater.bot.username)
    updater.start_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
