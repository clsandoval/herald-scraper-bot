"""Unified match data cache for periodic and interactive features."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with access tracking and TTL."""
    match_details: Any
    stratz_data: Any
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    def is_expired(self, ttl_hours: int) -> bool:
        """Check if entry has exceeded TTL."""
        return datetime.now(timezone.utc) - self.created_at > timedelta(hours=ttl_hours)
    
    @property
    def age_minutes(self) -> int:
        """Get entry age in minutes."""
        return int((datetime.now(timezone.utc) - self.created_at).total_seconds() / 60)
    
    def access(self) -> Tuple[Any, Any]:
        """Mark as accessed and return data."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        return self.match_details, self.stratz_data


class UnifiedMatchCache:
    """Thread-safe cache shared between periodic and interactive features."""
    
    def __init__(self, ttl_hours: int = 4, max_entries: int = 100):
        self.ttl_hours = ttl_hours
        self.max_entries = max_entries
        self._cache: Dict[int, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
    async def get(self, match_id: int) -> Optional[Tuple[Any, Any]]:
        """Get cached match data if available and fresh."""
        async with self._lock:
            entry = self._cache.get(match_id)
            
            if entry and not entry.is_expired(self.ttl_hours):
                self._stats['hits'] += 1
                logger.info(f"Cache HIT for match {match_id}")
                return entry.access()
            elif entry:
                # Remove expired entry
                del self._cache[match_id]
                logger.info(f"Removed expired cache entry for match {match_id}")
            
            self._stats['misses'] += 1
            logger.info(f"Cache MISS for match {match_id}")
            return None
    
    async def set(self, match_id: int, match_details: Any, stratz_data: Any) -> None:
        """Store match data with automatic capacity management."""
        async with self._lock:
            # Clean up expired entries first
            await self._cleanup_expired()
            
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_entries:
                oldest_id = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
                del self._cache[oldest_id]
                self._stats['evictions'] += 1
                logger.info(f"Evicted oldest entry: match {oldest_id}")
            
            # Store new entry
            self._cache[match_id] = CacheEntry(
                match_details=match_details,
                stratz_data=stratz_data,
                created_at=datetime.now(timezone.utc)
            )
            logger.info(f"Cached match data for {match_id}")
    
    async def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        expired = [
            match_id for match_id, entry in self._cache.items()
            if entry.is_expired(self.ttl_hours)
        ]
        for match_id in expired:
            del self._cache[match_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired entries")
    
    async def stats(self) -> Dict[str, Any]:
        """Get basic cache statistics.""" 
        async with self._lock:
            return {
                "entries": len(self._cache),
                "total_hits": self._stats['hits'],
                "total_misses": self._stats['misses'],
                "total_evictions": self._stats['evictions']
            }
    
    async def clear(self) -> None:
        """Clear all cached data (for testing)."""
        async with self._lock:
            cleared = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {cleared} cache entries")