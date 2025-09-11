"""Unified data models for Herald Discord Bot."""
from .opendota import OpenDotaMatch, OpenDotaMatchDetail, OpenDotaQueryResponse
from .stratz import StratzPlayer, StratzMatchData, StratzMatchResponse

__all__ = [
    "OpenDotaMatch", "OpenDotaMatchDetail", "OpenDotaQueryResponse",
    "StratzPlayer", "StratzMatchData", "StratzMatchResponse"
]