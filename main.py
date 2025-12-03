import logging
import os
import json
import asyncio
import mercadopago
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================================================================
# ⚙️ CONFIGURAÇÕES GERAIS
# ==============================================================================

TOKEN_DO_BOT = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'
ADMIN_ID = 8118512396
MP_ACCESS_TOKEN = 'APP_USR-1151802253593086-120216-db34f09f0a276c014b4ea41f372b5080-7110707' # TOKEN MERCADO PAGO
VALOR_PRODUTO = 9.99 #VALOR QUE O CLIENTE IRA PAGAR

# PRODUTO PRINCIPAL (Start)
ID_VITRINE = 'BAACAgEAAxkBAAMRaS8rNKhVKXPYWqXhC970CFlCaYwAAnQGAAKRS3lFP5Q3Hl9lVNg2BA'
TIPO_VITRINE = 'video'
ID_PRODUTO = 'BQACAgEAAxkBAAMaaS8t485BndGpJ_I2t_gZyj9ZX3QAAncGAAKRS3lFLCbLbVc-e8w2BA'
TIPO_PRODUTO = 'documento'

# ==============================================================================
# 🔥 CONFIGURAÇÃO DE MARKETING (FUNIL AUTOMÁTICO)
# Preencha os IDs após descobri-los com o modo Admin
# ==============================================================================

# DIA 2: FOCO NO DESEJO (Enviado 24h após entrar se não comprar)
ID_DIA_2 = ''  # Cole o ID da foto/vídeo do Dia 2 aqui
TXT_DIA_2 = (
    "Ficou na vontade? 😈\n\n"
    "Essa é só uma das 50 mídias que estão no pack.\n"
    "O link vai expirar em breve. Garanta o seu agora."
)

# DIA 3: PROVA SOCIAL (Enviado 48h após entrar se não comprar)
ID_DIA_3 = ''  # Cole o ID da foto/vídeo do Dia 3 aqui
TXT_DIA_3 = (
    "Muita gente a perguntar se é real... Tá aí a prova! 🔥\n\n"
    "Última chance de entrar no grupo VIP pelo valor promocional.\n"
    "Clica aqui para não perder."
)

# ==============================================================================

try:
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
except:
    print("⚠️ Token MP não configurado.")

# --- SISTEMA DE BANCO DE DADOS (JSON) ---
DB_FILE = "database.json"

def carregar_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def salvar_db(dados):
    with open(DB_FILE, "w") as f:
        json.dump(dados, f, indent=4)

def registrar_usuario(chat_id, nome):
    """Registra entrada do usuário se não existir"""
    db = carregar_db()
    str_id = str(chat_id)
    if str_id not in db:
        db[str_id] = {
            "nome": nome,
            "data_entrada": datetime.now().isoformat(),
            "status": "pendente", # pendente ou comprador
            "funil_dia": 0 # 0=novo, 1=recebeu dia 1, 2=recebeu dia 2...
        }
        salvar_db(db)

def marcar_como_comprador(chat_id):
    """Atualiza status para Comprador (para parar de receber mkt de vendas)"""
    db = carregar_db()
    str_id = str(chat_id)
    if str_id in db:
        db[str_id]["status"] = "comprador"
        salvar_db(db)

# --- SERVIDOR WEB (KEEP ALIVE) ---
app = Flask('')
@app.route('/')
def home(): return "PrimeFlixx Marketing Pro Online"
def run_http(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_http).start()

logging.basicConfig(level=logging.INFO)

# --- LOOP DE MARKETING AUTOMÁTICO (RODA EM SEGUNDO PLANO) ---
async def marketing_automacao_loop(app_context):
    """Verifica todos os dias quem precisa receber mensagem"""
    while True:
        try:
            logging.info("🔄 Rodando verificação de Marketing Automático...")
            db = carregar_db()
            agora = datetime.now()
            alteracoes = False
            
            for user_id, dados in db.items():
                # Só envia marketing para quem NÃO comprou
                if dados.get("status") != "pendente":
                    continue
                
                try:
                    entrada = datetime.fromisoformat(dados["data_entrada"])
                except:
                    continue # Pula se data estiver bugada

                dias_passados = (agora - entrada).days
                ultimo_envio = dados.get("funil_dia", 0)

                # REGRA DO DIA 2 (24h depois)
                if dias_passados >= 1 and ultimo_envio < 2:
                    if ID_DIA_2: # Só envia se tiver configurado
                        try:
                            # Tenta foto ou vídeo
                            try: await app_context.bot.send_photo(user_id, ID_DIA_2, caption=TXT_DIA_2)
                            except: await app_context.bot.send_video(user_id, ID_DIA_2, caption=TXT_DIA_2)
                            
                            # Botão de compra novamente
                            kb = [[InlineKeyboardButton("🔥 Quero Agora", callback_data='comprar')]]
                            await app_context.bot.send_message(user_id, "Vem pro VIP! 👇", reply_markup=InlineKeyboardMarkup(kb))
                            
                            db[user_id]["funil_dia"] = 2
                            alteracoes = True
                        except Exception as e:
                            logging.error(f"Falha envio Dia 2 para {user_id}: {e}")

                # REGRA DO DIA 3 (48h depois)
                elif dias_passados >= 2 and ultimo_envio < 3:
                    if ID_DIA_3:
                        try:
                            try: await app_context.bot.send_photo(user_id, ID_DIA_3, caption=TXT_DIA_3)
                            except: await app_context.bot.send_video(user_id, ID_DIA_3, caption=TXT_DIA_3)
                            
                            kb = [[InlineKeyboardButton("💎 Acessar VIP com Desconto", callback_data='comprar')]]
                            await app_context.bot.send_message(user_id, "Última chamada! 👇", reply_markup=InlineKeyboardMarkup(kb))
                            
                            db[user_id]["funil_dia"] = 3
                            alteracoes = True
                        except: pass

            if alteracoes:
                salvar_db(db)
                
            # Verifica a cada 4 horas (para não sobrecarregar)
            await asyncio.sleep(60 * 60 * 4) 
            
        except Exception as e:
            logging.error(f"Erro no loop de marketing: {e}")
            await asyncio.sleep(60 * 60) # Espera 1h se der erro

