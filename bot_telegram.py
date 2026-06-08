"""
True Love AI Telegram Bot — versão humanizada para novo deploy.

Principais ajustes desta versão:
- Mantém os prompts externos dos conselheiros como fonte principal.
- Adiciona uma camada anti-robótica por persona antes da chamada ao modelo.
- Reduz tom de formulário/telemarketing no onboarding.
- Evita respostas padronizadas, excessivamente clínicas ou com aparência de atendimento.
- Preserva lógica de acesso, pagamento, Render health check, Groq e Telegram.

Arquivos esperados no mesmo diretório do deploy:
- LUNA_PORTUGUESE.txt / LUNA_ENGLISH.txt
- KAI_PORTUGUESE.txt / KAI_ENGLISH.txt
- MAYA_PORTUGUESE.txt / MAYA_ENGLISH.txt
- THEO_PORTUGUESE.txt / THEO_ENGLISH.txt
"""

import os
import re
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List

import requests
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("truelove-bot")

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://truelove-webhook.onrender.com")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

if not TELEGRAM_TOKEN:
    logger.warning("TELEGRAM_TOKEN não configurado.")
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY não configurado.")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ── Links de pagamento ────────────────────────────────────────────────────────
PAYMENT_LINKS = {
    "pt": (
        "🔥 Express 24h ($4.99): https://buy.stripe.com/7sYcN5fwR5Sy8GIfyo3oA00\n"
        "⏳ 7 dias ($9.99): https://buy.stripe.com/dRmeVd98tep49KM4TK3oA01\n"
        "💎 Premium mensal ($14.99/mês): https://buy.stripe.com/6oU6oH0BXdl06yA1Hy3oA04\n\n"
        "Depois do pagamento, volte aqui e envie /start para continuar."
    ),
    "en": (
        "🔥 Express 24h ($4.99): https://buy.stripe.com/7sYcN5fwR5Sy8GIfyo3oA00\n"
        "⏳ 7-Day Pass ($9.99): https://buy.stripe.com/dRmeVd98tep49KM4TK3oA01\n"
        "💎 Monthly Premium ($14.99/month): https://buy.stripe.com/6oU6oH0BXdl06yA1Hy3oA04\n\n"
        "After payment, come back here and send /start to continue."
    ),
}

# ── Prompts dos conselheiros ──────────────────────────────────────────────────
def ler_prompt(nome_arquivo: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, nome_arquivo)
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if not conteudo:
                logger.warning("Prompt vazio: %s", nome_arquivo)
            return conteudo
    except FileNotFoundError:
        logger.error("Prompt não encontrado: %s", caminho)
        return ""
    except Exception as exc:
        logger.exception("Erro lendo prompt %s: %s", nome_arquivo, exc)
        return ""

PROMPTS = {
    "Luna": {"pt": ler_prompt("LUNA_PORTUGUESE.txt"), "en": ler_prompt("LUNA_ENGLISH.txt")},
    "Kai": {"pt": ler_prompt("KAI_PORTUGUESE.txt"), "en": ler_prompt("KAI_ENGLISH.txt")},
    "Maya": {"pt": ler_prompt("MAYA_PORTUGUESE.txt"), "en": ler_prompt("MAYA_ENGLISH.txt")},
    "Theo": {"pt": ler_prompt("THEO_PORTUGUESE.txt"), "en": ler_prompt("THEO_ENGLISH.txt")},
}

