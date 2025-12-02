from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TOKEN = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc' 

async def descobrir_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Se for foto
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        await update.message.reply_text(f"📸 ID da FOTO:\n`{file_id}`", parse_mode='Markdown')
    
    # Se for vídeo
    elif update.message.video:
        file_id = update.message.video.file_id
        await update.message.reply_text(f"🎥 ID do VÍDEO:\n`{file_id}`", parse_mode='Markdown')
        
    # Se for documento/arquivo
    elif update.message.document:
        file_id = update.message.document.file_id
        await update.message.reply_text(f"📂 ID do ARQUIVO:\n`{file_id}`", parse_mode='Markdown')

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    # O bot vai responder a qualquer arquivo que você enviar com o ID dele
    application.add_handler(MessageHandler(filters.ALL, descobrir_id))
    print("Bot Rodando no modo Descobridor...")
    application.run_polling()
