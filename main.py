# main.py
# Путь: /main.py
# Запуск: python3 main.py
import os
import io
import numpy as np
from PIL import Image, ImageChops, ImageStat, ExifTags
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# -------------------------
# Настройки из окружения
# -------------------------
# Поддерживаем оба имени переменной: TELEGRAM_TOKEN или BOT_TOKEN
TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
# WEBHOOK_BASE_URL должен быть типа: https://your-app.onrender.com
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE_URL")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("Установи TELEGRAM_TOKEN (или BOT_TOKEN) в окружении Render")
if not WEBHOOK_BASE:
    raise RuntimeError("Установи WEBHOOK_BASE_URL в окружении Render (например https://your-app.onrender.com)")

# ---------------------------------
# Forensic helper-методы (как было)
# ---------------------------------
def extract_exif(img):
    try:
        exif = img._getexif()
        if not exif:
            return "❌ EXIF отсутствует — частый признак AI."

        readable = {
            ExifTags.TAGS.get(tag, tag): val
            for tag, val in exif.items()
        }

        hints = []
        if "Software" in readable:
            sw = str(readable["Software"]).lower()
            if any(x in sw for x in ["ai", "stable", "diffusion", "midjourney"]):
                hints.append("⚠️ ПО изображения указывает на нейросеть.")

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

# ---------------------------------
# Handlers
# ---------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Inspector ADF.\n"
        "Отправь фото, и я выполню forensic-анализ."
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
    if "ai" in exif_res.lower():
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
        f"📉 Noise: {noise:.2f}\n"
        f"📊 ELA: {ela:.2f}\n\n"
        f"🔎 *Вердикт:* {verdict}"
    )

    await update.message.reply_text(result, parse_mode="Markdown")

# ---------------------------------
# Запуск через webhook
# ---------------------------------
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # путь вебхука используем как токен (уникально и безопасно)
    url_path = TOKEN
    webhook_url = f"{WEBHOOK_BASE}/{url_path}"

    print("Запускаем webhook...")
    print("WEBHOOK URL ->", webhook_url)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=url_path,
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
