import logging
import os
import asyncio
import mercadopago
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================================================================
# ⚙️ ÁREA DE CONFIGURAÇÃO (SEUS DADOS JÁ ESTÃO AQUI)
# ==============================================================================

# 1. SEU TOKEN DO TELEGRAM
TOKEN_DO_BOT = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'

# 2. SEU ID DE ADMIN
ADMIN_ID = 8118512396

# 3. CONFIGURAÇÃO FINANCEIRA (AUTOMÁTICA)
# ⚠️ IMPORTANTE: Você PRECISA colar seu Token de Produção do Mercado Pago abaixo
# Sem isso, o bot vai dar erro ao tentar gerar o Pix.
MP_ACCESS_TOKEN = 'APP_USR-1151802253593086-120216-db34f09f0a276c014b4ea41f372b5080-7110707'

VALOR_PRODUTO = 9.99 #Valor do Produto (valor que o cliente, vai pagar no pix)

# 4. SEUS ARQUIVOS (VITRINE E PRODUTO)
ID_VITRINE = 'BAACAgEAAxkBAAMRaS8rNKhVKXPYWqXhC970CFlCaYwAAnQGAAKRS3lFP5Q3Hl9lVNg2BA'
TIPO_VITRINE = 'video' 

ID_PRODUTO = 'BQACAgEAAxkBAAMaaS8t485BndGpJ_I2t_gZyj9ZX3QAAncGAAKRS3lFLCbLbVc-e8w2BA'
TIPO_PRODUTO = 'documento'

# ==============================================================================

# Inicializa o SDK do Mercado Pago
try:
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
except:
    print("⚠️ ERRO: Token do Mercado Pago não configurado.")

# --- SISTEMA PARA O RENDER NÃO DESLIGAR O BOT ---
app = Flask('')
@app.route('/')
def home(): return "PrimeFlixx Auto System Online"
def run_http(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_http).start()
# ------------------------------------------------

logging.basicConfig(level=logging.INFO)

# --- 🔄 LOOP DE VALIDAÇÃO AUTOMÁTICA (O CÉREBRO) ---
async def check_payment_loop(context: ContextTypes.DEFAULT_TYPE, chat_id, payment_id, message_id):
    """
    Monitora o pagamento por 15 minutos (90 tentativas de 10s).
    """
    attempts = 0
    max_attempts = 90 
    
    while attempts < max_attempts:
        try:
            # 1. Pergunta ao Mercado Pago o status
            payment_info = sdk.payment().get(int(payment_id))
            status = payment_info["response"]["status"]
            
            # 2. SE APROVADO
            if status == 'approved':
                # Atualiza a mensagem de espera
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="✅ **PAGAMENTO APROVADO!**\n\nO sistema validou seu Pix.\nEnviando seu conteúdo agora...",
                    parse_mode='Markdown'
                )
                
                # Envia o Produto
                legenda = "📂 **Aqui está seu Pack!** Obrigado pela compra."
                try:
                    if TIPO_PRODUTO == 'documento':
                        await context.bot.send_document(chat_id=chat_id, document=ID_PRODUTO, caption=legenda)
                    elif TIPO_PRODUTO == 'video':
                        await context.bot.send_video(chat_id=chat_id, video=ID_PRODUTO, caption=legenda)
                    else:
                        await context.bot.send_photo(chat_id=chat_id, photo=ID_PRODUTO, caption=legenda)
                except Exception as e:
                    await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Erro ao enviar arquivo. Admin, verifique o ID.\nErro: {e}")
                
                return # Sai do loop e encerra

            # 3. SE CANCELADO
            elif status in ['rejected', 'cancelled']:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Pagamento Cancelado.")
                return

            # 4. SE PENDENTE: Espera 10s e tenta de novo
            attempts += 1
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"Erro no loop: {e}")
            await asyncio.sleep(10)

    # Se o tempo acabou
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⏰ Tempo de pagamento esgotado.")
    except:
        pass

# --- COMANDOS DO BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Envia a Vitrine
    try:
        if TIPO_VITRINE == 'video':
            await context.bot.send_video(chat_id=update.effective_chat.id, video=ID_VITRINE, caption="👀 Prévia exclusiva...")
        else:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=ID_VITRINE)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro na vitrine: {e}")
    
    # Texto de Venda
    texto = (
        "Olá! 🔥\n\n"
        "Você está prestes a desbloquear o **Pack Exclusivo**.\n"
        "Veja uma prévia do que te espera acima! 👆\n\n"
        "💎 **Conteúdo Completo em Alta Definição**\n"
        "🚀 **Entrega Imediata e Automática**\n\n"
        f"De ~R$ 29,90~ por apenas **R$ {VALOR_PRODUTO}** hoje."
    )

    # Botão de Compra
    keyboard = [[InlineKeyboardButton("🔓 Quero Acesso Agora", callback_data='comprar')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(texto, reply_markup=reply_markup, parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'comprar':
        # Avisa que está gerando
        msg_temp = await query.edit_message_text("🔄 Gerando seu Pix exclusivo...")
        
        try:
            # 1. Cria Pagamento no Mercado Pago
            payment_data = {
                "transaction_amount": float(VALOR_PRODUTO),
                "description": "Pack Exclusivo",
                "payment_method_id": "pix",
                "payer": {
                    "email": "cliente_anonimo@email.com",
                    "first_name": update.effective_user.first_name
                }
            }
            
            result = sdk.payment().create(payment_data)
            response = result["response"]
            
            # 2. Pega o Código Pix
            pix_copia_cola = response['point_of_interaction']['transaction_data']['qr_code']
            payment_id = response['id']
            
            # 3. Envia o Código
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"`{pix_copia_cola}`", parse_mode='Markdown')
            
            # 4. Envia mensagem de Status
            msg_status = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⏳ **Aguardando Pagamento...**\n\nAssim que você pagar no seu banco, o envio será feito **automaticamente** aqui.\n_(O sistema está monitorando...)_",
                parse_mode='Markdown'
            )
            
            # 🔥 Dispara a verificação em segundo plano
            asyncio.create_task(check_payment_loop(context, update.effective_chat.id, payment_id, msg_status.message_id))
            
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Erro ao gerar Pix: {e}. (Verifique o Token MP)")

# --- FERRAMENTA ADMIN ---
async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        file_id = None
        tipo = ""
        
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            tipo = "FOTO"
        elif update.message.video:
            file_id = update.message.video.file_id
            tipo = "VIDEO"
        elif update.message.document:
            file_id = update.message.document.file_id
            tipo = "DOCUMENTO"
            
        if file_id:
            await update.message.reply_text(f"🛠️ **ADMIN:** {tipo}\n🆔 `{file_id}`", parse_mode='Markdown')

if __name__ == '__main__':
    keep_alive()
    application = ApplicationBuilder().token(TOKEN_DO_BOT).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.ATTACHMENT, admin_tools))
    
    print("Bot Automático Iniciado...")
    application.run_polling()


