from functools import wraps

from telegram import Update, TelegramError, Chat
from telegram.error import BadRequest
from telegram.ext import Updater, CommandHandler, CallbackContext, Filters, MessageHandler

updater = Updater("")


DEEPLINK_SUPERGROUPS_EXPLANATION = "https://t.me/{}?start=supergroups".format(updater.bot.username)

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

TEXT_UPGRADE = """It looks like this group was upgraded to supergroup, but \
<a href="{}">I don't work in supergroups</a>. Bye""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)

TEXT_ADDED_SUPERGROUP = """This group is a supergroup, but \
<a href="{}">I don't work in supergroups</a>. Bye""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)

TEXT_COMMAND_SUPERGROUP = """It looks like this group is not a supergroup, but \
<a href="{}">I don't work in supergroups</a>. Bye""".format(DEEPLINK_SUPERGROUPS_EXPLANATION)


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


def kick_user(update: Update, user_id: int):
    error_message = None

    try:
        update.effective_chat.kick_member(user_id, revoke_messages=False)
        success = True
    except (TelegramError, BadRequest) as e:
        # possible errors:
        # - bot has not the permission to kick members
        # - bot is trying to kick an user that is no longer parte of the group
        # - bot is tryng to kick an administrator with higher rank
        print(e.message)
        success = False
        error_message = e.message

    return success, error_message


def delete_messages(messages):
    for message in messages:
        # noinspection PyBroadException
        try:
            message.delete()
        except Exception:
            pass


@supergroup_check
def on_kick_command(update: Update, context: CallbackContext):
    user_to_kick = update.effective_message.reply_to_message.from_user.id

    success, reason = kick_user(update, user_to_kick)

    if success:
        delete_messages([update.message])
    else:
        update.message.reply_text(reason)


@supergroup_check
def on_kickme_command(update: Update, context: CallbackContext):
    user_to_kick = update.effective_user.id

    success, reason = kick_user(update, user_to_kick)

    if success:
        delete_messages([update.message])
    else:
        update.message.reply_text(reason)


def on_new_chat_member(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        if member.id == updater.bot.id and is_supergroup(update.effective_chat):
            update.message.reply_html(TEXT_ADDED_SUPERGROUP, disable_web_page_preview=True)
            update.effective_chat.leave()
            return


def on_migrate(update: Update, context: CallbackContext):
    update.message.reply_html(TEXT_UPGRADE, disable_web_page_preview=True)
    update.effective_chat.leave()


def main():
    on_kick_command_handler = CommandHandler(["kick"], on_kick_command, Filters.group & Filters.reply)
    on_kickme_command_handler = CommandHandler(["kickme"], on_kickme_command, Filters.group)
    on_new_chat_member_handler = MessageHandler(Filters.status_update.new_chat_members, on_new_chat_member)
    on_migrate_handler = MessageHandler(Filters.status_update.migrate, on_migrate)

    updater.dispatcher.add_handler(on_kick_command_handler)
    updater.dispatcher.add_handler(on_kickme_command_handler)
    updater.dispatcher.add_handler(on_new_chat_member_handler)
    updater.dispatcher.add_handler(on_migrate_handler)

    updater.start_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
