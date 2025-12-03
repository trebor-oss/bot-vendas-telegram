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
# ⚙️ CONFIGURAÇÕES GERAIS
# ==============================================================================

TOKEN_DO_BOT = '8553730181:AAF6ko-j_bJ5C5qrJn6wRLTsdgCTpsVV3bc'
ADMIN_ID = 8118512396

# SEUS ARQUIVOS
ID_VITRINE = 'BAACAgEAAxkBAAMRaS8rNKhVKXPYWqXhC970CFlCaYwAAnQGAAKRS3lFP5Q3Hl9lVNg2BA'
TIPO_VITRINE = 'video' 
ID_PRODUTO = 'BQACAgEAAxkBAAPlaTBbPtZ8d4PJ7z205epByhalr5cAAuoGAAKawYhFZgL2GysJ2_w2BA'
TIPO_PRODUTO = 'documento'

# FINANCEIRO
# ⚠️ IMPORTANTE: Cole seu Token do Mercado Pago aqui
MP_ACCESS_TOKEN = 'APP_USR-1151802253593086-120216-db34f09f0a276c014b4ea41f372b5080-7110707' 
VALOR_PRODUTO = 0.01   # Preço do Pack
VALOR_MENSAGEM = 0.02  # Preço simbólico para falar com você

# MARKETING AUTOMÁTICO (Dia 2 e 3)
# O código {nome} será substituído pelo nome do usuário automaticamente
ID_DIA_2 = 'BAACAgEAAxkBAANraTAvKSUG3TxC_CIPrGRsA9ZOnQcAAsAGAAKawYhFoHG-Wdvo9eM2BA' 
TXT_DIA_2 = "Ficou na vontade, {nome}? 😈 O link vai expirar. Garanta o seu agora."

ID_DIA_3 = 'AgACAgEAAxkBAAOGaTA7SrfoOaeHlz784ThYZ_U__kgAAiMLaxuawYhFLGFNqnmzeL8BAAMCAAN5AAM2BA' 
TXT_DIA_3 = "Ainda com medo, {nome}? 🤔 Olha quem comprou hoje! O valor de R$ 9,99 vai subir."

# ==============================================================================

try:
    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
except:
    print("⚠️ Token MP não configurado.")

# --- BANCO DE DADOS ---
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
    """Salva ou atualiza o nome do usuário no banco de dados"""
    try:
        db = carregar_db()
        str_id = str(chat_id)
        
        # Garante que temos um nome, senão usa "Amor" como fallback
        if not nome: nome = "Amor"
            
        if str_id not in db:
            db[str_id] = {
                "nome": nome,
                "data_entrada": datetime.now().isoformat(),
                "status": "pendente",
                "funil_dia": 0,
                "pode_mandar_msg": False 
            }
        else:
            # Atualiza o nome sempre que ele interage
            db[str_id]["nome"] = nome
            
        salvar_db(db)
    except: pass

def atualizar_campo(chat_id, campo, valor):
    try:
        db = carregar_db()
        str_id = str(chat_id)
        if str_id in db:
            db[str_id][campo] = valor
            salvar_db(db)
    except: pass

def verificar_permissao_msg(chat_id):
    db = carregar_db()
    return db.get(str(chat_id), {}).get("pode_mandar_msg", False)

def pegar_nome_cliente(chat_id):
    """Busca o nome salvo. Se der erro, retorna 'Amor'"""
    db = carregar_db()
    return db.get(str(chat_id), {}).get("nome", "Amor")

# --- SERVIDOR WEB ---
app = Flask('')
@app.route('/')
def home(): return "PrimeFlixx System Online"
def run_http(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_http).start()

logging.basicConfig(level=logging.INFO)

