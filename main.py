import logging
import os
import json
import asyncio
import mercadopago
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==============================================================================
# ⚙️ CONFIGURAÇÕES
# ==============================================================================

TOKEN_DO_BOT = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'
ADMIN_ID = 8118512396

# SEUS ARQUIVOS (Confirmados)
ID_VITRINE = 'BAACAgEAAxkBAAMRaS8rNKhVKXPYWqXhC970CFlCaYwAAnQGAAKRS3lFP5Q3Hl9lVNg2BA'
TIPO_VITRINE = 'video' 

ID_PRODUTO = 'BQACAgEAAxkBAAMaaS8t485BndGpJ_I2t_gZyj9ZX3QAAncGAAKRS3lFLCbLbVc-e8w2BA'
TIPO_PRODUTO = 'documento'

# FINANCEIRO
# ⚠️ RECOMENDAÇÃO: Gere um novo token no Mercado Pago por segurança, pois este foi exposto.
MP_ACCESS_TOKEN = 'APP_USR-1151802253593086-120216-db34f09f0a276c014b4ea41f372b5080-7110707' 
VALOR_PRODUTO = 0.01 # PRECO DE TESTE

# CONFIGURAÇÃO DE MARKETING (Dia 2 e 3)
ID_DIA_2 = 'BAACAgEAAxkBAANraTAvKSUG3TxC_CIPrGRsA9ZOnQcAAsAGAAKawYhFoHG-Wdvo9eM2BA' 
TXT_DIA_2 = "Ficou na vontade, {nome} ? 😈 O link vai expirar. Garanta o seu agora."

ID_DIA_3 = 'AgACAgEAAxkBAAOGaTA7SrfoOaeHlz784ThYZ_U__kgAAiMLaxuawYhFLGFNqnmzeL8BAAMCAAN5AAM2BA' 
TXT_DIA_3 = (
    " {nome} ainda esta com medo de não receber seu pack de imagens/videos? 🤔\n\n"
    "Dá uma olhada em quem comprou hoje cedo! 👆\n\n"
    " {nome} Aqui o sistema é automático: Pagou, recebeu na hora. Sem enrolação.\n\n"
    "O valor promocional de **R$ 9,99** esta se encerrando. Vem logo antes de voltar ao preço normal de **R$29,90**"
)

# ==============================================================================

try:
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
except:
    print("⚠️ Token MP não configurado.")

# --- BANCO DE DADOS SEGURO ---
DB_FILE = "database.json"

def carregar_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def salvar_db(dados):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(dados, f, indent=4)
    except: pass

def registrar_usuario(chat_id, nome):
    try:
        db = carregar_db()
        str_id = str(chat_id)
        if str_id not in db:
            db[str_id] = {
                "nome": nome,
                "data_entrada": datetime.now().isoformat(),
                "status": "pendente",
                "funil_dia": 0
            }
            salvar_db(db)
    except: pass # Se der erro, ignora para não travar o bot

def marcar_como_comprador(chat_id):
    try:
        db = carregar_db()
        str_id = str(chat_id)
        if str_id in db:
            db[str_id]["status"] = "comprador"
            salvar_db(db)
    except: pass

# --- SERVIDOR WEB ---
app = Flask('')
@app.route('/')
def home(): return "PrimeFlixx System Online"
def run_http(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_http).start()

logging.basicConfig(level=logging.INFO)

