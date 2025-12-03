import logging
import os
import asyncio
import mercadopago
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================================================================
# ⚙️ ÁREA DE CONFIGURAÇÃO
# ==============================================================================

# 1. SEUS DADOS (JÁ CONFIGURADOS)
TOKEN_DO_BOT = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'
ADMIN_ID = 8118512396

# 2. CONFIGURAÇÃO DOS ARQUIVOS (VITRINE E PRODUTO)
ID_VITRINE = 'BAACAgEAAxkBAAMRaS8rNKhVKXPYWqXhC970CFlCaYwAAnQGAAKRS3lFP5Q3Hl9lVNg2BA'
TIPO_VITRINE = 'video' 

ID_PRODUTO = 'BQACAgEAAxkBAAMaaS8t485BndGpJ_I2t_gZyj9ZX3QAAncGAAKRS3lFLCbLbVc-e8w2BA'
TIPO_PRODUTO = 'documento'

# 3. FINANCEIRO (AUTOMÁTICO)
# ⚠️ COLE SEU TOKEN DE PRODUÇÃO DO MERCADO PAGO ABAIXO:
MP_ACCESS_TOKEN = 'CO8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bcLE_SEU_TOKEN_MERCADO_PAGO_AQUI'
VALOR_PRODUTO = 9.99

# ==============================================================================

# Inicializa SDK Mercado Pago
try:
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
except:
    print("⚠️ Token MP não configurado.")

# --- SISTEMA DE BANCO DE DADOS (SIMPLES) ---
CLIENTES_FILE = "clientes.txt"

def salvar_cliente(chat_id):
    """Salva o ID do cliente numa lista segura"""
    lista = []
    # Lê os existentes
    if os.path.exists(CLIENTES_FILE):
        with open(CLIENTES_FILE, "r") as f:
            lista = f.read().splitlines()
    
    # Se for novo, salva
    if str(chat_id) not in lista:
        with open(CLIENTES_FILE, "a") as f:
            f.write(f"{chat_id}\n")

def ler_clientes():
    """Lê todos os clientes para enviar mensagem"""
    if os.path.exists(CLIENTES_FILE):
        with open(CLIENTES_FILE, "r") as f:
            return f.read().splitlines()
    return []

# --- SERVIDOR WEB ---
app = Flask('')
@app.route('/')
def home(): return "PrimeFlixx Marketing System On"
def run_http(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_http).start()

logging.basicConfig(level=logging.INFO)

# --- LOOP DE PAGAMENTO (VALIDAÇÃO AUTOMÁTICA) ---
async def check_payment_loop(context: ContextTypes.DEFAULT_TYPE, chat_id, payment_id, message_id):
    attempts = 0
    max_attempts = 90 # 15 minutos
    
    while attempts < max_attempts:
        try:
            payment_info = sdk.payment().get(int(payment_id))
            status = payment_info["response"]["status"]
            
            if status == 'approved':
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="✅ **PAGAMENTO APROVADO!**\n\nEnviando seu conteúdo...", parse_mode='Markdown'
                )
                legenda = "📂 **Seu Pack Exclusivo!** Obrigado."
                try:
                    if TIPO_PRODUTO == 'documento': await context.bot.send_document(chat_id, ID_PRODUTO, caption=legenda)
                    elif TIPO_PRODUTO == 'video': await context.bot.send_video(chat_id, ID_PRODUTO, caption=legenda)
                    else: await context.bot.send_photo(chat_id, ID_PRODUTO, caption=legenda)
                except Exception as e:
                    await context.bot.send_message(chat_id, f"Erro entrega: {e}")
                return 

            elif status in ['rejected', 'cancelled']:
                await context.bot.edit_message_text(chat_id, message_id, text="❌ Pagamento Cancelado.")
                return

            attempts += 1
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(10)
            
    try: await context.bot.edit_message_text(chat_id, message_id, text="⏰ Tempo esgotado.")
    except: pass

