import io
import os

import textwrap
import traceback
from contextlib import redirect_stdout

from tg_bot import dispatcher, LOGGER
from tg_bot.modules.helper_funcs.chat_status import owner_plus
from telegram import ParseMode, Update
from telegram.ext import CommandHandler, Filters, CallbackContext

namespaces = {}


def namespace_of(chat, update, bot, context):
    if chat not in namespaces:
        namespaces[chat] = {
            "__builtins__": globals()["__builtins__"],
            "bot": bot,
            "effective_message": update.effective_message,
            "effective_user": update.effective_user,
            "effective_chat": update.effective_chat,
            "update": update,
            "ctx": context,
        }

    return namespaces[chat]


def log_input(update):
    user = update.effective_user.id
    chat = update.effective_chat.id
    LOGGER.info(
        f"IN: {update.effective_message.text} (user={user}, chat={chat})")


def send(msg, bot, update):
    if len(str(msg)) > 2000:
        with io.BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            bot.send_document(chat_id=update.effective_chat.id,
                              document=out_file)
    else:
        LOGGER.info(f"OUT: '{msg}'")
        bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"`{msg}`",
            parse_mode=ParseMode.MARKDOWN,
        )


@owner_plus
def evaluate(update: Update, context: CallbackContext):
    bot = context.bot
    send(do(eval, bot, update, context), bot, update)


@owner_plus
def execute(update: Update, context: CallbackContext):
    bot = context.bot
    send(do(exec, bot, update, context), bot, update)


def cleanup_code(code):
    if code.startswith("```") and code.endswith("```"):
        return "\n".join(code.split("\n")[1:-1])
    return code.strip("` \n")


def do(func, bot, update, context):
    log_input(update)
    content = update.message.text.split(" ", 1)[-1]
    body = cleanup_code(content)
    env = namespace_of(update.message.chat_id, update, bot, context)
    app = dispatcher.bot
    os.chdir(os.getcwd())
    with open(
            os.path.join(os.getcwd(), "tg_bot/modules/helper_funcs/temp.txt"),
            "w",
    ) as temp:
        temp.write(body)

    stdout = io.StringIO()

    to_compile = f'def func():\n{textwrap.indent(body, "  ")}'

    try:
        exec(to_compile, env)
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"

    func = env["func"]

    try:
        with redirect_stdout(stdout):
            func_return = func()
    except Exception as e:
        value = stdout.getvalue()
        return f"{value}{traceback.format_exc()}"
    else:
        value = stdout.getvalue()
        result = None
        if func_return is None:
            if value:
                result = f"{value}"
            else:
                try:
                    result = f"{repr(eval(body, env))}"
                except:
                    pass
        else:
            result = f"{value}{func_return}"
        if result:
            return result


EVAL_HANDLER = CommandHandler("eval", evaluate, run_async=True)
EXEC_HANDLER = CommandHandler("exec", execute, run_async=True)

dispatcher.add_handler(EVAL_HANDLER)
dispatcher.add_handler(EXEC_HANDLER)

__mod_name__ = "Eval Module"
