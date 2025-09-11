"""Unified OpenDota API client for periodic and interactive features."""

import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional
from pypika import Query, Table, Order
import logging
from urllib.parse import quote

from ..models.opendota import OpenDotaMatch, OpenDotaQueryResponse, OpenDotaMatchDetail
from ..config import Config

logger = logging.getLogger(__name__)


class OpenDotaClient:
    """Unified OpenDota API client with rate limiting and caching support."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://api.opendota.com/api"

    async def discover_herald_matches(self) -> List[OpenDotaMatch]:
        """Discover Herald matches for periodic reporting."""
        logger.info(
            f"Discovering Herald matches from last {self.config.query_days_back} days"
        )

        time_chunks = self._generate_time_chunks(self.config.query_days_back)
        all_matches = []

        for start_time, end_time in time_chunks:
            try:
                chunk_matches = await self._query_match_chunk(start_time, end_time)
                all_matches.extend(chunk_matches)

                # Rate limiting
                await asyncio.sleep(self.config.api_delay_seconds)

            except Exception as e:
                logger.error(f"Failed to query chunk {start_time}-{end_time}: {e}")
                continue

        # Filter for Herald eligibility
        herald_matches = [m for m in all_matches if m.is_herald_eligible]
        logger.info(
            f"Found {len(herald_matches)} Herald-eligible matches from {len(all_matches)} total"
        )

        return herald_matches

    async def get_match_details(self, match_id: int) -> OpenDotaMatchDetail:
        """Get detailed match information for analysis."""
        url = f"{self.base_url}/matches/{match_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(
                        f"OpenDota API error {response.status} for match {match_id}"
                    )

                data = await response.json()
                return OpenDotaMatchDetail(**data)

    def _generate_time_chunks(self, days_back: int) -> List[Tuple[int, int]]:
        """Generate 1-hour time chunks for efficient querying."""
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days_back)

        chunks = []
        current = start_date

        while current < now:
            chunk_end = min(current + timedelta(hours=1), now)
            chunks.append((int(current.timestamp()), int(chunk_end.timestamp())))
            current = chunk_end

        return chunks

    async def _query_match_chunk(
        self, start_time: int, end_time: int
    ) -> List[OpenDotaMatch]:
        """Query a single time chunk with optimized SQL."""
        public_matches = Table("public_matches")

        query = (
            Query.from_(public_matches)
            .select(
                public_matches.match_id,
                public_matches.start_time,
                public_matches.duration,
                public_matches.avg_rank_tier,
                public_matches.lobby_type,
                public_matches.game_mode,
            )
            .where(public_matches.avg_rank_tier >= 11)  # Herald minimum
            .where(public_matches.avg_rank_tier <= 15)  # Herald maximum
            .where(public_matches.duration > 4500)  # 75+ minutes
            .where(public_matches.start_time >= start_time)
            .where(public_matches.start_time <= end_time)
            .where(public_matches.lobby_type == 0)  # Public matches
            .limit(100)
            .orderby(public_matches.start_time, order=Order.desc)
        )

        # Fix query string conversion - try different methods
        try:
            # Try get_sql() method first (safer)
            if hasattr(query, 'get_sql'):
                sql_string = query.get_sql()
            else:
                # Fallback to str() conversion
                sql_string = str(query)
            
            logger.debug(f"Generated SQL for chunk {start_time}-{end_time}: {sql_string}")
        except Exception as e:
            logger.error(f"Failed to convert query to SQL string: {e}")
            raise ValueError(f"Query conversion failed: {e}")

        # Use GET request with percent-encoded SQL parameter
        encoded_sql = quote(sql_string)
        url = f"{self.base_url}/explorer?sql={encoded_sql}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenDota API error {response.status}: {error_text}")
                    raise ValueError(
                        f"OpenDota explorer query failed: {response.status}"
                    )

                try:
                    data = await response.json()
                    logger.debug(f"Raw API response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    
                    # Validate response structure before Pydantic parsing
                    if not isinstance(data, dict):
                        raise ValueError(f"Expected dict response, got {type(data)}")
                    
                    if 'err' in data and data['err']:
                        raise ValueError(f"OpenDota API returned error: {data['err']}")
                    
                    query_response = OpenDotaQueryResponse(**data)
                    return query_response.to_matches()
                    
                except Exception as e:
                    logger.error(f"Failed to parse API response: {e}")
                    logger.error(f"Raw response data: {data}")
                    raise ValueError(f"Response parsing failed: {e}")
