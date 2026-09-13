from dotenv import load_dotenv

load_dotenv()

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from LLM import process_location_setup, process_text_message
from stt import stt
from tts import tts
from teleToken import TOKEN
import os
from uuid import uuid4


# Run when /start is sent
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! Use /location to share your location, then /weather to get the weather."
    )


async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /location command - request user's location."""
    await update.message.reply_text(
        "Please share your location.",
        reply_markup=__import__('telegram').ReplyKeyboardMarkup(
            [[__import__('telegram').KeyboardButton(text="📍 Share Location", request_location=True)]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )


# User location sharing logic
async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    location = update.message.location
    latitude = location.latitude
    longitude = location.longitude

    # Save it to persistent context.user_data storage
    context.user_data["location"] = {
        "latitude": latitude,
        "longitude": longitude,
    }
    
    await update.message.reply_text(
        process_location_setup(latitude, longitude, str(update.effective_user.id))
    )


async def get_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Transcribe a voice message and answer its weather request."""
    voice = update.message.voice
    telegram_file = await context.bot.get_file(voice.file_id)
    input_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Telegram_input_audio_files")
    os.makedirs(input_dir, exist_ok=True)
    audio_path = os.path.join(input_dir, f"{voice.file_unique_id}.ogg")

    await telegram_file.download_to_drive(audio_path)
    try:
        user_input = stt(audio_path)
        response = process_text_message(
            user_input,
            str(update.effective_user.id),
            context.user_data.get("location"),
        )
        await update.message.reply_text(response)

        response_audio_path = tts(
            response,
            lang="hi-IN",
            filename=f"voice_response_{uuid4().hex}.wav",
        )
        try:
            with open(response_audio_path, "rb") as audio_file:
                await update.message.reply_voice(voice=audio_file)
        finally:
            os.remove(response_audio_path)
    finally:
        os.remove(audio_path)


async def get_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer a text weather request with text and synthesized voice."""
    response = process_text_message(
        update.message.text,
        str(update.effective_user.id),
        context.user_data.get("location"),
    )
    await update.message.reply_text(f"TRANSCRIPT: {response}")

    response_audio_path = tts(
        response,
        lang="hi-IN",
        filename=f"text_response_{uuid4().hex}.wav",
    )
    try:
        with open(response_audio_path, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)
    finally:
        os.remove(response_audio_path)


# Send out weather info for given location
async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    location = context.user_data.get("location")
    if not location:
        await update.message.reply_text("Please use /location and share your location first.")
        return

    response = process_text_message(
        "What is the weather at my saved location?",
        str(update.effective_user.id),
        location,
    )
    audio_path = tts(response, lang="hi-IN")
    try:
        with open(audio_path, "rb") as audio_file:
            await update.message.reply_audio(audio=audio_file)
    finally:
        os.remove(audio_path)


async def post_init(application: Application) -> None:
    """Set bot commands that appear in the / menu."""
    commands = [
        BotCommand("start", "Show bot introduction"),
        BotCommand("location", "Share your location and get coordinates"),
        BotCommand("weather", "Get weather at your shared location"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Start the bot."""
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    application.post_init = post_init

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("location", location_command))
    application.add_handler(CommandHandler("weather", weather_command))
    
    # Register message handlers
    application.add_handler(MessageHandler(filters.LOCATION, get_location))
    application.add_handler(MessageHandler(filters.VOICE, get_voice_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_text_message))

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()