# --- VALIDAÇÃO DE PAGAMENTO (CORRIGIDA) ---
async def check_payment_loop(context: ContextTypes.DEFAULT_TYPE, chat_id, payment_id, message_id):
    attempts = 0
    max_attempts = 90
    
    while attempts < max_attempts:
        try:
            info = sdk.payment().get(int(payment_id))
            status = info["response"]["status"]
            
            if status == 'approved':
                # 1. PRIMEIRO: AVISA O CLIENTE (Prioridade Máxima)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, 
                        message_id=message_id, 
                        text="✅ **PAGAMENTO APROVADO!**\n\nEnviando seu conteúdo agora...", 
                        parse_mode='Markdown'
                    )
                except: pass

                # 2. SEGUNDO: ENTREGA O PRODUTO (Prioridade Máxima)
                legenda = "📂 **Seu Pack Exclusivo!** Obrigada pela compra."
                try:
                    if TIPO_PRODUTO == 'documento': 
                        await context.bot.send_document(chat_id, ID_PRODUTO, caption=legenda)
                    elif TIPO_PRODUTO == 'video': 
                        await context.bot.send_video(chat_id, ID_PRODUTO, caption=legenda)
                    else: 
                        await context.bot.send_photo(chat_id, ID_PRODUTO, caption=legenda)
                except Exception as e:
                    # Se falhar aqui, avisa o admin ou o usuário
                    await context.bot.send_message(chat_id, f"⚠️ Ocorreu um erro no envio do arquivo. Por favor, encaminhe este comprovante ao suporte.\nErro: {e}")

                # 3. TERCEIRO: ATUALIZA O BANCO DE DADOS (Se falhar, não tem problema)
                marcar_como_comprador(chat_id)
                
                return # Encerra o loop com sucesso

            elif status in ['rejected', 'cancelled']:
                await context.bot.edit_message_text(chat_id, message_id, text="❌ Pagamento Cancelado.")
                return

            attempts += 1
            await asyncio.sleep(10)
            
        except Exception as e:
            # Se der erro na conexão, espera e tenta de novo
            print(f"Erro check: {e}")
            await asyncio.sleep(10)

    try: await context.bot.edit_message_text(chat_id, message_id, text="⏰ Tempo de pagamento esgotado.")
    except: pass

# --- MARKETING AUTOMÁTICO ---
async def marketing_automacao_loop(app_context):
    while True:
        try:
            db = carregar_db()
            agora = datetime.now()
            alteracoes = False
            
            for uid, dados in db.items():
                if dados.get("status") != "pendente": continue
                try: entrada = datetime.fromisoformat(dados["data_entrada"])
                except: continue

                dias = (agora - entrada).days
                ultimo = dados.get("funil_dia", 0)

                # Dia 2
                if dias >= 1 and ultimo < 2 and ID_DIA_2:
                    try:
                        try: await app_context.bot.send_photo(uid, ID_DIA_2, caption=TXT_DIA_2)
                        except: await app_context.bot.send_video(uid, ID_DIA_2, caption=TXT_DIA_2)
                        kb = [[InlineKeyboardButton("🔥 Quero Agora", callback_data='comprar')]]
                        await app_context.bot.send_message(uid, "Vem pro VIP! 👇", reply_markup=InlineKeyboardMarkup(kb))
                        db[uid]["funil_dia"] = 2
                        alteracoes = True
                    except: pass
                
                # Dia 3
                elif dias >= 2 and ultimo < 3 and ID_DIA_3:
                    try:
                        try: await app_context.bot.send_photo(uid, ID_DIA_3, caption=TXT_DIA_3)
                        except: await app_context.bot.send_video(uid, ID_DIA_3, caption=TXT_DIA_3)
                        kb = [[InlineKeyboardButton("💎 Desconto VIP", callback_data='comprar')]]
                        await app_context.bot.send_message(uid, "Última chamada! 👇", reply_markup=InlineKeyboardMarkup(kb))
                        db[uid]["funil_dia"] = 3
                        alteracoes = True
                    except: pass

            if alteracoes: salvar_db(db)
            await asyncio.sleep(60 * 60 * 4) 
        except: await asyncio.sleep(60 * 60)

