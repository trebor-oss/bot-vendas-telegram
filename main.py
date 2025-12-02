import logging
import os
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================================================================
# ÁREA DE EDIÇÃO - PREENCHA AQUI COM SEUS DADOS
# ==============================================================================

TOKEN_DO_BOT = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'

# ⚠️ NOVO: Seu ID de usuário (Pegue no @userinfobot). Ex: 123456789
# Sem aspas, apenas números.
ADMIN_ID = 8118512396 

# Link para o cliente pagar (Link do MP, Kiwify ou sua Chave Pix)
LINK_PAGAMENTO = 'https://mpago.la/2VTLkdf'

# ID da Mídia que aparece quando a pessoa clica em /start
ID_VITRINE = 'BAACAgEAAxkBAAMRaS8rNKhVKXPYWqXhC970CFlCaYwAAnQGAAKRS3lFP5Q3Hl9lVNg2BA'
TIPO_VITRINE = 'video' # 'foto' ou 'video'

# ID do Produto que será entregue
ID_PRODUTO = 'BQACAgEAAxkBAAMaaS8t485BndGpJ_I2t_gZyj9ZX3QAAncGAAKRS3lFLCbLbVc-e8w2BA'
# ⚠️ Importante: Mantenha 'documento' se for ZIP/PDF.
TIPO_PRODUTO = 'documento' 

# Textos
TEXTO_BOAS_VINDAS = (
    "Olá! 🔥\n\n"
    "Você está prestes a desbloquear o **Pack Exclusivo**.\n"
    "Veja uma prévia do que te espera acima! 👆\n\n"
    "💎 **Conteúdo Completo em Alta Definição**\n"
    "🚀 **Entrega Imediata**\n\n"
    "De ~R$ 29,90~ por apenas **R$ 9,99** hoje."
)

TEXTO_BOTAO_COMPRAR = "🔓 Quero Acesso Agora"

# ==============================================================================

# --- MANTÉM O BOT ONLINE NO RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Bot Vendedor Online!"
def run_http(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_http).start()
# -------------------------------------

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Envia a vitrine (Foto ou Vídeo)
    try:
        if TIPO_VITRINE == 'video':
            await context.bot.send_video(chat_id=update.effective_chat.id, video=ID_VITRINE, caption="👀 Prévia exclusiva...")
        else:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=ID_VITRINE)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao enviar vitrine. Verifique o ID. Erro: {e}")
    
    # Botão de Compra
    keyboard = [[InlineKeyboardButton(TEXTO_BOTAO_COMPRAR, callback_data='comprar')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(TEXTO_BOAS_VINDAS, reply_markup=reply_markup, parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'comprar':
        texto = (
            "Otima escolha! 🌶️\n\n"
            f"1️⃣ Clique no link: {LINK_PAGAMENTO}\n"
            "2️⃣ Faça o pagamento.\n"
            "3️⃣ Volte aqui e clique no botão abaixo para receber."
        )
        # Botões: Link e Confirmação
        keyboard = [
            [InlineKeyboardButton("🔗 Pagar Agora", url=LINK_PAGAMENTO)],
            [InlineKeyboardButton("✅ Já fiz o Pix", callback_data='confirmar')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=texto, reply_markup=reply_markup)

    elif query.data == 'confirmar':
        await query.edit_message_text(text="⏳ Verificando seu pagamento... Só um instante.")
        
        # AQUI O BOT ENTREGA O PRODUTO
        try:
            legenda = "📂 Aqui está seu Pack! Obrigado pela compra."
            
            if TIPO_PRODUTO == 'documento':
                await context.bot.send_document(chat_id=update.effective_chat.id, document=ID_PRODUTO, caption=legenda)
            elif TIPO_PRODUTO == 'video':
                await context.bot.send_video(chat_id=update.effective_chat.id, video=ID_PRODUTO, caption=legenda)
            else:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=ID_PRODUTO, caption=legenda)
                
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Qualquer dúvida, chame o suporte.")
            
        except Exception as e:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ Erro na entrega. O Admin precisa verificar o ID do arquivo.\nErro: {e}")

# --- NOVA FUNÇÃO: FERRAMENTA PARA O ADMIN (VOCÊ) ---
async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Só responde se for VOCÊ (O Admin)
    if user_id == ADMIN_ID:
        file_id = None
        tipo = ""
        
        # Detecta qual tipo de arquivo você mandou
        if update.message.photo:
            file_id = update.message.photo[-1].file_id # Pega a maior resolução
            tipo = "FOTO"
        elif update.message.video:
            file_id = update.message.video.file_id
            tipo = "VIDEO"
        elif update.message.document:
            file_id = update.message.document.file_id
            tipo = "DOCUMENTO (ZIP/PDF)"
            
        if file_id:
            await update.message.reply_text(
                f"🛠️ **MODO ADMIN DETECTADO**\n\n"
                f"TIPO: {tipo}\n"
                f"🆔 COPIE O CÓDIGO ABAIXO:\n"
                f"`{file_id}`",
                parse_mode='Markdown'
            )

if __name__ == '__main__':
    keep_alive()
    application = ApplicationBuilder().token(TOKEN_DO_BOT).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Adiciona o "ouvinte" de arquivos para o Admin
    # Filtra apenas fotos, vídeos ou documentos
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, admin_tools))
    
    print("Bot de Vendas Iniciado...")
    application.run_polling()
