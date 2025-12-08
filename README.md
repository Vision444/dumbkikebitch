# AIO Discord Bot - All-in-One Discord Bot

A comprehensive Discord bot that combines audio downloading from YouTube/SoundCloud with secure password management, all powered by a single PostgreSQL database.

## Features

### 🎵 Audio Downloader
- Download audio from YouTube, SoundCloud, and Twitter/X
- Interactive 6-step DM workflow for metadata collection
- Custom metadata (artist, title, album, filename)
- Album art embedding from URLs or attachments
- Auto-detection of metadata from video info
- File size handling for Discord limits (25MB)
- Download tracking in database
- Twitter/X video audio extraction

### 🔐 Password Manager
- Secure password storage with Fernet encryption
- CRUD operations (Create, Read, Update, Delete)
- Multi-step command flows with 120-second timeouts
- Credentials sent via DM only
- Auto-deletion of sensitive messages
- Smart search and duplicate handling
- Complete audit trail with timestamps

### 🚀 Deployment Ready
- Railway-ready configuration
- Health check endpoints
- Automatic database table creation
- Connection pooling for performance
- Comprehensive error handling
- Structured logging

## Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd aio-discord-bot
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env` file and configure:

```env
# Discord Bot Token (Required)
DISCORD_TOKEN=your_discord_bot_token_here

# Database Configuration (Required)
DATABASE_URL=postgresql://postgres:xyLqkqZvMQubrvDkBoffAzxRuMaPwCHv@postgres-production-8950.up.railway.app/railway

# Encryption Key for Password Manager (Required)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_encryption_key_here

# Audio Downloader Configuration (Optional)
OUTPUT_DIRECTORY=./downloads
AUDIO_QUALITY=best
FFMPEG_PATH=ffmpeg
DEFAULT_ARTIST=
DEFAULT_ALBUM=

# Railway Configuration (Optional)
PORT=8080
```

### 3. Generate Encryption Key
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())
```

### 4. Run Locally
```bash
python main.py
```

## Commands

### Audio Downloader (Slash Commands)
- `/download` - Start interactive audio download process
- `/help` - Show available commands
- `/cancel` - Show cancellation instructions
- Supports: YouTube, SoundCloud, Twitter/X URLs

### Password Manager (Prefix Commands)
- `!new [service]` - Create new password (with or without service name)
- `!get <service>` - Retrieve password via DM
- `!list` - Show all stored services
- `!update <service>` - Update existing password
- `!delete <service>` - Delete password with confirmation
- `!help` - Show password manager help

## Database Schema

The bot automatically creates two tables in your PostgreSQL database:

### passwords table
```sql
CREATE TABLE passwords (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    service_name TEXT NOT NULL,
    username TEXT,
    encrypted_payload BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### audio_downloads table
```sql
CREATE TABLE audio_downloads (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    filename TEXT,
    file_size BIGINT,
    download_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

## Railway Deployment

### 1. Deploy to Railway
1. Connect your GitHub repository to Railway
2. Railway will automatically detect the Python project
3. Add environment variables in Railway dashboard:
   - `DISCORD_TOKEN`
   - `ENCRYPTION_KEY` 
   - `DATABASE_URL` (Railway provides this when you add PostgreSQL)

### 2. Railway Configuration Files
- **Procfile**: Tells Railway how to run your bot
- **railway.json**: Deployment configuration with health checks
- **requirements.txt**: Python dependencies

### 3. Health Checks
- **Health Check**: `GET /health` → Returns "OK" when running
- **Status**: `GET /` → Returns service status
- **Port**: Automatically detected via `PORT` environment variable

## Security Features

### Password Manager
- **Encryption**: All passwords encrypted with Fernet (AES-128 + HMAC-SHA256)
- **DM Delivery**: Credentials sent via direct messages only
- **Auto-deletion**: Password messages automatically deleted after 60 seconds
- **Input Validation**: All user inputs validated and sanitized
- **Error Handling**: No sensitive data logged or exposed

### Audio Downloader
- **URL Validation**: Accepts YouTube, SoundCloud, and Twitter/X URLs
- **File Sanitization**: Safe filename generation for all operating systems
- **Size Limits**: Handles Discord's 25MB file upload limit
- **Metadata Sanitization**: All metadata properly validated
- **Twitter/X Support**: Extracts audio from Twitter/X video posts

## Development

### Project Structure
```
├── main.py              # Main bot file with unified command handling
├── database.py          # Database manager with both schemas
├── utils.py             # Encryption utilities
├── password_commands.py # Password manager command handler
├── audio_downloader.py  # Audio downloading functionality
├── requirements.txt    # Python dependencies
├── .env                # Environment variables
├── Procfile           # Railway process configuration
├── railway.json       # Railway deployment configuration
└── README.md          # This file
```

### Adding New Features
1. Create new command handler files following the pattern in `password_commands.py`
2. Add database methods to `database.py`
3. Register commands in `main.py`
4. Update requirements.txt if new dependencies are needed

### Testing
The bot includes comprehensive error handling and logging. Monitor the console output for debugging information.

## Troubleshooting

### Common Issues

1. **Bot doesn't respond**: Check Discord token and intents
2. **Database errors**: Verify DATABASE_URL and PostgreSQL access
3. **Encryption errors**: Ensure ENCRYPTION_KEY is valid Fernet key
4. **Permission errors**: Bot needs Message Content Intent enabled
5. **Audio download fails**: Check ffmpeg installation and network connectivity

### Logs
Monitor Railway logs or local console for detailed error information and debugging.

## Dependencies

- **discord.py** 2.3+ - Discord API wrapper
- **asyncpg** 0.28+ - Async PostgreSQL driver
- **cryptography** 41.0+ - Fernet encryption
- **yt-dlp** 2023.0+ - YouTube/SoundCloud/Twitter downloader
- **mutagen** 1.46.0+ - Audio metadata handling
- **requests** 2.31.0+ - HTTP client
- **aiohttp** 3.8.0+ - Async HTTP client
- **python-dotenv** 1.0.0+ - Environment variable management

## License

This project is open source. Feel free to use, modify, and distribute according to your needs.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for specific error messages
3. Ensure all environment variables are correctly set
4. Verify Discord bot permissions and intents

---

**Note**: This bot combines the functionality of both Filez (audio downloader) and Pw (password manager) into a single, unified Discord bot with shared infrastructure and a single PostgreSQL database.