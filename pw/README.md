# Discord Password Manager Bot

A high-performance Discord bot for secure password management with PostgreSQL database and Fernet encryption.

## Features

- 🔐 **Secure Storage**: All passwords encrypted with Fernet symmetric encryption
- 🚀 **High Performance**: AsyncPG connection pool for maximum database speed
- 📱 **Multi-step Commands**: Intuitive command flows with 120-second timeout
- 🔍 **Smart Search**: Partial matching and duplicate service name handling
- 💬 **DM Security**: Sensitive credentials sent via direct messages
- 📋 **Complete CRUD**: Create, Read, Update, Delete operations
- 🛡️ **Error Handling**: Comprehensive error handling and logging

## Commands

### Password Management
- `!new` - Start multi-step password creation
- `!new <service>` - Quick add with service name
- `!get <service>` - Retrieve credentials via DM
- `!list` - Show all stored services
- `!delete <service>` - Remove entry with confirmation
- `!update <service>` - Modify existing entry
- `!help` - Show usage information

### Command Examples

```
!new
!new Gmail
!get Gmail
!list
!delete Netflix
!update Amazon
```

## Tech Stack

- **Language**: Python 3.10+
- **Framework**: discord.py 2.3+
- **Database**: PostgreSQL with asyncpg
- **Encryption**: cryptography (Fernet)
- **Deployment**: Railway

## Setup

### 1. Environment Variables

Create a `.env` file with the following variables:

```env
DISCORD_TOKEN=your_discord_bot_token_here
ENCRYPTION_KEY=your_fernet_encryption_key_here
DATABASE_URL=postgresql://username:password@host:port/database_name
```

### 2. Generate Encryption Key

Run this Python script to generate a Fernet key:

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())
```

### 3. Database Setup

The bot automatically creates the required tables on startup. Just ensure your PostgreSQL database is accessible.

### 4. Discord Bot Setup

1. Create a new application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a bot user
3. Enable Message Content Intent
4. Copy the bot token
5. Invite the bot to your server with appropriate permissions

## Deployment on Railway

### 1. Prepare Your Repository

Ensure your repository contains:
- `main.py` - Main bot file
- `database.py` - Database layer
- `utils.py` - Encryption utilities
- `commands.py` - Command handlers
- `requirements.txt` - Dependencies
- `Procfile` - Railway process configuration

### 2. Deploy to Railway

1. Connect your GitHub repository to Railway
2. Railway will automatically detect the Python project
3. Add environment variables in Railway dashboard:
   - `DISCORD_TOKEN`
   - `ENCRYPTION_KEY`
   - `DATABASE_URL` (Railway provides this when you add PostgreSQL)

### 3. Railway Configuration

The `Procfile` tells Railway how to run your bot:
```
worker: python main.py
```

## Database Schema

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

CREATE INDEX idx_user_service ON passwords(user_id, service_name);
```

## Security Features

- **Encryption**: All passwords encrypted with Fernet (AES-128 + HMAC-SHA256)
- **DM Delivery**: Credentials sent via direct messages only
- **Message Cleanup**: Password messages automatically deleted
- **Input Validation**: All user inputs validated and sanitized
- **Error Handling**: No sensitive data logged or exposed

## Performance Features

- **Connection Pooling**: 2-10 concurrent database connections
- **Async Operations**: Non-blocking database and Discord operations
- **Efficient Queries**: Optimized database queries with proper indexing
- **Memory Management**: Efficient state management with cleanup

## Error Handling

- Database connection failures with retry logic
- Discord API error handling
- Invalid input validation
- Timeout management (120 seconds)
- Graceful degradation for edge cases

## Development

### Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up `.env` file with local variables
4. Run: `python main.py`

### Testing

The bot includes comprehensive error handling and logging. Monitor the console output for debugging information.

## Troubleshooting

### Common Issues

1. **Bot doesn't respond**: Check Discord token and intents
2. **Database errors**: Verify DATABASE_URL and PostgreSQL access
3. **Encryption errors**: Ensure ENCRYPTION_KEY is valid Fernet key
4. **Permission errors**: Bot needs Message Content Intent enabled

### Logs

Monitor Railway logs or local console for detailed error information and debugging.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Feel free to use, modify, and distribute according to your needs.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for specific error messages
3. Ensure all environment variables are correctly set
4. Verify Discord bot permissions and intents