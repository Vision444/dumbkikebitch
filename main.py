import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys
import tempfile
import logging
import re
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import aiohttp
from dotenv import load_dotenv

from database import DatabaseManager
from utils import EncryptionManager
from password_commands import PasswordCommandHandler
from audio_downloader import AudioDownloader, AudioMetadata, AudioConfig

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    print("Error: DISCORD_TOKEN not found in environment variables.")
    sys.exit(1)


async def download_image_from_url(image_url: str) -> Optional[str]:
    """Download image from URL and save to temp file."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "image/jpeg")
                    ext = content_type.split("/")[-1].split(";")[0]

                    if ext not in ["jpeg", "jpg", "png", "gif", "webp"]:
                        ext = "jpg"

                    temp_file = tempfile.NamedTemporaryFile(
                        suffix=f".{ext}", delete=False, dir=tempfile.gettempdir()
                    )

                    image_data = await response.read()
                    temp_file.write(image_data)
                    temp_file.close()

                    return temp_file.name
                return None
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None


async def get_image_from_attachment(attachment: discord.Attachment) -> Optional[str]:
    """Download image from Discord attachment."""
    try:
        temp_file = tempfile.NamedTemporaryFile(
            suffix=f".{attachment.filename.split('.')[-1]}",
            delete=False,
            dir=tempfile.gettempdir(),
        )

        await attachment.save(temp_file.name)
        temp_file.close()

        return temp_file.name
    except Exception as e:
        print(f"Error saving attachment: {e}")
        return None


def validate_url(url: str) -> bool:
    """Validate YouTube/SoundCloud URL."""
    url_lower = url.lower()
    return any(
        pattern in url_lower
        for pattern in ["youtube.com/watch", "youtu.be/", "soundcloud.com"]
    )


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Railway health checks."""

    def do_GET(self):
        """Handle GET requests for health checks."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        elif parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"AIO Discord Bot is running")
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        """Suppress HTTP server logging to avoid spam."""
        pass


def start_health_server():
    """Start HTTP server for Railway health checks."""
    port = int(os.environ.get("PORT", 8080))

    def health_server():
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check server starting on port {port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Health check server shutting down")
            server.shutdown()

    # Start health server in separate thread
    import threading

    health_thread = threading.Thread(target=health_server, daemon=True)
    health_thread.start()
    logger.info("Health check server started in background")


class AIOBot(commands.Bot):
    """AIO Discord Bot with audio downloader and password manager."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.dm_messages = True
        intents.dm_reactions = True
        super().__init__(command_prefix="!", intents=intents)

        # Initialize components
        self.db_manager = None
        self.encryption_manager = None
        self.password_handler = None
        self.audio_downloader = None

    async def setup_hook(self):
        """Called when the bot is starting up."""
        print(f"Bot logged in as {self.user}")

        # Initialize database
        self.db_manager = DatabaseManager()
        await self.db_manager.initialize()
        logger.info("Database initialized")

        # Initialize encryption
        self.encryption_manager = EncryptionManager()
        if not self.encryption_manager.validate_key():
            logger.error("Invalid encryption key")
            raise ValueError("Invalid encryption key")
        logger.info("Encryption manager initialized")

        # Initialize password handler
        self.password_handler = PasswordCommandHandler(
            self, self.db_manager, self.encryption_manager
        )
        logger.info("Password handler initialized")

        # Initialize audio downloader
        audio_config = AudioConfig()
        self.audio_downloader = AudioDownloader(audio_config, verbose=False)
        logger.info("Audio downloader initialized")

        # Sync commands
        await self.tree.sync()
        print("Commands synced!")

    async def on_ready(self):
        """Called when the bot is ready."""
        print(f"{self.user} is ready!")

    async def on_message(self, message):
        """Handle incoming messages."""
        if message.author.bot:
            return

        # Process password commands through handler
        if self.password_handler:
            await self.password_handler.handle_message(message)

        # Also process through bot for other commands
        await self.process_commands(message)

    async def on_raw_reaction_add(self, payload):
        """Handle raw reaction events for password confirmations."""
        if payload.user_id == self.user.id:
            return

        if self.password_handler:
            await self.password_handler.handle_reaction(payload)


