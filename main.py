import logging
import os
from threading import Thread
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# --- CONFIGURAÇÃO DO SERVIDOR WEB (O TRUQUE PARA O RENDER) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot de Vendas está Online!"

def run_http():
    # O Render define a porta na variável de ambiente PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_http)
    t.start()
# -----------------------------------------------------------

# --- LÓGICA DO BOT ---
TOKEN = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'  # <-- Coloque seu token aqui

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    texto = (
        f"Olá, {user_name}! 👋\n\n"
        "Sou seu assistente de vendas.\n"
        "🔥 **Acesso ao Conteúdo VIP**\n"
        "💰 Valor: R$ 29,90\n\n"
        "O envio é automático após o pagamento."
    )
    keyboard = [[InlineKeyboardButton("💳 Comprar Agora", callback_data='comprar')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(texto, reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'comprar':
        # Simulando link de pagamento
        texto_pagamento = (
            "Gerei seu link de pagamento!\n\n"
            "🔗 [Link Simulado - Clique Aqui]\n\n"
            "Após pagar, clique abaixo:"
        )
        keyboard = [[InlineKeyboardButton("✅ Já Paguei", callback_data='confirmar')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=texto_pagamento, reply_markup=reply_markup)

    elif query.data == 'confirmar':
        await query.edit_message_text(text="🔍 Verificando pagamento no sistema...")
        # Simulação de envio do produto
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="✅ **Pagamento Aprovado!**\n\nAqui está seu acesso:\n📂 https://link-do-seu-conteudo.com/download"
        )

# --- INICIALIZAÇÃO ---
if __name__ == '__main__':
    # 1. Inicia o servidor web falso em segundo plano
    keep_alive()
    
    # 2. Inicia o Bot
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click))
    
    print("Bot rodando...")
    application.run_polling()