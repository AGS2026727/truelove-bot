import os
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from groq import Groq

# ── Variáveis de ambiente ──────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY")
WEBHOOK_URL     = os.environ.get("WEBHOOK_URL", "https://truelove-webhook.onrender.com")
GROQ_MODEL      = "llama-3.3-70b-versatile"

groq_client = Groq(api_key=GROQ_API_KEY)

# ── Links de pagamento ─────────────────────────────────────────────────────────
PAYMENT_LINKS = {
    "pt": (
        "🔥 Express 24h ($4.99): https://buy.stripe.com/7sYcN5fwR5Sy8GIfyo3oA00\n"
        "⏳ 7 dias ($9.99): https://buy.stripe.com/dRmeVd98tep49KM4TK3oA01\n"
        "💎 Premium mensal ($14.99/mês): https://buy.stripe.com/6oU6oH0BXdl06yA1Hy3oA04\n\n"
        "Após o pagamento, volte aqui e envie /start para continuar."
    ),
    "en": (
        "🔥 Express 24h ($4.99): https://buy.stripe.com/7sYcN5fwR5Sy8GIfyo3oA00\n"
        "⏳ 7-Day Pass ($9.99): https://buy.stripe.com/dRmeVd98tep49KM4TK3oA01\n"
        "💎 Monthly Premium ($14.99/month): https://buy.stripe.com/6oU6oH0BXdl06yA1Hy3oA04\n\n"
        "After payment, come back here and send /start to continue."
    ),
}

# ── Prompts dos conselheiros ───────────────────────────────────────────────────
def ler_prompt(nome_arquivo: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, nome_arquivo)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read()
    return ""

PROMPTS = {
    "Luna": {
        "pt": ler_prompt("LUNA_PORTUGUESE.txt"),
        "en": ler_prompt("LUNA_ENGLISH.txt"),
    },
    "Kai": {
        "pt": ler_prompt("KAI_PORTUGUESE.txt"),
        "en": ler_prompt("KAI_ENGLISH.txt"),
    },
    "Maya": {
        "pt": ler_prompt("MAYA_PORTUGUESE.txt"),
        "en": ler_prompt("MAYA_ENGLISH.txt"),
    },
    "Theo": {
        "pt": ler_prompt("THEO_PORTUGUESE.txt"),
        "en": ler_prompt("THEO_ENGLISH.txt"),
    },
}

# ── Estados do ConversationHandler ────────────────────────────────────────────
(
    LANG, EMAIL, VERIFICAR, NOME, GENERO, PRONOMES,
    TEMA, CONSELHEIRO, CHAT
) = range(9)

# ── Helpers ────────────────────────────────────────────────────────────────────
def verificar_acesso(email: str) -> dict:
    try:
        r = requests.get(f"{WEBHOOK_URL}/verificar", params={"email": email}, timeout=30)
        return r.json()
    except Exception:
        return {"ativo": True, "plano": "gratis", "mensagens": 0}

def incrementar(email: str) -> dict:
    try:
        r = requests.post(f"{WEBHOOK_URL}/incrementar", json={"email": email}, timeout=30)
        return r.json()
    except Exception:
        return {"status": "ok"}

def vincular_telegram(email: str, telegram_id: str):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    requests.patch(
        f"{supabase_url}/rest/v1/Usuarios?Email=eq.{email}",
        json={"telegram_id": str(telegram_id)},
        headers=headers,
        timeout=10
    )

def mensagem_limite(lang: str) -> str:
    if lang == "pt":
        return (
            "⛔ Você usou suas 3 conversas gratuitas.\n\n"
            "Para continuar com acesso ilimitado, escolha um plano:\n\n"
            + PAYMENT_LINKS["pt"]
        )
    return (
        "⛔ You have used your 3 free conversations.\n\n"
        "To continue with unlimited access, choose a plan:\n\n"
        + PAYMENT_LINKS["en"]
    )

def mensagem_expirado(lang: str) -> str:
    if lang == "pt":
        return (
            "⛔ Seu plano expirou.\n\n"
            "Renove seu acesso:\n\n"
            + PAYMENT_LINKS["pt"]
        )
    return (
        "⛔ Your plan has expired.\n\n"
        "Renew your access:\n\n"
        + PAYMENT_LINKS["en"]
    )

def construir_system_prompt(conselheiro: str, lang: str, nome: str, genero: str, pronomes: str) -> str:
    prompt = PROMPTS[conselheiro][lang]
    prompt = prompt.replace("{{nome_usuario}}", nome)
    prompt = prompt.replace("{{genero_usuario}}", genero)
    prompt = prompt.replace("{{pronomes_usuario}}", pronomes)
    return prompt