# --- COMANDOS PRINCIPAIS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. SALVA O CLIENTE NA LISTA
    salvar_cliente(update.effective_chat.id)
    
    # 2. MOSTRA A VITRINE
    try:
        if TIPO_VITRINE == 'video': await context.bot.send_video(update.effective_chat.id, ID_VITRINE, caption="👀 Prévia...")
        else: await context.bot.send_photo(update.effective_chat.id, ID_VITRINE)
    except: pass
    
    texto = (
        "Olá! 🔥\n\nVocê está prestes a desbloquear o **Pack Exclusivo**.\n"
        "💎 **Conteúdo Completo HD**\n🚀 **Entrega Automática**\n\n"
        f"Promoção: **R$ {VALOR_PRODUTO}**"
    )
    kb = [[InlineKeyboardButton("🔓 Quero Acesso Agora", callback_data='comprar')]]
    await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'comprar':
        msg = await query.edit_message_text("🔄 Gerando Pix...")
        try:
            pay_data = {
                "transaction_amount": float(VALOR_PRODUTO),
                "description": "Pack VIP",
                "payment_method_id": "pix",
                "payer": {"email": "cliente@email.com", "first_name": "Cliente"}
            }
            res = sdk.payment().create(pay_data)["response"]
            pix_code = res['point_of_interaction']['transaction_data']['qr_code']
            pid = res['id']
            
            await context.bot.send_message(update.effective_chat.id, f"`{pix_code}`", parse_mode='Markdown')
            status_msg = await context.bot.send_message(update.effective_chat.id, "⏳ **Aguardando Pagamento...**\n_(Monitorando...)_", parse_mode='Markdown')
            
            # Inicia verificação em segundo plano
            asyncio.create_task(check_payment_loop(context, update.effective_chat.id, pid, status_msg.message_id))
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"Erro MP: {e}")

# --- 🚀 SISTEMA DE REMARKETING (BROADCAST) ---

async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pega ID de arquivos que o Admin envia"""
    if update.effective_user.id != ADMIN_ID: return

    file_id = None
    if update.message.photo: file_id = update.message.photo[-1].file_id
    elif update.message.video: file_id = update.message.video.file_id
    elif update.message.document: file_id = update.message.document.file_id
    
    # Se mandou arquivo sem comando, mostra o ID
    if file_id and not context.args:
        await update.message.reply_text(f"🆔 ID: `{file_id}`", parse_mode='Markdown')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando para enviar mensagens em massa.
    Uso: /enviar ID_DA_MIDIA Texto da Mensagem
    """
    # Segurança: Só o Admin pode usar
    if update.effective_user.id != ADMIN_ID: return
    
    try:
        # Pega os argumentos (ID da foto + Texto)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Uso correto:\n`/enviar ID_DA_MIDIA Escreva sua mensagem aqui`", parse_mode='Markdown')
            return

        midia_id = args[0]
        texto_msg = " ".join(args[1:]) # Junta todo o resto do texto
        
        clientes = ler_clientes()
        if not clientes:
            await update.message.reply_text("❌ Nenhum cliente salvo ainda.")
            return

        await update.message.reply_text(f"🚀 Iniciando envio para {len(clientes)} clientes...")
        
        enviados = 0
        bloqueados = 0
        
        for chat_id in clientes:
            try:
                # Tenta enviar como Foto primeiro
                try:
                    await context.bot.send_photo(chat_id=chat_id, photo=midia_id, caption=texto_msg)
                except:
                    # Se falhar (ex: ID é de video), tenta como Vídeo
                    await context.bot.send_video(chat_id=chat_id, video=midia_id, caption=texto_msg)
                
                enviados += 1
                await asyncio.sleep(0.5) # Pausa pequena para não ser banido por spam
            except:
                bloqueados += 1 # Cliente bloqueou o bot
        
        await update.message.reply_text(f"✅ FIM!\n\nEnviados: {enviados}\nFalhas/Bloqueios: {bloqueados}")
        
    except Exception as e:
        await update.message.reply_text(f"Erro no comando: {e}")

if __name__ == '__main__':
    keep_alive()
    app_bot = ApplicationBuilder().token(TOKEN_DO_BOT).build()
    
    app_bot.add_handler(CommandHandler('start', start))
    app_bot.add_handler(CommandHandler('enviar', broadcast)) # Novo comando
    app_bot.add_handler(CallbackQueryHandler(button_click))
    app_bot.add_handler(MessageHandler(filters.ATTACHMENT, admin_tools))
    
    print("Bot PrimeFlixx + Marketing Iniciado...")
    app_bot.run_polling()
