import os
import io
import threading
import numpy as np
from flask import Flask
from PIL import Image, ImageChops, ImageStat, ExifTags
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# --------------------------
# Flask health-check server
# --------------------------

app_server = Flask(__name__)

@app_server.get("/")
def home():
    return "Inspector ADF is running!", 200


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_server.run(host="0.0.0.0", port=port)


# --------------------------
# Telegram Bot
# --------------------------

TOKEN = os.getenv("ВАШ_ТОКЕН")

def extract_exif(img):
    try:
        exif_data = img._getexif()
        if not exif_data:
            return "❌ EXIF отсутствует — часто признак AI."

        readable = {}
        for tag, value in exif_data.items():
            decoded = ExifTags.TAGS.get(tag, tag)
            readable[decoded] = value

        hints = []
        if "Software" in readable:
            sw = str(readable["Software"]).lower()
            if any(x in sw for x in ["midjourney", "diffusion", "ai", "stable", "generated"]):
                hints.append("⚠️ ПО указывает на генерацию нейросетью.")

        if not hints:
            hints.append("✔ EXIF выглядит естественно.")

        return "\n".join(hints) + "\n\n" + str(readable)
    except:
        return "❌ Ошибка чтения EXIF — файл модифицирован."


def error_level_analysis(img):
    temp = io.BytesIO()
    img.save(temp, "JPEG", quality=90)
    temp.seek(0)
    recompressed = Image.open(temp)
    diff = ImageChops.difference(img, recompressed)
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / len(stat.mean)


def noise_level(img):
    gray = img.convert("L")
    arr = np.array(gray)
    return float(np.std(arr))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Inspector ADF.\n"
        "Отправь фото — выполню forensic-анализ: EXIF, ELA, шумы.\n"
        "Определю вероятность AI-подделки."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Анализирую фото…")

    file = await update.message.photo[-1].get_file()
    data = await file.download_as_bytearray()
    img = Image.open(io.BytesIO(data)).convert("RGB")

    exif_res = extract_exif(img)
    noise = noise_level(img)
    ela = error_level_analysis(img)

    score = 0
    if "подозр" in exif_res.lower() or "ai" in exif_res.lower():
        score += 0.4
    if noise < 8:
        score += 0.3
    if ela > 20:
        score += 0.3

    if score < 0.3:
        verdict = "✔ Низкая вероятность AI."
    elif score < 0.6:
        verdict = "⚠️ Есть признаки AI."
    else:
        verdict = "❌ Высокая вероятность AI-генерации."

    result = (
        "🧾 *Inspector ADF — Forensic Report*\n\n"
        f"EXIF:\n{exif_res}\n\n"
        f"📉 Noise Level: {noise:.2f}\n"
        f"📊 ELA Score: {ela:.2f}\n\n"
        f"🔎 *Вердикт:* {verdict}"
    )

    await update.message.reply_text(result, parse_mode="Markdown")


def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.run_polling()


# --------------------------
# RUN BOTH SYSTEMS
# --------------------------

if __name__ == "__main__":
    # Flask server (health check)
    threading.Thread(target=run_flask).start()

    # Telegram bot polling
    run_bot()
