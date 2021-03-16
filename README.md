Extremely simple Telegram bot that exposes two commands in groups:

- `/kick` can only be issued by the administrators in reply to another user. The bot will kick the replied-to user
- `/kickme` will kick the user who issued the command

What's the point of having a bot doing this simple tasks that users can do on their own? 
When you are removed from a Telegram group (or leave on your own), you 
loose access to your copy of the messages history in that group. The bot API, though, allows bots to kick users and let them keep 
the chat history. Thus, the existence of this bot.

This bot works only in normal groups becuase in supergroups, this "trick" doesn't work and there is no way to kick/leave 
and retain the chat history.

To run the bot: rename `config.example.toml` to `config.toml` and paste your bot token in the relevant field.