# ── Handlers ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    kb = [["🇧🇷 Português", "🇺🇸 English"]]
    await update.message.reply_text(
        "💬 True Love AI\n\nEscolha seu idioma / Choose your language:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return LANG

async def lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text
    if "Português" in texto:
        context.user_data["lang"] = "pt"
        await update.message.reply_text(
            "Para começar, qual é o seu e-mail?\n(O mesmo usado no cadastro ou no pagamento)",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        context.user_data["lang"] = "en"
        await update.message.reply_text(
            "To get started, what is your email?\n(The same one used for registration or payment)",
            reply_markup=ReplyKeyboardRemove()
        )
    return EMAIL

async def email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip().lower()
    lang = context.user_data.get("lang", "pt")
    context.user_data["email"] = email

    acesso = verificar_acesso(email)

    if not acesso.get("ativo"):
        motivo = acesso.get("motivo", "")
        if motivo == "expirado":
            await update.message.reply_text(mensagem_expirado(lang))
        elif motivo == "limite gratis atingido":
            await update.message.reply_text(mensagem_limite(lang))
        else:
            # Novo usuário: tem 3 mensagens grátis
            pass

    # Vincula telegram_id ao email
    vincular_telegram(email, update.effective_user.id)

    # Segue para onboarding
    if lang == "pt":
        await update.message.reply_text("Como você se chama?")
    else:
        await update.message.reply_text("What is your name?")
    return NOME

async def nome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nome"] = update.message.text.strip()
    lang = context.user_data.get("lang", "pt")

    if lang == "pt":
        kb = [
            ["Mulher Cisgênero", "Mulher Transgênero"],
            ["Homem Cisgênero", "Homem Transgênero"],
            ["Não-binário", "Outro"],
            ["Prefiro não responder"]
        ]
        await update.message.reply_text(
            f"Como você se identifica, {context.user_data['nome']}?",
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        kb = [
            ["Cisgender Woman", "Transgender Woman"],
            ["Cisgender Man", "Transgender Man"],
            ["Non-binary", "Other"],
            ["Prefer not to answer"]
        ]
        await update.message.reply_text(
            f"How do you identify, {context.user_data['nome']}?",
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
    return GENERO

async def genero_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["genero"] = update.message.text.strip()
    lang = context.user_data.get("lang", "pt")

    if lang == "pt":
        kb = [["Ela/Dela", "Ele/Dele"], ["Elu/Delu", "Prefiro não responder"]]
        await update.message.reply_text(
            "Quais pronomes você usa?",
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        kb = [["She/Her", "He/Him"], ["They/Them", "Prefer not to answer"]]
        await update.message.reply_text(
            "What pronouns do you use?",
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
    return PRONOMES

async def pronomes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pronomes"] = update.message.text.strip()
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data["nome"]

    if lang == "pt":
        kb = [["💑 Relacionamentos e Emoções", "🔥 Sexualidade e Intimidade (+18)"]]
        await update.message.reply_text(
            f"O True Love respeita quem você é, {nome}.\n\nSobre o que você quer conversar hoje?",
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        kb = [["💑 Relationships and Emotions", "🔥 Sexuality and Intimacy (+18)"]]
        await update.message.reply_text(
            f"True Love respects who you are, {nome}.\n\nWhat would you like to talk about today?",
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
    return TEMA

async def tema_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data["nome"]

    if "Relacionamentos" in texto or "Relationships" in texto:
        context.user_data["tema"] = "relacionamentos"
        if lang == "pt":
            kb = [["🌙 Luna (conselheira)", "🌊 Kai (conselheiro)"]]
            await update.message.reply_text(
                f"Com quem você prefere conversar, {nome}?",
                reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
            )
        else:
            kb = [["🌙 Luna (counselor)", "🌊 Kai (counselor)"]]
            await update.message.reply_text(
                f"Who would you prefer to talk with, {nome}?",
                reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
            )
    else:
        context.user_data["tema"] = "sexualidade"
        if lang == "pt":
            kb = [["🌺 Maya (conselheira)", "🦅 Theo (conselheiro)"]]
            await update.message.reply_text(
                f"Com quem você prefere conversar sobre sexualidade, {nome}?",
                reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
            )
        else:
            kb = [["🌺 Maya (counselor)", "🦅 Theo (counselor)"]]
            await update.message.reply_text(
                f"Who would you prefer to talk with about sexuality, {nome}?",
                reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
            )
    return CONSELHEIRO

async def conselheiro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data["nome"]

    if "Luna" in texto:
        context.user_data["conselheiro"] = "Luna"
        saudacao_pt = f"{nome}, que bom que você veio. Sou a Luna. Pode chegar do jeito que estiver, bagunçado, confuso, com raiva ou sem saber nem por onde começar, aqui não tem julgamento. O que está pesando?"
        saudacao_en = f"{nome}, so good to see you here. I'm Luna. Come as you are, messy, confused, angry or not even knowing where to start, no judgment here. What's weighing on you?"
    elif "Kai" in texto:
        context.user_data["conselheiro"] = "Kai"
        saudacao_pt = f"E aí {nome}. Sou o Kai. Pode falar o que quiser, do jeito que sair, sem filtro, sem julgamento. O que está acontecendo?"
        saudacao_en = f"Hey {nome}. I'm Kai. Say whatever you want, however it comes out, no filter, no judgment. What's going on?"
    elif "Maya" in texto:
        context.user_data["conselheiro"] = "Maya"
        saudacao_pt = f"{nome}, que bom te ver por aqui. Sou a Maya. Pode chegar sem filtro, sem ensaio e sem vergonha. O que está passando pela sua cabeça agora?"
        saudacao_en = f"{nome}, so good to see you here. I'm Maya. Come without a filter, no rehearsal, no shame. What's going through your head right now?"
    else:
        context.user_data["conselheiro"] = "Theo"
        saudacao_pt = f"{nome}, sou o Theo. Aqui você fala o que quiser, do jeito que sair. Sem enrolação, sem julgamento. O que está na sua cabeça?"
        saudacao_en = f"{nome}, I'm Theo. Here you say whatever you want, however it comes out. No nonsense, no judgment. What's on your mind?"

    context.user_data["historico"] = []

    saudacao = saudacao_pt if lang == "pt" else saudacao_en
    await update.message.reply_text(saudacao, reply_markup=ReplyKeyboardRemove())
    return CHAT

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mensagem = update.message.text
    lang = context.user_data.get("lang", "pt")
    email = context.user_data.get("email", "")
    conselheiro = context.user_data.get("conselheiro", "Luna")
    nome = context.user_data.get("nome", "")
    genero = context.user_data.get("genero", "")
    pronomes = context.user_data.get("pronomes", "")

    # Verificar acesso antes de cada resposta
    acesso = verificar_acesso(email)

    if not acesso.get("ativo"):
        motivo = acesso.get("motivo", "")
        if motivo == "expirado":
            await update.message.reply_text(mensagem_expirado(lang))
        else:
            await update.message.reply_text(mensagem_limite(lang))
        return ConversationHandler.END

    # Incrementar contador (só para usuários gratuitos)
    if acesso.get("plano") == "gratis":
        resultado = incrementar(email)
        if resultado.get("status") == "limite_atingido":
            await update.message.reply_text(mensagem_limite(lang))
            return ConversationHandler.END

    # Construir histórico
    historico = context.user_data.get("historico", [])
    historico.append({"role": "user", "content": mensagem})

    # Chamar Groq
    system_prompt = construir_system_prompt(conselheiro, lang, nome, genero, pronomes)

    try:
        await update.message.chat.send_action("typing")
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + historico,
            max_tokens=1024,
            temperature=0.85,
        )
        resposta = response.choices[0].message.content
    except Exception as e:
        if lang == "pt":
            resposta = "Desculpe, tive um problema técnico. Tente novamente em instantes."
        else:
            resposta = "Sorry, I had a technical issue. Please try again in a moment."

    historico.append({"role": "assistant", "content": resposta})

    # Limitar histórico a 20 mensagens para não estourar contexto
    if len(historico) > 20:
        historico = historico[-20:]
    context.user_data["historico"] = historico

    await update.message.reply_text(resposta)
    return CHAT

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "pt")
    msg = "Até logo! Quando quiser, é só enviar /start." if lang == "pt" else "See you! Whenever you're ready, just send /start."
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ── Servidor HTTP para manter o Render acordado ────────────────────────────────
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"True Love Bot OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args):
        pass

def iniciar_servidor():
    porta = int(os.environ.get("PORT", 8080))
    servidor = HTTPServer(("0.0.0.0", porta), HealthHandler)
    servidor.serve_forever()

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    # Inicia servidor HTTP em thread separada
    t = threading.Thread(target=iniciar_servidor, daemon=True)
    t.start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG:        [MessageHandler(filters.TEXT & ~filters.COMMAND, lang_handler)],
            EMAIL:       [MessageHandler(filters.TEXT & ~filters.COMMAND, email_handler)],
            NOME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, nome_handler)],
            GENERO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, genero_handler)],
            PRONOMES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, pronomes_handler)],
            TEMA:        [MessageHandler(filters.TEXT & ~filters.COMMAND, tema_handler)],
            CONSELHEIRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, conselheiro_handler)],
            CHAT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar), CommandHandler("cancel", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    print("Bot True Love AI iniciado.")
    app.run_polling()

if __name__ == "__main__":
    main()