bot = AIOBot()


async def get_user_input(
    dm_channel, user: discord.User, timeout: int = 300
) -> Optional[str]:
    """Get input from user via DM."""
    logger.debug(f"Waiting for input from user {user.name} (ID: {user.id})")
    try:

        def check(msg):
            return msg.author == user and msg.channel == dm_channel

        message = await bot.wait_for("message", check=check, timeout=timeout)
        logger.debug(f"Received input from {user.name}: {message.content[:50]}")
        return message.content.strip()
    except asyncio.TimeoutError:
        logger.warning(f"Input timeout for user {user.name}")
        await dm_channel.send("⏱️ Request timed out.")
        return None


async def get_yes_no_reaction(
    dm_channel, user: discord.User, message: discord.Message
) -> Optional[bool]:
    """Get yes/no response via raw_reaction_add to be reliable in DMs and without cache."""
    message_id = message.id
    user_id = user.id
    channel_id = dm_channel.id

    logger.debug(
        f"Adding reactions to message {message_id} for user {user.name} (ID: {user_id}) in channel {channel_id}"
    )

    try:
        await message.add_reaction("✅")
        logger.debug("Added ✅ reaction")
        await message.add_reaction("❌")
        logger.debug("Added ❌ reaction")

        # Verify message exists
        try:
            fresh_message = await dm_channel.fetch_message(message_id)
            logger.debug(
                f"Fetched fresh message: {fresh_message.id}, channel: {fresh_message.channel.id}"
            )
        except Exception as fetch_error:
            logger.warning(f"Could not fetch fresh message: {fetch_error}")

        logger.debug(
            f"Setting up wait_for raw_reaction_add: user {user_id}, message {message_id}, channel {channel_id}"
        )

        def check(payload):
            # Ignore bot reactions
            if bot.user and payload.user_id == bot.user.id:
                return False
            logger.debug(
                f"Raw reaction payload received: user={payload.user_id}, message={payload.message_id}, channel={payload.channel_id}, emoji={payload.emoji}"
            )
            user_match = payload.user_id == user_id
            msg_match = payload.message_id == message_id
            chan_match = payload.channel_id == channel_id
            emoji_match = str(payload.emoji) in ["✅", "❌"]
            logger.debug(
                f"  - matches => user:{user_match} message:{msg_match} channel:{chan_match} emoji:{emoji_match}"
            )
            return user_match and msg_match and chan_match and emoji_match

        logger.debug("Starting wait_for('raw_reaction_add')...")
        payload = await bot.wait_for("raw_reaction_add", check=check, timeout=300)
        logger.debug(
            f"wait_for resolved with payload: emoji={payload.emoji}, user_id={payload.user_id}"
        )

        result = str(payload.emoji) == "✅"
        logger.info(f"User {user.name} selected: {'Yes (✅)' if result else 'No (❌)'}")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"Reaction timeout for user {user.name} after 300 seconds")
        await dm_channel.send("⏱️ Request timed out.")
        return None
    except Exception as e:
        logger.error(f"Reaction error for user {user.name}: {e}", exc_info=True)
        await dm_channel.send(f"❌ Error: {e}")
        return None