# --- VALIDAÇÃO DE PAGAMENTO ---
async def check_payment_loop(context: ContextTypes.DEFAULT_TYPE, chat_id, payment_id, message_id, tipo_compra='pack'):
    attempts = 0
    max_attempts = 90
    
    while attempts < max_attempts:
        try:
            info = sdk.payment().get(int(payment_id))
            status = info["response"]["status"]
            
            if status == 'approved':
                # Busca o nome atualizado do cliente para usar nas mensagens
                nome_cli = pegar_nome_cliente(chat_id)

                # ==========================================================
                # CENÁRIO 1: CLIENTE COMPROU O PACK
                # ==========================================================
                if tipo_compra == 'pack':
                    # 1. Avisa Aprovação
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id, 
                            message_id=message_id, 
                            text=f"✅ **PAGAMENTO APROVADO, {nome_cli}!**\n\nEnviando seu conteúdo agora...", 
                            parse_mode='Markdown'
                        )
                    except: pass

                    # 2. Entrega o Produto
                    legenda = f"📂 **Seu Pack Exclusivo, {nome_cli}!** Obrigada pela compra."
                    try:
                        if TIPO_PRODUTO == 'documento': await context.bot.send_document(chat_id, ID_PRODUTO, caption=legenda)
                        elif TIPO_PRODUTO == 'video': await context.bot.send_video(chat_id, ID_PRODUTO, caption=legenda)
                        else: await context.bot.send_photo(chat_id, ID_PRODUTO, caption=legenda)
                    except: pass
                    
                    atualizar_campo(chat_id, "status", "comprador")
                    
                    # 3. 🔥 UPSELL PESSOAL (MENSAGEM DE R$ 1,00)
                    texto_upsell = (
                        f"Oi {nome_cli}, vi que você adquiriu meu conteúdo! 🔥\n\n"
                        "Por apenas um valor simbólico, você pode me enviar seu comentário ou sugestão "
                        "para meus próximos vídeos ou fotos.\n\n"
                        "Bjs! 💋"
                    )
                    
                    kb_msg = [[InlineKeyboardButton(f"💌 Enviar Sugestão (R$ {VALOR_MENSAGEM})", callback_data='comprar_msg')]]
                    
                    await asyncio.sleep(2)
                    await context.bot.send_message(
                        chat_id,
                        texto_upsell,
                        reply_markup=InlineKeyboardMarkup(kb_msg),
                        parse_mode='Markdown'
                    )

                # ==========================================================
                # CENÁRIO 2: CLIENTE COMPROU A MENSAGEM VIP
                # ==========================================================
                elif tipo_compra == 'msg_vip':
                    try:
                        # Aqui usamos o nome do cliente corretamente na mensagem
                        await context.bot.edit_message_text(
                            chat_id=chat_id, 
                            message_id=message_id, 
                            text=f"✅ **CHAT VIP LIBERADO!**\n\n{nome_cli}, pode escrever sua mensagem ou sugestão abaixo que eu vou ler com carinho. 👇", 
                            parse_mode='Markdown'
                        )
                    except: pass
                    
                    atualizar_campo(chat_id, "pode_mandar_msg", True)

                return # Encerra o loop

            elif status in ['rejected', 'cancelled']:
                await context.bot.edit_message_text(chat_id, message_id, text="❌ Pagamento Cancelado.")
                return

            attempts += 1
            await asyncio.sleep(10)
            
        except: await asyncio.sleep(10)

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
                
                # Pega o nome para personalizar o marketing
                nome_cli = dados.get("nome", "Amor")

                # Dia 2
                if dias >= 1 and ultimo < 2 and ID_DIA_2:
                    try:
                        # Substitui {nome} pelo nome real na mensagem configurada
                        msg = TXT_DIA_2.replace("{nome}", nome_cli)
                        
                        try: await app_context.bot.send_photo(uid, ID_DIA_2, caption=msg)
                        except: await app_context.bot.send_video(uid, ID_DIA_2, caption=msg)
                        kb = [[InlineKeyboardButton("🔥 Quero Agora", callback_data='comprar')]]
                        await app_context.bot.send_message(uid, "Vem pro VIP! 👇", reply_markup=InlineKeyboardMarkup(kb))
                        db[uid]["funil_dia"] = 2
                        alteracoes = True
                    except: pass
                # Dia 3
                elif dias >= 2 and ultimo < 3 and ID_DIA_3:
                    try:
                        msg = TXT_DIA_3.replace("{nome}", nome_cli)
                        
                        try: await app_context.bot.send_photo(uid, ID_DIA_3, caption=msg)
                        except: await app_context.bot.send_video(uid, ID_DIA_3, caption=msg)
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
    user = update.effective_user
    user_name = user.first_name
    
    # Salva o nome imediatamente
    registrar_usuario(user.id, user_name)
    
    try:
        if TIPO_VITRINE == 'video': await context.bot.send_video(user.id, ID_VITRINE, caption="👀 Prévia...")
        else: await context.bot.send_photo(user.id, ID_VITRINE)
    except: pass
    
    texto = (
        f"Oi, {user_name}... Sabia que você viria. 😈\n\n"
        "O que você vê nas redes sociais é só 1% do que eu gravo.\n"
        "Aqui, a brincadeira é **sem cortes, sem tarjas e sem limites**.\n\n"
        "🔞 **O que te espera:**\n"
        "• Vídeos Completos em Full HD\n"
        "• Ângulos que nunca mostrei antes\n"
        "• Acesso Vitalício (Baixe e guarde)\n\n"
        "🔥 **Promoção Relâmpago**\n"
        f"👇 Garanta seu lugar: **R$ {VALOR_PRODUTO}**"
    )
    kb = [[InlineKeyboardButton("🔓 Quero Acesso Agora", callback_data='comprar')]]
    await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Atualiza o nome novamente ao clicar (garantia extra)
    registrar_usuario(update.effective_chat.id, update.effective_user.first_name)
    
    tipo = 'pack'
    valor = VALOR_PRODUTO
    desc = "Pack VIP"
    
    if query.data == 'comprar':
        tipo = 'pack'
        valor = VALOR_PRODUTO
    
    elif query.data == 'comprar_msg':
        tipo = 'msg_vip'
        valor = VALOR_MENSAGEM
        desc = "Mensagem Privada"

    msg = await query.edit_message_text(f"🔄 Gerando Pix para {desc}...")
    try:
        pay_data = {
            "transaction_amount": float(valor),
            "description": desc,
            "payment_method_id": "pix",
            "payer": {"email": "cliente@email.com", "first_name": "Cliente"}
        }
        res = sdk.payment().create(pay_data)["response"]
        pix = res['point_of_interaction']['transaction_data']['qr_code']
        pid = res['id']
        
        await context.bot.send_message(update.effective_chat.id, f"`{pix}`", parse_mode='Markdown')
        status_msg = await context.bot.send_message(update.effective_chat.id, "⏳ **Aguardando Pagamento...**\n_(Monitorando...)_", parse_mode='Markdown')
        
        asyncio.create_task(check_payment_loop(context, update.effective_chat.id, pid, status_msg.message_id, tipo_compra=tipo))
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Erro MP: {e}")

