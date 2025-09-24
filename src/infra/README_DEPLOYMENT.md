# Herald Scraper Bot - Deployment Guide

## Infrastructure Overview

The Herald Scraper Bot is configured for deployment on Fly.io with cost-effective resource allocation suitable for a Discord bot.

### Resource Configuration

- **Memory**: 512MB (can be reduced to 256MB if stable)
- **CPU**: 1 shared CPU core
- **Region**: US East (Virginia) - configurable
- **Storage**: 1GB persistent volume for logs

### Cost Estimation

With the current configuration:
- **Monthly cost**: ~$3-5 USD
  - Shared CPU VM: ~$3/month
  - 1GB persistent storage: ~$0.15/month
  - Bandwidth: Minimal for Discord bot

## Deployment Steps

### 1. Prerequisites

Install the Fly.io CLI:
```bash
# macOS
brew install flyctl

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# Linux
curl -L https://fly.io/install.sh | sh
```

### 2. Authentication

```bash
flyctl auth login
```

### 3. Environment Variables

Create a `.env` file in the project root with your secrets:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_TEST_CHANNEL_ID=your_channel_id
OPENDOTA_API_KEY=your_opendota_key
STRATZ_API_TOKEN=your_stratz_token
OPENAI_API_KEY=your_openai_key  # Optional for AI features
```

### 4. Deploy

Run the deployment script:
```bash
cd src/infra
chmod +x deploy.sh  # Unix/Linux/Mac only
./deploy.sh
```

Or manually:
```bash
# Create app (first time only)
flyctl apps create herald-scraper-bot

# Create volume for logs (first time only)
flyctl volumes create herald_logs --size 1 --region iad

# Set secrets
flyctl secrets set DISCORD_BOT_TOKEN=your_token
flyctl secrets set OPENDOTA_API_KEY=your_key
flyctl secrets set STRATZ_API_TOKEN=your_token
flyctl secrets set OPENAI_API_KEY=your_key  # Optional

# Deploy
flyctl deploy --config src/infra/fly.toml
```

## Monitoring

### View Logs
```bash
flyctl logs
```

### Check Status
```bash
flyctl status
```

### SSH into Container
```bash
flyctl ssh console
```

### Health Check
The bot exposes health endpoints:
- `/health` - Bot health status
- `/metrics` - Prometheus-compatible metrics

## Scaling and Optimization

### Reduce Memory Usage
If the bot runs stable, you can reduce memory to save costs:
```toml
# In fly.toml
[[vm]]
  memory = "256mb"  # Reduced from 512mb
```

### Regional Deployment
Change the region based on your user base:
```toml
primary_region = "iad"  # US East
# Other options: "sea" (Seattle), "lhr" (London), "nrt" (Tokyo)
```

### Auto-scaling
The bot is configured with:
- Auto-restart on crashes (max 10 retries)
- Rolling deployments (zero downtime)
- Persistent log storage

## Troubleshooting

### Bot Not Starting
1. Check logs: `flyctl logs`
2. Verify secrets: `flyctl secrets list`
3. SSH in and check: `flyctl ssh console`

### Memory Issues
If you see OOM (Out of Memory) errors:
1. Increase memory in fly.toml
2. Redeploy: `flyctl deploy`

### Connection Issues
Ensure Discord token and API keys are correctly set:
```bash
flyctl secrets set DISCORD_BOT_TOKEN=new_token
```

## Backup and Recovery

### Export Logs
```bash
flyctl ssh console -C "cat /app/logs/herald_bot.log" > local_backup.log
```

### Database/Cache
The bot uses in-memory caching. No database backup needed.

## Updates and Maintenance

### Deploy Updates
```bash
git pull
flyctl deploy --config src/infra/fly.toml
```

### Zero-Downtime Deployment
The configuration uses rolling deployments to ensure the bot stays online during updates.

## Security Notes

- Never commit `.env` files to git
- Use Fly.io secrets for sensitive data
- The bot runs with minimal privileges
- Health endpoints don't expose sensitive data