# --- LOOP DE PAGAMENTO (VALIDAÇÃO) ---
async def check_payment_loop(context: ContextTypes.DEFAULT_TYPE, chat_id, payment_id, message_id):
    attempts = 0
    while attempts < 90:
        try:
            info = sdk.payment().get(int(payment_id))
            status = info["response"]["status"]
            
            if status == 'approved':
                # 1. Atualiza Status no Banco de Dados (Para parar de receber mkt de vendas)
                marcar_como_comprador(chat_id)
                
                await context.bot.edit_message_text(chat_id, message_id, text="✅ **PAGAMENTO APROVADO!**\n\nEnviando conteúdo...")
                legenda = "📂 **Seu Pack Exclusivo!** Aproveite."
                try:
                    if TIPO_PRODUTO == 'documento': await context.bot.send_document(chat_id, ID_PRODUTO, caption=legenda)
                    elif TIPO_PRODUTO == 'video': await context.bot.send_video(chat_id, ID_PRODUTO, caption=legenda)
                    else: await context.bot.send_photo(chat_id, ID_PRODUTO, caption=legenda)
                except Exception as e:
                    await context.bot.send_message(chat_id, f"Erro entrega: {e}")
                return 

            elif status in ['rejected', 'cancelled']:
                await context.bot.edit_message_text(chat_id, message_id, text="❌ Cancelado.")
                return
            attempts += 1
            await asyncio.sleep(10)
        except: await asyncio.sleep(10)
    try: await context.bot.edit_message_text(chat_id, message_id, text="⏰ Tempo esgotado.")
    except: pass

# --- COMANDOS PRINCIPAIS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    registrar_usuario(user.id, user.first_name)
    
    try:
        if TIPO_VITRINE == 'video': await context.bot.send_video(user.id, ID_VITRINE, caption="👀 Prévia...")
        else: await context.bot.send_photo(user.id, ID_VITRINE)
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
        registrar_usuario(update.effective_chat.id, update.effective_user.first_name) # Garante registro
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
            asyncio.create_task(check_payment_loop(context, update.effective_chat.id, pid, status_msg.message_id))
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"Erro MP: {e}")

# --- FERRAMENTAS DO ADMIN (SEGMENTAÇÃO) ---
async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    # Mostra ID de qualquer arquivo enviado pelo admin
    file_id = None
    if update.message.photo: file_id = update.message.photo[-1].file_id
    elif update.message.video: file_id = update.message.video.file_id
    elif update.message.document: file_id = update.message.document.file_id
    if file_id and not context.args: await update.message.reply_text(f"🆔 ID: `{file_id}`", parse_mode='Markdown')

async def enviar_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, filtro):
    """Função genérica de envio"""
    if update.effective_user.id != ADMIN_ID: return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Use: `/comando ID_MIDIA Texto...`", parse_mode='Markdown')
        return

    midia_id = args[0]
    texto = " ".join(args[1:])
    
    db = carregar_db()
    destinatarios = []
    
    # Filtra quem vai receber
    for uid, dados in db.items():
        if filtro == "todos": destinatarios.append(uid)
        elif filtro == "pendentes" and dados["status"] == "pendente": destinatarios.append(uid)
        elif filtro == "compradores" and dados["status"] == "comprador": destinatarios.append(uid)
        
    if not destinatarios:
        await update.message.reply_text("Ninguém encontrado para esse filtro.")
        return

    await update.message.reply_text(f"🚀 Enviando para {len(destinatarios)} pessoas ({filtro})...")
    
    sucesso = 0
    for chat_id in destinatarios:
        try:
            try: await context.bot.send_photo(chat_id, midia_id, caption=texto)
            except: await context.bot.send_video(chat_id, midia_id, caption=texto)
            sucesso += 1
            await asyncio.sleep(0.5)
        except: pass
        
    await update.message.reply_text(f"✅ Enviado com sucesso para {sucesso} usuários.")

# Comandos Específicos
async def aviso_geral(update, context): await enviar_broadcast(update, context, "todos")
async def aviso_leads(update, context): await enviar_broadcast(update, context, "pendentes")
async def aviso_clientes(update, context): await enviar_broadcast(update, context, "compradores")

if __name__ == '__main__':
    keep_alive()
    app_bot = ApplicationBuilder().token(TOKEN_DO_BOT).build()
    
    app_bot.add_handler(CommandHandler('start', start))
    app_bot.add_handler(CallbackQueryHandler(button_click))
    app_bot.add_handler(MessageHandler(filters.ATTACHMENT, admin_tools))
    
    # Novos Comandos de Segmentação
    app_bot.add_handler(CommandHandler('aviso_geral', aviso_geral))     # Manda pra todo mundo
    app_bot.add_handler(CommandHandler('aviso_leads', aviso_leads))     # Manda pra quem NÃO comprou (Remarketing manual)
    app_bot.add_handler(CommandHandler('aviso_clientes', aviso_clientes)) # Manda pra quem JÁ comprou (Atualizações)

    print("Bot Marketing Pro Iniciado...")
    
    # Inicia o Loop de Automação (Dia 2 e Dia 3)
    loop = asyncio.get_event_loop()
    loop.create_task(marketing_automacao_loop(app_bot))
    
    app_bot.run_polling()