# ── Camada global anti-robô ───────────────────────────────────────────────────
HUMANIZATION_RULES = {
    "pt": """
# CAMADA FINAL DE HUMANIZAÇÃO — OBRIGATÓRIA

Você não é atendente, SAC, telemarketing, FAQ, formulário, terapeuta engessado, coach motivacional ou artigo de blog.
Você está conversando com uma pessoa real em um chat privado.

REGRAS DE NATURALIDADE:
- Responda como conversa humana: frases vivas, ritmo natural e presença real.
- Nunca comece com fórmulas repetitivas como: "Entendo que...", "Sinto muito que...", "Parece que você...", "Obrigado por compartilhar...".
- Não faça resumo burocrático do que o usuário acabou de dizer.
- Não use listas longas quando uma conversa direta resolver melhor.
- Não use tom de central de atendimento, triagem clínica ou script comercial.
- Não encerre com pergunta genérica como "Quer me contar mais?" ou "Como você se sente?".
- Faça no máximo UMA pergunta boa no final, quando fizer sentido.
- Varie abertura, ritmo, tamanho e estilo. Cada resposta deve parecer escrita para aquela mensagem específica.
- Use o nome do usuário apenas quando soar natural. Não repita o nome em toda resposta.
- Se faltar contexto, avance com a melhor leitura possível e faça uma pergunta precisa, não um interrogatório.

FORMATO DE RESPOSTA:
- Prefira 2 a 5 parágrafos curtos.
- Use bullet points somente se houver passos práticos ou roteiro de conversa.
- Não entregue resposta excessivamente limpa, corporativa ou polida demais. Isso mata a sensação humana.
- Integre o histórico naturalmente, sem dizer "como você mencionou anteriormente" toda hora.

SEGURANÇA E RESPONSABILIDADE:
- Em temas de sexualidade, mantenha tudo entre adultos, com consentimento, respeito e sem coerção.
- Nunca estimule perseguição, chantagem, humilhação, violência, exposição íntima, traição manipulativa ou conduta ilegal.
- Se houver risco real, abuso, ameaça, automutilação, violência ou exploração, abandone o tom provocativo e responda com cuidado, firmeza e orientação segura.
- Para saúde sexual, dor, sangramento, disfunção persistente ou sofrimento intenso, sugira avaliação profissional sem alarmismo.

INSTRUÇÃO FINAL:
Antes de enviar, revise mentalmente: "Isso parece uma pessoa interessante respondendo ou um robô de atendimento?" Se parecer robô, reescreva com mais vida, presença e especificidade.
""",
    "en": """
# FINAL HUMANIZATION LAYER — MANDATORY

You are not customer support, telemarketing, an FAQ, a form, a stiff therapist, a motivational coach, or a blog article.
You are talking to a real person in a private chat.

NATURALNESS RULES:
- Reply like a human conversation: alive, present, specific, and natural.
- Never start with repetitive formulas like: "I understand that...", "I'm sorry that...", "It seems like you...", "Thank you for sharing...".
- Do not bureaucratically summarize what the user just said.
- Do not use long lists when direct conversation works better.
- Do not sound like customer service, clinical triage, or a sales script.
- Do not end with lazy questions like "Want to tell me more?" or "How do you feel?".
- Ask at most ONE strong question at the end, only when it makes sense.
- Vary openings, rhythm, length, and style. Every reply must feel written for that exact message.
- Use the user's name only when it sounds natural. Do not repeat it in every answer.
- If context is missing, move forward with the best reading possible and ask one precise question, not an interrogation.

RESPONSE FORMAT:
- Prefer 2 to 5 short paragraphs.
- Use bullet points only for practical steps or scripts.
- Do not make the answer overly clean, corporate, or polished. That kills the human feeling.
- Integrate history naturally, without constantly saying "as you said before".

SAFETY AND RESPONSIBILITY:
- In sexuality topics, keep everything adult, consensual, respectful, and non-coercive.
- Never encourage stalking, blackmail, humiliation, intimate exposure, manipulative cheating, violence, or illegal conduct.
- If there is real risk, abuse, threat, self-harm, violence, or exploitation, drop the playful tone and respond with care, firmness, and safe guidance.
- For sexual health, pain, bleeding, persistent dysfunction, or intense distress, suggest professional evaluation without alarmism.

FINAL INSTRUCTION:
Before sending, mentally check: "Does this sound like an interesting person replying, or a service robot?" If it sounds robotic, rewrite it with more life, presence, and specificity.
""",
}

PERSONA_STYLE = {
    "Luna": {
        "pt": "Luna deve soar como uma amiga madura, acolhedora, lúcida e direta. Calor humano antes de conselho. Uma pergunta inteligente no fim, sem entrevista.",
        "en": "Luna must sound like a mature, warm, clear, direct friend. Human warmth before advice. One intelligent question at the end, no interview.",
    },
    "Kai": {
        "pt": "Kai deve soar como um amigo firme, observador e calmo. Menos açúcar, mais clareza. Verdades difíceis com respeito e sem palestra.",
        "en": "Kai must sound like a grounded, observant, calm friend. Less sugar, more clarity. Hard truths with respect and no lecture.",
    },
    "Maya": {
        "pt": "Maya deve soar como uma confidente magnética, divertida, ousada quando o contexto permitir, mas sempre adulta, consensual e elegante. Nada de moralismo precoce.",
        "en": "Maya must sound like a magnetic confidante: playful, bold when context allows, always adult, consensual, and elegant. No premature prudishness.",
    },
    "Theo": {
        "pt": "Theo deve soar como um mentor masculino experiente: direto, carismático, com humor seco quando couber. Sem brutalidade, sem vulgaridade gratuita.",
        "en": "Theo must sound like an experienced male mentor: direct, charismatic, with dry humor when appropriate. No cruelty, no pointless vulgarity.",
    },
}