@bot.tree.command(
    name="download", description="Download audio from YouTube or SoundCloud"
)
async def download_command(interaction: discord.Interaction):
    """Start interactive download process."""

    logger.info(
        f"Download command initiated by {interaction.user.name} (ID: {interaction.user.id})"
    )
    await interaction.response.send_message(
        "Check your DMs to continue.", ephemeral=True
    )
    user = interaction.user

    try:
        logger.debug(f"Creating DM channel with {user.name}")
        dm_channel = await user.create_dm()
        logger.debug(f"DM channel created: {dm_channel.id}")

        # Create database entry for tracking
        download_id = await bot.db_manager.create_audio_download(
            user.id, "pending_download"
        )

        # Step 1: URL
        logger.info(f"Step 1/5 - Requesting URL from {user.name}")
        await dm_channel.send(
            "**Step 1 of 5: URL**\n\nEnter a YouTube or SoundCloud URL:"
        )
        url = await get_user_input(dm_channel, user)
        if not url:
            logger.warning(f"No URL provided by {user.name}")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return

        logger.debug(f"Validating URL: {url}")
        if not validate_url(url):
            logger.warning(f"Invalid URL provided by {user.name}: {url}")
            await dm_channel.send(
                "❌ Invalid URL. Please provide a valid YouTube or SoundCloud URL."
            )
            await bot.db_manager.update_audio_download(download_id, status="failed")
            return

        logger.info(f"URL validated for {user.name}: {url}")
        await dm_channel.send("✅ URL validated.")

        # Step 2: Artist
        logger.info(f"Step 2/5 - Requesting artist from {user.name}")
        await dm_channel.send(
            "**Step 2 of 5: Artist**\n\nEnter artist name (or type 'skip' or 'cancel'):"
        )
        artist = await get_user_input(dm_channel, user)
        if artist is None:
            logger.warning(f"User {user.name} timed out during artist input")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if artist.lower() == "cancel":
            await dm_channel.send("❌ Download cancelled.")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if not artist or artist.lower() == "skip":
            artist = None
            logger.debug(f"Artist skipped by {user.name}")
        else:
            logger.debug(f"Artist set: {artist}")
        await dm_channel.send("✅ Noted.")

        # Step 3: Title
        logger.info(f"Step 3/5 - Requesting title from {user.name}")
        await dm_channel.send(
            "**Step 3 of 5: Title**\n\nEnter song title (or type 'skip' or 'cancel'):"
        )
        title = await get_user_input(dm_channel, user)
        if title is None:
            logger.warning(f"User {user.name} timed out during title input")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if title.lower() == "cancel":
            await dm_channel.send("❌ Download cancelled.")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if not title or title.lower() == "skip":
            title = None
            logger.debug(f"Title skipped by {user.name}")
        else:
            logger.debug(f"Title set: {title}")
        await dm_channel.send("✅ Noted.")

        # Step 4: Album
        logger.info(f"Step 4/5 - Requesting album from {user.name}")
        await dm_channel.send(
            "**Step 4 of 5: Album**\n\nEnter album name (or type 'skip' or 'cancel'):"
        )
        album = await get_user_input(dm_channel, user)
        if album is None:
            logger.warning(f"User {user.name} timed out during album input")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if album.lower() == "cancel":
            await dm_channel.send("❌ Download cancelled.")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if not album or album.lower() == "skip":
            album = None
            logger.debug(f"Album skipped by {user.name}")
        else:
            logger.debug(f"Album set: {album}")
        await dm_channel.send("✅ Noted.")

        # Step 5: Filename
        logger.info(f"Step 5/5 - Requesting filename from {user.name}")
        await dm_channel.send(
            "**Step 5 of 5: Filename**\n\nEnter output filename (without .mp3, or type 'skip' or 'cancel' for auto-generated):"
        )
        filename = await get_user_input(dm_channel, user)
        if filename is None:
            logger.warning(f"User {user.name} timed out during filename input")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if filename.lower() == "cancel":
            await dm_channel.send("❌ Download cancelled.")
            await bot.db_manager.update_audio_download(download_id, status="cancelled")
            return
        if not filename or filename.lower() == "skip":
            filename = None
            logger.debug(f"Filename skipped by {user.name}")
        else:
            logger.debug(f"Filename set: {filename}")
        await dm_channel.send("✅ Noted.")

        # Step 6: Cover
        logger.info(f"Step 6 - Requesting album cover choice from {user.name}")
        cover_msg = await dm_channel.send(
            "**Album Cover**\n\nAdd album cover image? (React with ✅ for yes, ❌ for no)"
        )
        add_cover = await get_yes_no_reaction(dm_channel, user, cover_msg)

        cover_path = None
        if add_cover:
            logger.info(f"{user.name} chose to add album cover")
            await dm_channel.send(
                "Provide cover image:\n• Image URL (Imgur, Pinterest, Google Images, etc.)\n• Or attach an image file"
            )

            def check(msg):
                return msg.author == user and msg.channel == dm_channel

            try:
                logger.debug(f"Waiting for cover image from {user.name}")
                cover_msg = await bot.wait_for("message", check=check, timeout=300)

                if cover_msg.attachments:
                    logger.debug(f"Processing attachment from {user.name}")
                    attachment = cover_msg.attachments[0]
                    logger.debug(
                        f"Attachment type: {attachment.content_type}, filename: {attachment.filename}"
                    )
                    if attachment.content_type and attachment.content_type.startswith(
                        "image/"
                    ):
                        await dm_channel.send("📥 Saving image...")
                        cover_path = await get_image_from_attachment(attachment)
                        if cover_path:
                            logger.info(
                                f"Cover image saved for {user.name}: {cover_path}"
                            )
                            await dm_channel.send("✅ Image saved.")
                        else:
                            logger.error(f"Failed to save cover image for {user.name}")
                    else:
                        logger.warning(
                            f"Invalid attachment type from {user.name}: {attachment.content_type}"
                        )
                        await dm_channel.send("❌ Attachment must be an image file.")
                else:
                    cover_url = cover_msg.content.strip()
                    logger.debug(f"Processing cover URL from {user.name}: {cover_url}")
                    if cover_url:
                        await dm_channel.send("📥 Downloading image...")
                        cover_path = await download_image_from_url(cover_url)
                        if cover_path:
                            logger.info(
                                f"Cover image downloaded for {user.name}: {cover_path}"
                            )
                            await dm_channel.send("✅ Image downloaded.")
                        else:
                            logger.warning(
                                f"Failed to download cover image from {cover_url}"
                            )
                            await dm_channel.send(
                                "⚠️ Could not download image. Continuing without cover."
                            )
            except asyncio.TimeoutError:
                logger.warning(f"Cover image timeout for {user.name}")
                await dm_channel.send("⏱️ Request timed out.")
        else:
            logger.info(f"{user.name} chose not to add album cover")

        # Update database with metadata
        await bot.db_manager.update_audio_download(
            download_id, url=url, title=title, artist=artist, album=album
        )

        # Create metadata
        metadata = AudioMetadata(
            artist=artist, title=title, album=album, cover_path=cover_path
        )

        # Auto-detect if empty
        if metadata.is_empty():
            await dm_channel.send("🔍 Auto-detecting metadata...")
            try:
                import yt_dlp

                ydl_opts = {"quiet": True, "no_warnings": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                if "soundcloud.com" in url.lower():
                    detected = AudioMetadata.from_soundcloud_info(info)
                else:
                    detected = AudioMetadata.from_youtube_info(info)

                if not metadata.artist:
                    metadata.artist = detected.artist
                if not metadata.title:
                    metadata.title = detected.title
                if not metadata.album:
                    metadata.album = detected.album

                await dm_channel.send("✅ Metadata detected.")
            except Exception as e:
                await dm_channel.send(f"⚠️ Could not auto-detect metadata: {e}")

        # Download
        logger.info(f"Starting download for {user.name}")
        await dm_channel.send("📥 Downloading audio...")
        await bot.db_manager.update_audio_download(download_id, status="downloading")

        try:
            logger.debug(
                f"Calling downloader with metadata: artist={metadata.artist}, title={metadata.title}, album={metadata.album}"
            )
            output_file = await asyncio.to_thread(
                bot.audio_downloader.download, url, metadata, "good"
            )
            logger.info(f"Download completed for {user.name}: {output_file}")

            if filename:
                logger.debug(f"Renaming file to custom filename: {filename}")
                # Sanitize filename to remove invalid Windows characters
                safe_filename = re.sub(r'[<>:"/\\|?*]', "", filename)
                safe_filename = re.sub(r"[.\s]+", " ", safe_filename)
                safe_filename = safe_filename.strip(" .")

                if not safe_filename:
                    safe_filename = "downloaded_audio"

                safe_filename = safe_filename.rstrip(" .")

                new_filepath = output_file.parent / f"{safe_filename}.mp3"

                # Handle duplicate filenames
                counter = 1
                original_path = new_filepath
                while new_filepath.exists():
                    safe_filename = f"{original_path.stem}_{counter}"
                    new_filepath = output_file.parent / f"{safe_filename}.mp3"
                    counter += 1

                output_file.rename(new_filepath)
                output_file = new_filepath
                logger.debug(f"File renamed to: {output_file}")

            file_size = output_file.stat().st_size / (1024 * 1024)
            logger.info(f"File size: {file_size:.2f} MB")

            # Update database with completion
            await bot.db_manager.update_audio_download(
                download_id,
                filename=output_file.name,
                file_size=int(file_size * 1024 * 1024),
                status="completed",
            )

            if file_size > 25:
                logger.warning(f"File too large for Discord upload: {file_size:.2f} MB")
                await dm_channel.send(
                    f"✅ Download complete!\n\n"
                    f"**File:** `{output_file.name}`\n"
                    f"**Size:** {file_size:.2f} MB\n\n"
                    f"⚠️ File is too large for Discord (25 MB limit).\n"
                    f"**Location:** `{output_file}`"
                )
            else:
                logger.debug(f"Uploading file to Discord for {user.name}")
                await dm_channel.send(file=discord.File(output_file))
                logger.info(f"File uploaded successfully to Discord for {user.name}")

            if cover_path and os.path.exists(cover_path):
                logger.debug(f"Cleaning up temporary cover file: {cover_path}")
                try:
                    os.remove(cover_path)
                    logger.debug("Cover file removed")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to remove cover file: {cleanup_error}")

        except Exception as e:
            logger.error(f"Download failed for {user.name}: {e}", exc_info=True)
            await dm_channel.send(f"❌ Download failed: {e}")
            await bot.db_manager.update_audio_download(download_id, status="failed")

    except Exception as e:
        logger.error(
            f"Fatal error in download command for {user.name}: {e}", exc_info=True
        )
        try:
            await user.send(f"❌ Error: {e}")
        except:
            pass


@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    """Show help information."""

    embed = discord.Embed(
        title="🤖 AIO Discord Bot",
        description="All-in-one Discord bot with audio downloader and password manager",
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="🎵 Audio Downloader",
        value="/download - Start interactive audio download\n"
        "Supports YouTube and SoundCloud\n"
        "Custom metadata and album art",
        inline=False,
    )

    embed.add_field(
        name="🔐 Password Manager",
        value="!new [service] - Create new password\n"
        "!get <service> - Retrieve password\n"
        "!list - Show all services\n"
        "!update <service> - Update password\n"
        "!delete <service> - Delete password\n"
        "!help - Show password help",
        inline=False,
    )

    embed.add_field(
        name="🔒 Security",
        value="• All passwords encrypted with Fernet\n"
        "• Credentials sent via DM only\n"
        "• Auto-deletion of sensitive messages",
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="cancel", description="Cancel current download process")
async def cancel_command(interaction: discord.Interaction):
    """Cancel information."""

    await interaction.response.send_message(
        "❌ **Download Cancellation**\n\n"
        "To cancel a download process, simply type 'cancel' when prompted for any input during the download flow.\n\n"
        "The download will timeout automatically after 5 minutes of inactivity.",
        ephemeral=True,
    )


def main():
    """Main function to run the bot."""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set!")
        sys.exit(1)

    # Debug token
    token_len = len(DISCORD_TOKEN)
    masked_token = f"{DISCORD_TOKEN[:5]}...{DISCORD_TOKEN[-5:]}" if token_len > 10 else "TOO_SHORT"
    print(f"DEBUG: Token length: {token_len}")
    print(f"DEBUG: Token starts/ends: {masked_token}")
    print(f"DEBUG: Token has whitespace: {any(c.isspace() for c in DISCORD_TOKEN)}")
    
    try:
        # Start health check server for Railway
        start_health_server()

        # Run Discord bot
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Error: Invalid Discord bot token!")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
