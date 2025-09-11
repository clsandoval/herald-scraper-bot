"""OpenDota API models with comprehensive validation."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class OpenDotaMatch(BaseModel):
    """Herald match from OpenDota query results."""
    match_id: int
    start_time: int
    duration: int
    avg_rank_tier: Optional[int] = None
    lobby_type: Optional[int] = None
    game_mode: Optional[int] = None
    
    @property
    def is_herald_eligible(self) -> bool:
        """Check if match meets Herald criteria (rank 11-15, duration >75min)."""
        return (
            self.avg_rank_tier is not None 
            and 11 <= self.avg_rank_tier <= 15
            and self.duration > 4500
        )
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS."""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    @property
    def start_datetime(self) -> datetime:
        """Convert start_time to datetime object."""
        return datetime.fromtimestamp(self.start_time)


class OpenDotaQueryResponse(BaseModel):
    """Response wrapper for OpenDota explorer queries - VALIDATED AGAINST REAL API DATA."""
    command: str
    rowCount: int = Field(alias="rowCount")
    rows: List[Dict[str, Any]]  # CORRECTED: Objects not arrays!
    fields: List[Dict[str, Any]]
    
    # Additional fields found in actual response
    oid: Optional[Any] = None
    err: Optional[str] = None
    
    def to_matches(self) -> List[OpenDotaMatch]:
        """Convert raw rows to typed match objects - CORRECTED for dict access."""
        matches = []
        for row in self.rows:
            matches.append(OpenDotaMatch(
                match_id=row["match_id"],
                start_time=row["start_time"], 
                duration=row["duration"],
                avg_rank_tier=row.get("avg_rank_tier"),
                lobby_type=None,  # Not available in query response
                game_mode=None    # Not available in query response
            ))
        return matches


class OpenDotaMatchDetail(BaseModel):
    """Detailed match information from OpenDota match API - VALIDATED AGAINST REAL API DATA."""
    match_id: int
    duration: int
    start_time: int
    lobby_type: int
    game_mode: int
    radiant_win: bool  # Added from real data
    players: List[Dict[str, Any]]
    
    # Additional fields from actual API response
    series_id: Optional[int] = 0
    series_type: Optional[int] = 0
    cluster: Optional[int] = None
    radiant_score: Optional[int] = None
    dire_score: Optional[int] = None
    replay_url: Optional[str] = None
    patch: Optional[int] = None
    region: Optional[int] = None
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS."""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    @property
    def has_leavers(self) -> bool:
        """Check if any players abandoned the game."""
        return any(player.get("leaver_status", 0) != 0 for player in self.players)
    
    @property
    def radiant_players(self) -> List[Dict[str, Any]]:
        """Get Radiant team players (player_slot < 128)."""
        return [p for p in self.players if p.get("player_slot", 0) < 128]
    
    @property
    def dire_players(self) -> List[Dict[str, Any]]:
        """Get Dire team players (player_slot >= 128)."""
        return [p for p in self.players if p.get("player_slot", 0) >= 128]