# --- COMANDOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CORREÇÃO: Definindo a variável user corretamente
    user = update.effective_user
    user_name = user.first_name # Cria a variável user_name que estava faltando
    
    registrar_usuario(user.id, user_name)
    
    try:
        if TIPO_VITRINE == 'video': await context.bot.send_video(update.effective_chat.id, ID_VITRINE, caption="👀 Prévia...")
        else: await context.bot.send_photo(update.effective_chat.id, ID_VITRINE)
    except: pass
    
    texto = (
        f"Oi, {user_name}... Sabia que você viria. 😈\n\n"
        "O que você vê nas redes sociais é só 1% do que eu gravo.\n"
        "Aqui, a brincadeira é **sem cortes, sem tarjas e sem limites**.\n\n"
        "🔞 **O que te espera:**\n"
        "• Vídeos Completos em Full HD\n"
        "• Ângulos que nunca mostrei antes\n"
        "• Acesso Vitalício (Baixe e guarde)\n\n"
        "🔥 **De ~R$ 29,90~ mas agora estou fazendo uma Promoção Relâmpago**\n"
        f"👇 Garanta seu lugar antes que o preço suba. **R$ {VALOR_PRODUTO}**"
    )
    kb = [[InlineKeyboardButton("🔓 Quero Acesso Agora", callback_data='comprar')]]
    await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'comprar':
        registrar_usuario(update.effective_chat.id, update.effective_user.first_name)
        msg = await query.edit_message_text("🔄 Gerando Pix...")
        try:
            pay_data = {
                "transaction_amount": float(VALOR_PRODUTO),
                "description": "Pack VIP",
                "payment_method_id": "pix",
                "payer": {"email": "cliente@email.com", "first_name": "Cliente"}
            }
            res = sdk.payment().create(pay_data)["response"]
            pix = res['point_of_interaction']['transaction_data']['qr_code']
            pid = res['id']
            
            await context.bot.send_message(update.effective_chat.id, f"`{pix}`", parse_mode='Markdown')
            status_msg = await context.bot.send_message(update.effective_chat.id, "⏳ **Aguardando Pagamento...**\n_(Monitorando...)_", parse_mode='Markdown')
            asyncio.create_task(check_payment_loop(context, update.effective_chat.id, pid, status_msg.message_id))
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"Erro MP: {e}")

async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    fid = None
    if update.message.photo: fid = update.message.photo[-1].file_id
    elif update.message.video: fid = update.message.video.file_id
    elif update.message.document: fid = update.message.document.file_id
    if fid and not context.args: await update.message.reply_text(f"🆔 ID: `{fid}`", parse_mode='Markdown')

async def broadcast(update, context, filtro):
    if update.effective_user.id != ADMIN_ID: return
    args = context.args
    if len(args) < 2: return await update.message.reply_text("❌ Use: `/comando ID Texto`")
    midia, txt = args[0], " ".join(args[1:])
    db = carregar_db()
    
    alvos = [uid for uid, d in db.items() if filtro == "todos" or 
             (filtro == "pendentes" and d["status"] == "pendente") or 
             (filtro == "compradores" and d["status"] == "comprador")]
             
    await update.message.reply_text(f"🚀 Enviando para {len(alvos)} pessoas...")
    for uid in alvos:
        try:
            try: await context.bot.send_photo(uid, midia, caption=txt)
            except: await context.bot.send_video(uid, midia, caption=txt)
            await asyncio.sleep(0.5)
        except: pass
    await update.message.reply_text("✅ Envio concluído.")

async def aviso_geral(u, c): await broadcast(u, c, "todos")
async def aviso_leads(u, c): await broadcast(u, c, "pendentes")
async def aviso_clientes(u, c): await broadcast(u, c, "compradores")

if __name__ == '__main__':
    keep_alive()
    app_bot = ApplicationBuilder().token(TOKEN_DO_BOT).build()
    app_bot.add_handler(CommandHandler('start', start))
    app_bot.add_handler(CallbackQueryHandler(button_click))
    app_bot.add_handler(MessageHandler(filters.ATTACHMENT, admin_tools))
    app_bot.add_handler(CommandHandler('aviso_geral', aviso_geral))
    app_bot.add_handler(CommandHandler('aviso_leads', aviso_leads))
    app_bot.add_handler(CommandHandler('aviso_clientes', aviso_clientes))
    
    print("Bot PrimeFlixx Seguro Iniciado...")
    loop = asyncio.get_event_loop()
    loop.create_task(marketing_automacao_loop(app_bot))
    app_bot.run_polling()

