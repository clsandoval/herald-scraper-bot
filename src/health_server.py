"""Simple health check server for Fly.io monitoring."""

import asyncio
import logging
from aiohttp import web

logger = logging.getLogger(__name__)


class HealthServer:
    """Simple HTTP server for health checks."""

    def __init__(self, bot, port=8080):
        self.bot = bot
        self.port = port
        self.app = web.Application()
        self.runner = None
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/metrics', self.metrics)

    async def health_check(self, request):
        """Health check endpoint."""
        is_ready = self.bot.is_ready() if hasattr(self.bot, 'is_ready') else False

        if is_ready:
            return web.json_response({
                'status': 'healthy',
                'bot_ready': True,
                'guilds': len(self.bot.guilds) if hasattr(self.bot, 'guilds') else 0,
                'uptime': self.bot.uptime.total_seconds() if hasattr(self.bot, 'uptime') else 0
            })
        else:
            return web.json_response({
                'status': 'starting',
                'bot_ready': False
            }, status=503)

    async def metrics(self, request):
        """Metrics endpoint for monitoring."""
        metrics_data = {
            'bot_ready': 1 if (hasattr(self.bot, 'is_ready') and self.bot.is_ready()) else 0,
            'guilds_count': len(self.bot.guilds) if hasattr(self.bot, 'guilds') else 0,
            'users_count': len(self.bot.users) if hasattr(self.bot, 'users') else 0,
            'latency_ms': self.bot.latency * 1000 if hasattr(self.bot, 'latency') else 0,
        }

        # Format as Prometheus metrics
        metrics_text = []
        for key, value in metrics_data.items():
            metrics_text.append(f"herald_bot_{key} {value}")

        return web.Response(text='\n'.join(metrics_text), content_type='text/plain')

    async def start(self):
        """Start the health check server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await site.start()
            logger.info(f"Health check server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")

    async def stop(self):
        """Stop the health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")