# --- RECEBER MENSAGEM PAGA ---
async def receber_mensagem_privada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and update.message.caption is None and update.message.text is None: return 
    user_id = update.effective_user.id
    if user_id == ADMIN_ID: return 

    if verificar_permissao_msg(user_id):
        nome = update.effective_user.first_name
        msg_cliente = update.message.text
        if not msg_cliente: msg_cliente = "Arquivo de Mídia"

        try:
            await context.bot.send_message(
                ADMIN_ID, 
                f"💌 **NOVA MENSAGEM PAGA (R$ {VALOR_MENSAGEM})**\n\n"
                f"👤 **De:** {nome} (ID: `{user_id}`)\n"
                f"💬 **Diz:** {msg_cliente}\n\n"
                "💡 _Para responder, mande mensagem no privado dele._",
                parse_mode='Markdown'
            )
            if update.message.photo or update.message.video or update.message.document:
                await update.message.forward(ADMIN_ID)

            await update.message.reply_text("✅ **Mensagem Enviada!**\nEu recebi aqui e vou ler com carinho. Obrigada!")
            atualizar_campo(user_id, "pode_mandar_msg", False)
        except:
            await update.message.reply_text("Erro ao enviar. Tente novamente.")
    else:
        pass

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
            nome_cli = db[uid].get("nome", "amor")
            txt_p = txt.replace("{nome}", nome_cli)
            try: await context.bot.send_photo(uid, midia, caption=txt_p)
            except: await context.bot.send_video(uid, midia, caption=txt_p)
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
    app_bot.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, receber_mensagem_privada))
    app_bot.add_handler(CommandHandler('aviso_geral', aviso_geral))
    app_bot.add_handler(CommandHandler('aviso_leads', aviso_leads))
    app_bot.add_handler(CommandHandler('aviso_clientes', aviso_clientes))
    
    print("Bot PrimeFlixx + VIP Chat Iniciado...")
    loop = asyncio.get_event_loop()
    loop.create_task(marketing_automacao_loop(app_bot))
    app_bot.run_polling()


