import discord
from discord.ext import commands
import asyncio
import os
import logging
from dotenv import load_dotenv
from database import DatabaseManager
from utils import EncryptionManager
from commands import CommandHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

db_manager = None
encryption_manager = None
command_handler = None


@bot.event
async def on_ready():
    global db_manager, encryption_manager, command_handler

    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")

    try:
        # Initialize database connection pool
        db_manager = DatabaseManager()
        await db_manager.initialize()
        logger.info("Database connection pool initialized")

        # Initialize encryption manager
        encryption_manager = EncryptionManager()
        if not encryption_manager.validate_key():
            logger.error("Invalid encryption key")
            raise ValueError("Invalid encryption key")
        logger.info("Encryption manager initialized")

        # Initialize command handler
        command_handler = CommandHandler(bot, db_manager, encryption_manager)
        logger.info("Command handler initialized")

        logger.info("Bot is ready and all systems initialized!")

    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        raise


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Process commands through command handler
    if command_handler:
        await command_handler.handle_message(message)

    # Also process through bot for other commands
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument. Use `!help` for usage.")
    elif isinstance(error, discord.Forbidden):
        logger.warning(f"Permission denied for user {ctx.author.id}: {error}")
        await ctx.send("❌ I don't have permission to do that.")
    elif isinstance(error, discord.HTTPException):
        logger.error(f"Discord API error: {error}")
        await ctx.send("❌ A Discord API error occurred. Please try again.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send("❌ An error occurred while processing your command.")


if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN environment variable is required")
        exit(1)

    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)
