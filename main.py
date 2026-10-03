"""
Bot de Telegram:
1. Recibes archivo(s) -> botones [Acumular otro archivo] [Confirmar]
2. Al confirmar, pide el nombre del archivo final
3. Luego permite reemplazar palabras/frases por "nada" (dejando un salto de línea
   en su lugar) tantas veces como quieras
4. Entrega el archivo final con cabecera + contenido + pie, y olvida todo
   (si vuelves a mandar un archivo, empieza de cero)

Requisitos:
    pip install "python-telegram-bot>=21,<22" --break-system-packages

Ejecutar:
    python3 bot.py
"""

import re
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ⚠️ IMPORTANTE: este token quedó expuesto en el chat. Te recomiendo
# regenerarlo en @BotFather (/mybots -> tu bot -> API Token -> Revoke)
# y luego reemplazar el valor de abajo (o mejor, leerlo de una variable
# de entorno) para que nadie más pueda controlar tu bot.
TOKEN = "8771496728:AAEEsxLBFj2zmh90RiBo8FvRf8rLe_PWQ6Q"

logging.basicConfig(level=logging.INFO)

# --- Cabecera / pie que se añade por defecto al archivo final ---------------
BLOQUE_PROMO = (
    "━━━━━━━━━━━━━━━━\n"
    "✨Share our channel for more exciting giveaways ✨\n"
    "https://t.me/+vlElCjzuOFY4MDEx ✔️ \n"
    "🚀 Thank you for staying with us\n"
    "━━━━━━━━━━━━━━━━\n"
    "✔️ Join the channel \"🌿 𝙼𝚊𝚔𝚒 𝙲𝚑𝚊𝚗𝚗𝚎𝚕 🌿\" for more content ✔️\n"
    "👇👇👇\n"
    "https://t.me/+vlElCjzuOFY4MDEx\n"
    "━━━━━━━━━━━━━━━━\n"
    "𝗜𝗻𝘃𝗶𝘁𝗲 𝗟𝗶𝗻𝗸 -\n"
    "━━━━━━━━━━━━━━━━\n"
    "https://t.me/+vlElCjzuOFY4MDEx 🔗"
)

# "Salta 3 espacios" entre bloque y contenido (ajusta aquí si quieres más/menos)
SALTO = "\n\n\n"

# Qué se pone en lugar de la palabra/frase eliminada: un salto de línea.
# Si en vez de salto de línea prefieres un espacio simple, cambia esto a " ".
RELLENO_AL_BORRAR = "\n"


def teclado_acumular_confirmar():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Acumular otro archivo", callback_data="acumular"),
                InlineKeyboardButton("✅ Confirmar", callback_data="confirmar"),
            ]
        ]
    )


def teclado_seguir_o_terminar():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔎 Buscar otra palabra", callback_data="seguir_reemplazando"),
                InlineKeyboardButton("🏁 Terminar", callback_data="terminar_reemplazos"),
            ]
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Mándame uno o varios archivos .txt y te dejo juntarlos, "
        "ponerles la cabecera/pie de siempre y reemplazar palabras por nada."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    etapa = context.chat_data.get("etapa")

    if etapa in ("nombre", "palabra", "decidir"):
        await update.message.reply_text(
            "⚠️ Ya estás en otro paso del proceso. Termínalo (o dale a Terminar) "
            "antes de mandar más archivos."
        )
        return

    doc = update.message.document
    archivo_tg = await doc.get_file()
    datos = await archivo_tg.download_as_bytearray()

    try:
        texto = bytes(datos).decode("utf-8")
    except UnicodeDecodeError:
        texto = bytes(datos).decode("latin-1", errors="ignore")

    context.chat_data.setdefault("archivos", []).append(texto)
    context.chat_data["etapa"] = "acumulando"

    n = len(context.chat_data["archivos"])
    await update.message.reply_text(
        f"📎 Archivo recibido. Llevas {n} archivo(s) acumulado(s).\n¿Qué quieres hacer?",
        reply_markup=teclado_acumular_confirmar(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "acumular":
        await query.edit_message_text("📥 Perfecto, mándame el siguiente archivo cuando quieras.")

    elif data == "confirmar":
        archivos = context.chat_data.get("archivos", [])
        if not archivos:
            await query.edit_message_text("⚠️ No has mandado ningún archivo todavía.")
            return
        context.chat_data["cuerpo"] = "\n".join(archivos)
        context.chat_data["etapa"] = "nombre"
        await query.edit_message_text("📝 ¿Cómo quieres llamar al archivo final? (sin extensión)")

    elif data == "seguir_reemplazando":
        context.chat_data["etapa"] = "palabra"
        await query.edit_message_text("🔎 Escribe la palabra o frase que quieres reemplazar por nada:")

    elif data == "terminar_reemplazos":
        await enviar_archivo_final(update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    etapa = context.chat_data.get("etapa")
    texto = update.message.text

    if etapa == "nombre":
        nombre = texto.strip()
        if not nombre:
            await update.message.reply_text("❌ Nombre inválido, intenta de nuevo:")
            return
        context.chat_data["nombre"] = nombre
        context.chat_data["etapa"] = "palabra"
        await update.message.reply_text(
            "🔎 Escribe una palabra o frase para reemplazar por nada "
            "(o escribe /listo si no quieres reemplazar nada):"
        )
        return

    if etapa == "palabra":
        if texto.strip().lower() in ("/listo", "listo", "no"):
            await enviar_archivo_final(update, context)
            return

        # Ojo: no hacemos .strip() a la palabra, así aceptas frases con
        # espacios al inicio/fin si de verdad las quieres buscar.
        palabra = texto
        cuerpo = context.chat_data.get("cuerpo", "")
        patron = re.escape(palabra)
        coincidencias = list(re.finditer(patron, cuerpo, flags=re.IGNORECASE))
        contador = len(coincidencias)

        if contador == 0:
            await update.message.reply_text(f"⚠️ No encontré '{palabra}' en el contenido.")
        else:
            partes = []
            ultimo_fin = 0
            for m in coincidencias:
                inicio, fin = m.start(), m.end()
                partes.append(cuerpo[ultimo_fin:inicio])
                partes.append(RELLENO_AL_BORRAR)
                ultimo_fin = fin
            partes.append(cuerpo[ultimo_fin:])
            context.chat_data["cuerpo"] = "".join(partes)
            await update.message.reply_text(
                f"✅ Reemplazadas {contador} ocurrencia(s) de '{palabra}' por nada."
            )

        context.chat_data["etapa"] = "decidir"
        await update.message.reply_text(
            "¿Quieres reemplazar algo más por nada?", reply_markup=teclado_seguir_o_terminar()
        )
        return

    # Si no está en ninguna etapa que espere texto, lo ignoramos.


async def enviar_archivo_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cuerpo = context.chat_data.get("cuerpo", "")
    nombre = context.chat_data.get("nombre", "archivo_final")

    contenido_final = BLOQUE_PROMO + SALTO + cuerpo + SALTO + BLOQUE_PROMO

    chat_id = update.effective_chat.id
    archivo_bytes = contenido_final.encode("utf-8")

    await context.bot.send_document(
        chat_id=chat_id,
        document=archivo_bytes,
        filename=f"{nombre}.txt",
        caption="✅ Aquí tienes tu archivo final.",
    )

    # Olvida todo para este chat: si mandas otro archivo, empieza de cero
    context.chat_data.clear()


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot corriendo...")
    app.run_polling()


if __name__ == "__main__":
    main()