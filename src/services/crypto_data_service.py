import os
import logging
import aiohttp
import json
import time
from typing import Dict, Optional, Tuple, Any
from decimal import Decimal
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('CryptoDataService')

class CryptoDataService:
    """Service for retrieving cryptocurrency market data from CoinMarketCap"""
    
    def __init__(self, api_key: str = None):
        """Initialize the CryptoDataService with API key and cache"""
        self.api_key = api_key or os.getenv('COINMARKETCAP_API_KEY')
        if not self.api_key:
            logger.warning("No CoinMarketCap API key provided. Service will not work.")
        
        self.base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        self.cache = {}
        self.cache_expiry = {}
        self.cache_duration = 300  # Cache data for 5 minutes (300 seconds)
    
    async def get_crypto_data(self, symbols: str = "BTC,SOL") -> Dict[str, Any]:
        """
        Fetch cryptocurrency data from CoinMarketCap API
        
        Args:
            symbols: Comma-separated list of cryptocurrency symbols
            
        Returns:
            Dictionary with cryptocurrency data or empty dict on failure
        """
        cache_key = symbols
        current_time = time.time()
        
        # Check if we have cached data that hasn't expired
        if cache_key in self.cache and self.cache_expiry.get(cache_key, 0) > current_time:
            logger.info(f"Using cached data for {symbols}")
            return self.cache[cache_key]
        
        if not self.api_key:
            logger.error("Cannot fetch crypto data: No API key provided")
            return {}
        
        try:
            params = {
                'symbol': symbols,
                'convert': 'USD'
            }
            
            headers = {
                'X-CMC_PRO_API_KEY': self.api_key,
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.base_url, 
                    params=params, 
                    headers=headers, 
                    timeout=10
                ) as response:
                    if response.status != 200:
                        logger.error(f"API request failed with status {response.status}")
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text[:200]}")
                        return {}
                    
                    data = await response.json()
                    
                    if 'data' not in data:
                        logger.error(f"Unexpected API response format: {data}")
                        return {}
                    
                    # Process and cache the result
                    result = {}
                    for symbol in symbols.split(','):
                        if symbol in data['data']:
                            crypto_data = data['data'][symbol]
                            quote = crypto_data['quote']['USD']
                            result[symbol] = {
                                'id': crypto_data['id'],
                                'name': crypto_data['name'],
                                'symbol': crypto_data['symbol'],
                                'price': Decimal(str(quote['price'])),
                                'market_cap': Decimal(str(quote['market_cap'])),
                                'percent_change_24h': Decimal(str(quote['percent_change_24h'])),
                                'volume_24h': Decimal(str(quote['volume_24h'])),
                                'last_updated': quote['last_updated']
                            }
                    
                    # Cache the result
                    self.cache[cache_key] = result
                    self.cache_expiry[cache_key] = current_time + self.cache_duration
                    
                    logger.info(f"Successfully fetched and cached data for {symbols}")
                    return result
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during API request: {e}")
        except ValueError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching crypto data: {e}")
        
        return {}
    
    def format_market_cap(self, market_cap: Decimal) -> str:
        """Format market cap value for human-readable output"""
        if market_cap >= 1_000_000_000_000:  # Trillion
            return f"${market_cap / 1_000_000_000_000:.2f}T"
        elif market_cap >= 1_000_000_000:  # Billion
            return f"${market_cap / 1_000_000_000:.2f}B"
        elif market_cap >= 1_000_000:  # Million
            return f"${market_cap / 1_000_000:.2f}M"
        else:
            return f"${market_cap:.2f}"
    
    async def get_formatted_marketcap_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get formatted marketcap data for a specific cryptocurrency symbol
        
        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC", "SOL")
            
        Returns:
            Dictionary with formatted marketcap data or None on failure
        """
        try:
            data = await self.get_crypto_data(symbol)
            if not data or symbol not in data:
                logger.warning(f"No data found for {symbol}")
                return None
            
            crypto_data = data[symbol]
            formatted_market_cap = self.format_market_cap(crypto_data['market_cap'])
            
            return {
                "ticker": f"${symbol}",
                "value": crypto_data['market_cap'],
                "formatted_value": formatted_market_cap,
                "name": crypto_data['name'],
                "price": crypto_data['price'],
                "percent_change_24h": crypto_data['percent_change_24h']
            }
            
        except Exception as e:
            logger.error(f"Error formatting marketcap data for {symbol}: {e}")
            return None 