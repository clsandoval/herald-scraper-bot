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


class StratzMatchResponse(BaseModel):
    """Wrapper for Stratz GraphQL response."""
    data: Dict[str, Any]
    
    def to_match_data(self, match_id: int) -> "StratzMatchData":
        """Convert raw GraphQL response to typed match data."""
        match_data = self.data.get("match")
        if not match_data:
            raise ValueError(f"Match {match_id} not found in Stratz response")
        
        return StratzMatchData(
            match_id=match_id,
            players=match_data["players"]
        )


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
        """Verify all players with rank data are Herald."""
        players_with_rank = [p for p in self.players if p.rank is not None]
        return all(p.is_herald for p in players_with_rank) if players_with_rank else False
    
    @property
    def average_apm(self) -> Optional[float]:
        """Calculate match average APM."""
        apms = [p.average_apm for p in self.players if p.average_apm is not None]
        return sum(apms) / len(apms) if apms else None
    
    @property
    def total_kills(self) -> int:
        """Calculate total kills in match."""
        return sum(p.kills for p in self.players)