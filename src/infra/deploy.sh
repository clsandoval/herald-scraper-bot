#!/bin/bash

# Herald Bot Deployment Script for Fly.io

set -e

echo "🚀 Deploying Herald Scraper Bot to Fly.io..."

# Check if fly CLI is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ Error: flyctl is not installed"
    echo "Install it from: https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Check if authenticated
if ! flyctl auth whoami &> /dev/null; then
    echo "📝 Please authenticate with Fly.io..."
    flyctl auth login
fi

# Navigate to project root
cd "$(dirname "$0")/../.."

# Check if app exists, if not create it
if ! flyctl apps list | grep -q "herald-scraper-bot"; then
    echo "📱 Creating new Fly.io app..."
    flyctl apps create herald-scraper-bot

    # Create volume for logs
    echo "💾 Creating persistent volume for logs..."
    flyctl volumes create herald_logs --size 1 --region iad
fi

# Set secrets from .env file if it exists
if [ -f .env ]; then
    echo "🔐 Setting secrets from .env file..."

    # Read .env file and set secrets
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        if [[ ! "$key" =~ ^# ]] && [[ -n "$key" ]]; then
            # Remove quotes from value if present
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"

            # Set the secret in Fly.io
            flyctl secrets set "$key=$value" --stage
        fi
    done < .env

    # Deploy the secrets
    flyctl secrets deploy
else
    echo "⚠️  Warning: No .env file found. Make sure to set secrets manually:"
    echo "   flyctl secrets set DISCORD_BOT_TOKEN=your_token"
    echo "   flyctl secrets set OPENDOTA_API_KEY=your_key"
    echo "   flyctl secrets set STRATZ_API_TOKEN=your_token"
    echo "   flyctl secrets set OPENAI_API_KEY=your_key"
fi

# Deploy the application
echo "🚀 Deploying application..."
flyctl deploy --config src/infra/fly.toml

# Show deployment status
echo "✅ Deployment complete!"
echo ""
echo "📊 Check your app status with:"
echo "   flyctl status"
echo ""
echo "📝 View logs with:"
echo "   flyctl logs"
echo ""
echo "🔧 SSH into the container with:"
echo "   flyctl ssh console"