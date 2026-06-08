# ── Servidor de Health Check Assíncrono ───────────────────────────────────────
import asyncio
from aiohttp import web

async def health_check(request):
    return web.Response(text="True Love Bot OK")

# ── Inicialização Unificada (Fluxo Único Sem Threads) ─────────────────────────
async def iniciar_tudo():
    # 1. Configura e prepara o Bot do Telegram
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

    # 2. Configura o Servidor Web de Health Check na mesma malha
    web_app = web.Application()
    web_app.router.add_get("/", health_check)
    
    porta = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", porta)
    
    # Liga o servidor HTTP
    await site.start()
    print(f"Servidor de Health Check ativo na porta {porta}")

    # 3. Inicia o Bot do Telegram dentro do mesmo loop assíncrono
    # Isso garante que ele escute as mensagens instantaneamente
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    print("Bot True Love AI totalmente iniciado e ouvindo.")

    # Mantém o loop rodando por tempo indeterminado
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("Encerrando serviços...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()

def main():
    try:
        asyncio.run(iniciar_tudo())
    except Exception as e:
        logger.error(f"Erro crítico na execução principal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
