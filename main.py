from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8071043602:AAHDmlntOwHbEs5tCcJDDQeb6i0B-XecXDs"
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello!")
def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Bot started")
    app.run_polling()
if __name__ == "__main__":
    run_bot()