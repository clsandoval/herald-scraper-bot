# Deployment Instructions for Herald Discord Bot on Fly.io

## Prerequisites
1. Install Fly CLI: https://fly.io/docs/hands-on/install-flyctl/
2. Sign up for Fly.io account: https://fly.io/signup
3. Have your Discord bot token and API keys ready

## Initial Setup

1. **Authenticate with Fly.io:**
   ```bash
   fly auth login
   ```

2. **Create your Fly app:**
   ```bash
   fly apps create herald-discord-bot
   ```
   Note: Replace `herald-discord-bot` with your preferred app name

3. **Update fly.toml:**
   Edit `fly.toml` and change the `app` name to match your created app

## Configure Secrets

Set your environment variables as Fly secrets:

```bash
# Required secrets
fly secrets set DISCORD_BOT_TOKEN=your_discord_bot_token
fly secrets set DISCORD_TEST_CHANNEL_ID=your_channel_id

# API Keys (if using Dota 2 features)
fly secrets set OPENDOTA_API_KEY=your_opendota_key
fly secrets set STRATZ_API_TOKEN=your_stratz_token

# OpenAI (if using AI features)
fly secrets set OPENAI_API_KEY=your_openai_key
```

## Create Persistent Volume

Create a volume for logs and data persistence:

```bash
fly volumes create herald_bot_data --size 1 --region iad
```
Note: Change `iad` to match your primary region in fly.toml

## Deploy

Deploy your bot:

```bash
fly deploy
```

## Monitor

Check your bot status:

```bash
# View app status
fly status

# View logs
fly logs

# SSH into the running container (for debugging)
fly ssh console
```

## Update Deployment

To deploy updates:

```bash
fly deploy
```

## Scaling

To scale your bot (if needed):

```bash
# Scale to different VM size
fly scale vm shared-cpu-2x --memory 1024

# Or adjust in fly.toml and redeploy
```

## Troubleshooting

1. **Bot not starting:**
   - Check logs: `fly logs`
   - Verify all required secrets are set: `fly secrets list`

2. **Connection issues:**
   - Ensure Discord token is valid
   - Check that the bot has proper permissions in your Discord server

3. **Memory issues:**
   - Scale up the VM: `fly scale vm shared-cpu-1x --memory 1024`

## Stop/Start Commands

```bash
# Stop the bot
fly apps stop herald-discord-bot

# Start the bot
fly apps start herald-discord-bot

# Restart the bot
fly apps restart herald-discord-bot
```