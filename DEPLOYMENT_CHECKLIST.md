# Deployment Checklist for AIO Discord Bot

## ✅ Pre-Deployment Checklist

### 1. Environment Variables (Required)
- [x] Database credentials configured
- [x] Encryption key generated and set
- [ ] DISCORD_TOKEN (add your bot token)

### 2. Discord Bot Setup
- [ ] Create bot at https://discord.com/developers/applications
- [ ] Enable Message Content Intent
- [ ] Enable Server Members Intent (optional)
- [ ] Copy bot token to .env file
- [ ] Invite bot to test server with permissions:
  - Send Messages
  - Use Slash Commands
  - Attach Files
  - Add Reactions
  - Use External Emojis
  - Read Message History

### 3. Railway Deployment
- [ ] Push code to GitHub repository
- [ ] Connect repository to Railway
- [ ] Add PostgreSQL service in Railway
- [ ] Set environment variables in Railway dashboard:
  - DISCORD_TOKEN
  - ENCRYPTION_KEY
  - DATABASE_URL (Railway provides this)

## 🚀 Deployment Steps

### Step 1: GitHub Setup
```bash
git add .
git commit -m "Initial AIO Discord Bot with audio downloader and password manager"
git push origin main
```

### Step 2: Railway Setup
1. Go to https://railway.app/dashboard
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway will auto-detect Python project
5. Add PostgreSQL service
6. Configure environment variables

### Step 3: Environment Variables in Railway
```
DISCORD_TOKEN=your_actual_discord_bot_token
ENCRYPTION_KEY=uwACs9Uw8Cg9zpPJP2fshnLCU7z0rvjoWOEKcyWyZh0=
DATABASE_URL=postgresql://postgres:your_password@your-host.railway.app/railway
```

### Step 4: Test Deployment
- Check Railway logs for startup
- Test `/help` command in Discord
- Test `!help` command in Discord
- Verify database tables are created

## 🔧 Local Testing

Before deploying, test locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Add your Discord token to .env
# DISCORD_TOKEN=your_token_here

# Run bot
python main.py
```

## 📋 Commands to Test

### Audio Downloader (Slash Commands)
- `/download` - Should start DM workflow
- `/help` - Should show command list
- `/cancel` - Should show cancellation info

### Password Manager (Prefix Commands)
- `!new Gmail` - Should start password creation
- `!help` - Should show password commands
- `!list` - Should show empty list initially

## 🚨 Troubleshooting

### Common Issues:
1. **Bot doesn't respond**: Check DISCORD_TOKEN and intents
2. **Database errors**: Verify DATABASE_URL in Railway
3. **Encryption errors**: Ensure ENCRYPTION_KEY matches
4. **Permission errors**: Check bot permissions in Discord

### Health Check:
- `https://your-app.railway.app/health` should return "OK"
- `https://your-app.railway.app/` should return status message

## 📊 Monitoring

- Railway Dashboard → Logs for real-time monitoring
- Database usage in Railway PostgreSQL section
- Bot activity in Discord server

---

**Ready to deploy!** Just add your Discord token and push to GitHub.