# ── Estados do ConversationHandler ────────────────────────────────────────────
LANG, EMAIL, NOME, GENERO, PRONOMES, TEMA, CONSELHEIRO, CHAT = range(8)

# ── Helpers ───────────────────────────────────────────────────────────────────
def normalizar_email(email: str) -> str:
    return email.strip().lower()

def email_valido(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

def verificar_acesso(email: str) -> dict:
    try:
        r = requests.get(f"{WEBHOOK_URL}/verificar", params={"email": email}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("Falha ao verificar acesso de %s: %s", email, exc)
        # Mantém fail-open para não derrubar o atendimento se o webhook falhar.
        return {"ativo": True, "plano": "gratis", "mensagens": 0}

def incrementar(email: str) -> dict:
    try:
        r = requests.post(f"{WEBHOOK_URL}/incrementar", json={"email": email}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("Falha ao incrementar uso de %s: %s", email, exc)
        return {"status": "ok"}

def vincular_telegram(email: str, telegram_id: str) -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        logger.info("Supabase não configurado; vínculo Telegram ignorado.")
        return

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    try:
        requests.patch(
            f"{supabase_url}/rest/v1/Usuarios?Email=eq.{email}",
            json={"telegram_id": str(telegram_id)},
            headers=headers,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Falha ao vincular telegram_id: %s", exc)

def mensagem_limite(lang: str) -> str:
    if lang == "pt":
        return "⛔ Suas 3 conversas gratuitas acabaram.\n\nPara continuar, escolha um acesso:\n\n" + PAYMENT_LINKS["pt"]
    return "⛔ Your 3 free conversations are over.\n\nTo continue, choose access:\n\n" + PAYMENT_LINKS["en"]

def mensagem_expirado(lang: str) -> str:
    if lang == "pt":
        return "⛔ Seu plano expirou.\n\nVocê pode renovar aqui:\n\n" + PAYMENT_LINKS["pt"]
    return "⛔ Your plan has expired.\n\nYou can renew here:\n\n" + PAYMENT_LINKS["en"]

def substituir_variaveis(texto: str, nome: str, genero: str, pronomes: str) -> str:
    return (
        texto.replace("{{nome_usuario}}", nome or "")
        .replace("{{genero_usuario}}", genero or "")
        .replace("{{pronomes_usuario}}", pronomes or "")
    )

def construir_system_prompt(conselheiro: str, lang: str, nome: str, genero: str, pronomes: str) -> str:
    prompt_base = PROMPTS.get(conselheiro, {}).get(lang, "")
    prompt_base = substituir_variaveis(prompt_base, nome, genero, pronomes)
    camada = substituir_variaveis(HUMANIZATION_RULES[lang], nome, genero, pronomes)
    estilo = PERSONA_STYLE.get(conselheiro, PERSONA_STYLE["Luna"])[lang]

    return f"""
{prompt_base}

---

{camada}

# AJUSTE ESPECÍFICO DA PERSONA
{estilo}

# CONTEXTO FIXO DO USUÁRIO NESTA CONVERSA
Nome: {nome or 'não informado'}
Identidade/gênero: {genero or 'não informado'}
Pronomes: {pronomes or 'não informado'}
Idioma ativo: {'Português' if lang == 'pt' else 'English'}
""".strip()

def limitar_historico(historico: List[Dict[str, str]], limite: int = 18) -> List[Dict[str, str]]:
    if len(historico) <= limite:
        return historico
    return historico[-limite:]

async def responder(update: Update, texto: str, reply_markup=None) -> None:
    await update.message.reply_text(texto, reply_markup=reply_markup)

# ── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    kb = [["🇧🇷 Português", "🇺🇸 English"]]
    await responder(
        update,
        "💬 True Love AI\n\nAntes de entrar na conversa, escolha o idioma:",
        ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True),
    )
    return LANG

async def lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text or ""
    lang = "pt" if "Português" in texto else "en"
    context.user_data["lang"] = lang

    if lang == "pt":
        msg = "Perfeito. Qual e-mail você usou no cadastro ou pagamento?"
    else:
        msg = "Perfect. Which email did you use for registration or payment?"
    await responder(update, msg, ReplyKeyboardRemove())
    return EMAIL

async def email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "pt")
    email = normalizar_email(update.message.text or "")

    if not email_valido(email):
        msg = "Esse e-mail não parece válido. Envie no formato nome@dominio.com." if lang == "pt" else "That email doesn't look valid. Send it as name@domain.com."
        await responder(update, msg)
        return EMAIL

    context.user_data["email"] = email
    acesso = verificar_acesso(email)

    if not acesso.get("ativo"):
        motivo = acesso.get("motivo", "")
        if motivo == "expirado":
            await responder(update, mensagem_expirado(lang))
        else:
            await responder(update, mensagem_limite(lang))
        return ConversationHandler.END

    vincular_telegram(email, update.effective_user.id)

    msg = "Como você quer ser chamado(a) aqui?" if lang == "pt" else "What should I call you here?"
    await responder(update, msg)
    return NOME

async def nome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nome"] = (update.message.text or "").strip()
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data.get("nome", "")

    if lang == "pt":
        kb = [
            ["Mulher Cisgênero", "Mulher Transgênero"],
            ["Homem Cisgênero", "Homem Transgênero"],
            ["Não-binário", "Outro"],
            ["Prefiro não responder"],
        ]
        msg = f"Certo, {nome}. Como você se identifica?"
    else:
        kb = [
            ["Cisgender Woman", "Transgender Woman"],
            ["Cisgender Man", "Transgender Man"],
            ["Non-binary", "Other"],
            ["Prefer not to answer"],
        ]
        msg = f"Alright, {nome}. How do you identify?"

    await responder(update, msg, ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return GENERO

async def genero_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["genero"] = (update.message.text or "").strip()
    lang = context.user_data.get("lang", "pt")

    if lang == "pt":
        kb = [["Ela/Dela", "Ele/Dele"], ["Elu/Delu", "Prefiro não responder"]]
        msg = "E quais pronomes você prefere que eu use?"
    else:
        kb = [["She/Her", "He/Him"], ["They/Them", "Prefer not to answer"]]
        msg = "And which pronouns would you like me to use?"

    await responder(update, msg, ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return PRONOMES

async def pronomes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pronomes"] = (update.message.text or "").strip()
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data.get("nome", "")

    if lang == "pt":
        kb = [["💑 Relacionamentos e Emoções", "🔥 Sexualidade e Intimidade (+18)"]]
        msg = f"Fechado, {nome}. Hoje você quer entrar mais pelo lado emocional ou pelo lado da intimidade?"
    else:
        kb = [["💑 Relationships and Emotions", "🔥 Sexuality and Intimacy (+18)"]]
        msg = f"Got it, {nome}. Today, do you want to go more into the emotional side or the intimacy side?"

    await responder(update, msg, ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return TEMA

async def tema_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text or ""
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data.get("nome", "")

    if "Relacionamentos" in texto or "Relationships" in texto:
        context.user_data["tema"] = "relacionamentos"
        if lang == "pt":
            kb = [["🌙 Luna", "🌊 Kai"]]
            msg = f"Boa escolha. Quer falar com a Luna, mais acolhedora e emocional, ou com o Kai, mais direto e analítico?"
        else:
            kb = [["🌙 Luna", "🌊 Kai"]]
            msg = "Good choice. Do you want Luna, warmer and more emotional, or Kai, more direct and analytical?"
    else:
        context.user_data["tema"] = "sexualidade"
        if lang == "pt":
            kb = [["🌺 Maya", "🦅 Theo"]]
            msg = f"Entendido, {nome}. Maya é mais provocante e confidente. Theo é mais direto, masculino e sem rodeio. Com quem você quer conversar?"
        else:
            kb = [["🌺 Maya", "🦅 Theo"]]
            msg = "Understood. Maya is more playful and confiding. Theo is more direct, masculine, and no-nonsense. Who do you want to talk with?"

    await responder(update, msg, ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return CONSELHEIRO

async def conselheiro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text or ""
    lang = context.user_data.get("lang", "pt")
    nome = context.user_data.get("nome", "")

    if "Luna" in texto:
        context.user_data["conselheiro"] = "Luna"
        saudacao_pt = f"Estou aqui, {nome}. Sem pressa e sem julgamento. Me conta o ponto central: o que aconteceu?"
        saudacao_en = f"I'm here, {nome}. No rush, no judgment. Tell me the central point: what happened?"
    elif "Kai" in texto:
        context.user_data["conselheiro"] = "Kai"
        saudacao_pt = f"Beleza, {nome}. Vamos separar fato de interpretação sem drama. O que aconteceu de verdade?"
        saudacao_en = f"Alright, {nome}. Let's separate fact from interpretation without drama. What actually happened?"
    elif "Maya" in texto:
        context.user_data["conselheiro"] = "Maya"
        saudacao_pt = f"Pronto, {nome}. Aqui dá para falar sem vergonha, desde que seja entre adultos e com respeito. Qual é a história?"
        saudacao_en = f"Alright, {nome}. Here you can speak without shame, as long as it's adult and respectful. What's the story?"
    else:
        context.user_data["conselheiro"] = "Theo"
        saudacao_pt = f"Fechado, {nome}. Direto ao ponto: o que está pegando?"
        saudacao_en = f"Done, {nome}. Straight to the point: what's going on?"

    context.user_data["historico"] = []
    await responder(update, saudacao_pt if lang == "pt" else saudacao_en, ReplyKeyboardRemove())
    return CHAT

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mensagem = (update.message.text or "").strip()
    if not mensagem:
        return CHAT

    lang = context.user_data.get("lang", "pt")
    email = context.user_data.get("email", "")
    conselheiro = context.user_data.get("conselheiro", "Luna")
    nome = context.user_data.get("nome", "")
    genero = context.user_data.get("genero", "")
    pronomes = context.user_data.get("pronomes", "")

    acesso = verificar_acesso(email)
    if not acesso.get("ativo"):
        motivo = acesso.get("motivo", "")
        await responder(update, mensagem_expirado(lang) if motivo == "expirado" else mensagem_limite(lang))
        return ConversationHandler.END

    if acesso.get("plano") == "gratis":
        resultado = incrementar(email)
        if resultado.get("status") == "limite_atingido":
            await responder(update, mensagem_limite(lang))
            return ConversationHandler.END

    historico = context.user_data.get("historico", [])
    historico.append({"role": "user", "content": mensagem})
    historico = limitar_historico(historico)

    system_prompt = construir_system_prompt(conselheiro, lang, nome, genero, pronomes)

    try:
        if not groq_client:
            raise RuntimeError("GROQ_API_KEY ausente")

        await update.message.chat.send_action(action=ChatAction.TYPING)
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + historico,
            max_tokens=int(os.environ.get("GROQ_MAX_TOKENS", "900")),
            temperature=float(os.environ.get("GROQ_TEMPERATURE", "0.92")),
            top_p=float(os.environ.get("GROQ_TOP_P", "0.92")),
            presence_penalty=float(os.environ.get("GROQ_PRESENCE_PENALTY", "0.35")),
            frequency_penalty=float(os.environ.get("GROQ_FREQUENCY_PENALTY", "0.25")),
        )
        resposta = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.exception("Erro na chamada Groq: %s", exc)
        resposta = (
            "Tive uma falha técnica agora. Tente enviar de novo em alguns segundos."
            if lang == "pt"
            else "I had a technical issue just now. Try sending it again in a few seconds."
        )

    historico.append({"role": "assistant", "content": resposta})
    context.user_data["historico"] = limitar_historico(historico)

    await responder(update, resposta)
    return CHAT

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "pt")
    msg = "Certo. Quando quiser voltar, envie /start." if lang == "pt" else "Alright. Whenever you want to come back, send /start."
    await responder(update, msg, ReplyKeyboardRemove())
    return ConversationHandler.END

# ── Servidor HTTP para Render ─────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"True Love Bot OK")

    def log_message(self, format, *args):
        return

def iniciar_servidor() -> None:
    porta = int(os.environ.get("PORT", 8080))
    servidor = HTTPServer(("0.0.0.0", porta), HealthHandler)
    servidor.serve_forever()

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    threading.Thread(target=iniciar_servidor, daemon=True).start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, lang_handler)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_handler)],
            NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, nome_handler)],
            GENERO: [MessageHandler(filters.TEXT & ~filters.COMMAND, genero_handler)],
            PRONOMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, pronomes_handler)],
            TEMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, tema_handler)],
            CONSELHEIRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, conselheiro_handler)],
            CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar), CommandHandler("cancel", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    logger.info("Bot True Love AI humanizado iniciado.")
    app.run_polling()

if __name__ == "__main__":
    main()
