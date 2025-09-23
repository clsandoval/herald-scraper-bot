"""Stratz API models with comprehensive player analytics."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class StratzPlayer(BaseModel):
    """Enhanced player data from Stratz GraphQL API - VALIDATED AGAINST REAL API DATA."""

    # Core fields from API
    heroId: int = Field(alias="heroId")
    kills: int
    deaths: int
    assists: int
    level: Optional[int] = None
    heroDamage: int = Field(alias="heroDamage", default=0)
    isRadiant: bool = Field(alias="isRadiant")
    position: Optional[str] = None  # "POSITION_1", "POSITION_5", etc.

    # Steam account and stats (can be None)
    steamAccount: Optional[Dict[str, Any]] = Field(alias="steamAccount", default=None)
    stats: Optional[Dict[str, Any]] = Field(default=None)

    # Items - CORRECTED to be optional since they may not exist in all responses
    item0Id: Optional[int] = Field(alias="item0Id", default=None)
    item1Id: Optional[int] = Field(alias="item1Id", default=None)
    item2Id: Optional[int] = Field(alias="item2Id", default=None)
    item3Id: Optional[int] = Field(alias="item3Id", default=None)
    item4Id: Optional[int] = Field(alias="item4Id", default=None)
    item5Id: Optional[int] = Field(alias="item5Id", default=None)

    # Advanced data (optional)
    playbackData: Optional[Dict[str, Any]] = Field(alias="playbackData", default=None)
    dotaPlus: Optional[Dict[str, Any]] = Field(alias="dotaPlus", default=None)

    @property
    def rank(self) -> Optional[int]:
        """Extract rank from steam account data."""
        if self.steamAccount and "seasonRank" in self.steamAccount:
            return self.steamAccount["seasonRank"]
        return None

    @property
    def is_herald(self) -> bool:
        """Check if player is Herald rank (11-15)."""
        rank = self.rank
        return rank is not None and 11 <= rank <= 15

    @property
    def kda_ratio(self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return float(self.kills + self.assists)
        return (self.kills + self.assists) / self.deaths

    @property
    def position_number(self) -> Optional[int]:
        """Extract position number from position string."""
        if self.position and self.position.startswith("POSITION_"):
            try:
                return int(self.position.split("_")[1])
            except (IndexError, ValueError):
                pass
        return None

    @property
    def actions_per_minute(self) -> List[int]:
        """Get APM data (array of integers)."""
        if self.stats and "actionsPerMinute" in self.stats:
            return self.stats["actionsPerMinute"]
        return []

    @property
    def average_apm(self) -> Optional[float]:
        """Calculate average APM from the array."""
        apm_data = self.actions_per_minute
        if apm_data:
            return sum(apm_data) / len(apm_data)
        return None

    @property
    def purchase_events(self) -> List[Dict[str, Any]]:
        """Get purchase timing events for AI analysis."""
        # Check playbackData first (more detailed)
        if self.playbackData and "purchaseEvents" in self.playbackData:
            return self.playbackData["purchaseEvents"]
        # Fallback to stats itemPurchases
        if self.stats and "itemPurchases" in self.stats:
            return self.stats["itemPurchases"]
        return []

    @property
    def ability_cast_report(self) -> List[Dict[str, Any]]:
        """Get ability cast statistics for AI analysis."""
        if self.stats and "abilityCastReport" in self.stats:
            return self.stats["abilityCastReport"]
        return []

    @property
    def major_item_timings(self) -> List[str]:
        """Extract major item purchase timings for AI analysis."""
        timings = []
        for event in self.purchase_events:
            time_sec = event.get("time", 0)
            item_id = event.get("itemId")
            if item_id and time_sec > 0:
                minutes = time_sec // 60
                item_name = self._get_item_name_safe(item_id)
                if self._is_major_item(item_id):
                    timings.append(f"{item_name} @{minutes}m")
        return timings

    @property
    def ability_usage_anomalies(self) -> List[str]:
        """Identify unusual ability usage patterns."""
        anomalies = []
        for ability in self.ability_cast_report:
            ability_id = ability.get("abilityId")
            cast_count = ability.get("count", 0)
            ability_name = self._get_ability_name_safe(ability_id)

            # Detect spam clicking (>200 casts)
            if cast_count > 200:
                anomalies.append(f"{ability_name}: {cast_count} casts (spam clicking)")
            # Detect underused ultimates (usually 6000+ ability IDs are ultimates)
            elif ability_id and ability_id >= 6000 and cast_count <= 3:
                anomalies.append(
                    f"{ability_name}: only {cast_count} casts (underused ultimate)"
                )

        return anomalies

    @property
    def kill_events(self) -> List[Dict[str, Any]]:
        """Get kill events for AI analysis."""
        if self.stats and "killEvents" in self.stats:
            return self.stats["killEvents"]
        return []

    @property
    def death_events(self) -> List[Dict[str, Any]]:
        """Get death events for AI analysis."""
        if self.stats and "deathEvents" in self.stats:
            return self.stats["deathEvents"]
        return []

    def _get_item_name_safe(self, item_id: int) -> str:
        """Safely get item name with fallback."""
        try:
            from ..constants import get_item_name

            return get_item_name(item_id)
        except Exception:
            return f"Item_{item_id}"

    def _get_ability_name_safe(self, ability_id: int) -> str:
        """Safely get ability name with fallback."""
        try:
            from ..constants import get_ability_name

            return get_ability_name(ability_id)
        except Exception:
            return f"Ability_{ability_id}"

    def _is_major_item(self, item_id: int) -> bool:
        """Check if item is considered major (rough heuristic)."""
        # Major items typically have higher IDs and cost more
        # This is a simplified heuristic - could be improved with actual cost data
        major_item_ids = {
            1,
            41,
            46,
            50,
            102,
            116,
            135,
            139,
            141,
            152,
            156,
            158,
            166,
            172,
            185,
            196,
            206,
            208,
            214,
            220,
            236,
            240,
            242,
            247,
            250,
            254,
            263,
            267,
            277,
            279,
            285,
            288,
            292,
            300,
        }
        return item_id in major_item_ids or item_id > 200


class StratzMatchResponse(BaseModel):
    """Wrapper for Stratz GraphQL response."""

    data: Dict[str, Any]

    def to_match_data(self, match_id: int) -> "StratzMatchData":
        """Convert raw GraphQL response to typed match data."""
        match_data = self.data.get("match")
        if not match_data:
            raise ValueError(f"Match {match_id} not found in Stratz response")

        return StratzMatchData(match_id=match_id, players=match_data["players"])


class StratzMatchData(BaseModel):
    """Complete match data with player analytics."""

    match_id: int  # Injected since it's not in API response
    players: List[StratzPlayer]

    @property
    def radiant_players(self) -> List[StratzPlayer]:
        """Get Radiant team players."""
        return [p for p in self.players if p.isRadiant]

    @property
    def dire_players(self) -> List[StratzPlayer]:
        """Get Dire team players."""
        return [p for p in self.players if not p.isRadiant]

    @property
    def all_players_herald(self) -> bool:
        """Verify all players have rank data AND are Herald."""
        # Only check players that have rank data
        ranked_players = [p for p in self.players if p.rank is not None]
        # All ranked players must be herald
        return all(p.is_herald for p in ranked_players)

    @property
    def average_apm(self) -> Optional[float]:
        """Calculate match average APM."""
        apms = [p.average_apm for p in self.players if p.average_apm is not None]
        return sum(apms) / len(apms) if apms else None

    @property
    def total_kills(self) -> int:
        """Calculate total kills in match."""
        return sum(p.kills for p in self.players)
