"""Unified Stratz GraphQL client with comprehensive match analytics."""
import asyncio
import aiohttp
import logging
from typing import Optional

from ..models.stratz import StratzMatchData, StratzMatchResponse
from ..config import Config

logger = logging.getLogger(__name__)


class StratzClient:
    """Unified Stratz GraphQL client with enhanced analytics."""
    
    def __init__(self, config: Config):
        self.config = config
        self.graphql_url = "https://api.stratz.com/graphql"
        
    async def get_match_analysis(self, match_id: int) -> StratzMatchData:
        """Get comprehensive match analysis with all player data."""
        headers = {
            "Authorization": f"Bearer {self.config.stratz_api_token}",
            "User-Agent": "STRATZ_API",
            "Content-Type": "application/json"
        }
        
        query = self._build_comprehensive_query(match_id)
        request_body = {
            "query": query,
            "operationName": "MatchAnalysis"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(self.graphql_url,
                                   json=request_body,
                                   headers=headers) as response:
                
                if response.status != 200:
                    response_text = await response.text()
                    raise ValueError(f"Stratz API error {response.status}: {response_text}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise ValueError(f"Stratz GraphQL errors: {data['errors']}")
                
                # Convert to typed match data
                response_obj = StratzMatchResponse(**data)
                return response_obj.to_match_data(match_id)
    
    def validate_herald_match(self, match_data: StratzMatchData) -> bool:
        """Validate that match contains Herald players."""
        if not match_data.all_players_herald:
            logger.info(f"Match {match_data.match_id} contains non-Herald players, skipping")
            return False
        
        logger.info(f"Match {match_data.match_id} validated as all-Herald")
        return True
    
    def _build_comprehensive_query(self, match_id: int) -> str:
        """Build comprehensive GraphQL query for match analysis."""
        return f"""
        query MatchAnalysis {{
          match(id: {match_id}) {{
            players {{
              heroId
              kills
              deaths
              assists
              level
              heroDamage
              isRadiant
              position
              
              # Items
              item0Id
              item1Id
              item2Id
              item3Id
              item4Id
              item5Id
              
              # Steam account info
              steamAccount {{
                seasonRank
                name
                avatar
              }}
              
              # Advanced statistics
              stats {{
                actionsPerMinute
                
                # Ability usage
                abilityCastReport {{
                  abilityId
                  count
                  targets {{
                    target
                    count
                    damage
                    duration
                  }}
                }}
                
                # Item usage
                itemUsed {{
                  itemId
                  count
                }}
                
                # Timeline events
                itemPurchases {{
                  time
                  itemId
                }}
                
                # Combat events
                killEvents {{
                  time
                  target
                  byAbility
                  byItem
                }}
                
                deathEvents {{
                  time
                  attacker
                  target
                  byItem
                  byAbility
                  positionX
                  positionY
                }}
                
                # Map control
                wards {{
                  time
                  positionX
                  positionY
                  type
                }}
              }}
              
              # Playback data
              playbackData {{
                abilityLearnEvents {{
                  time
                  abilityId
                  level
                }}
                
                purchaseEvents {{
                  time
                  itemId
                }}
              }}
              
              # Dota Plus data
              dotaPlus {{
                level
              }}
            }}
          }}
        }}
        """