import os
import json
import logging
import requests
import time
from typing import Optional, Tuple, Dict, List
from pathlib import Path
from decimal import Decimal
import aiohttp
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WalletManager')

class WalletManager:
    def __init__(self, api_url: str = "https://web3-agent.onrender.com"):
        """Initialize WalletManager with API URL"""
        self.api_url = api_url
        self.data_dir = Path("data")
        self.wallet_file = self.data_dir / "wallet_credentials.json"
        self.request_timeout = 30  # Default timeout in seconds
        
        # Create data directory if it doesn't exist
        self.data_dir.mkdir(exist_ok=True)
        
        # Load or create wallet credentials
        self.wallet_credentials = self._load_wallet_credentials()

    def generate_new_wallet(self) -> Tuple[bool, Optional[dict]]:
        """Generate a new wallet using the API or return existing credentials"""
        existing_creds = self.get_wallet_credentials()
        if existing_creds and existing_creds.get('public_key') and existing_creds.get('private_key'):
            logger.info(f"Using existing wallet: {existing_creds['public_key']}")
            return True, {
                'publicKey': existing_creds['public_key'],
                'privateKey': existing_creds['private_key']
            }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating wallet (attempt {attempt + 1}/{max_retries})...")
                response = requests.post(
                    f"{self.api_url}/generate-wallet",
                    headers={"Content-Type": "application/json"},
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success' and data.get('wallet'):
                        wallet_data = data['wallet']
                        if all(k in wallet_data for k in ['publicKey', 'privateKey']):
                            logger.info(f"Successfully generated wallet: {wallet_data['publicKey']}")
                            if self.set_wallet_credentials(
                                public_key=wallet_data['publicKey'],
                                private_key=wallet_data['privateKey'],
                                secret_key=wallet_data['privateKey']  # Using private as secret
                            ):
                                logger.info("Successfully stored wallet credentials")
                            else:
                                logger.error("Failed to store wallet credentials")
                            return True, wallet_data
                        logger.error("Wallet data missing required keys")
                
                elif response.status_code == 502:
                    logger.warning(f"Server error (502) on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                
                logger.error(f"API request failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response body: {response.text[:200]}")

            except requests.Timeout:
                logger.error(f"Request timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            except requests.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return False, None

        return False, None

    def transfer_sol(self, from_wallet: str, to_wallet: str, amount: Decimal) -> Tuple[bool, Optional[str]]:
        """Transfer SOL from one wallet to another"""
        try:
            if amount <= Decimal('0'):
                raise ValueError("Amount must be greater than 0")
                
            creds = self.get_wallet_credentials()
            if not creds.get('private_key') or not creds.get('public_key'):
                raise ValueError("No wallet credentials found")

            payload = {
                "fromPrivateKey": creds['private_key'],
                "fromPublicKey": from_wallet,
                "toAddress": to_wallet,
                "amount": float(amount)
            }
            
            response = requests.post(
                f"{self.api_url}/trigger",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info(f"Successfully transferred {amount} SOL to {to_wallet}")
                    return True, data.get('signature')
                else:
                    logger.error(f"API error: {data.get('message')}")
            else:
                logger.error(f"Transfer failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response: {response.text[:200]}")

            return False, None

        except Exception as e:
            logger.error(f"Error in transfer_sol: {str(e)}")
            return False, None

    async def check_balance(self, wallet_address: str, mint_address: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """Check wallet balance for both SOL and tokens"""
        try:
            payload = {
                "publicKey": wallet_address,
                "mintAddress": mint_address
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/check-balance",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.request_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success':
                            result = {
                                'sol': {
                                    'balance': Decimal(str(data['solBalance']['balance'])),
                                    'lamports': data['solBalance']['lamports']
                                }
                            }
                            if data.get('tokenBalance') and not data['tokenBalance'].get('error'):
                                result['token'] = {
                                    'balance': Decimal(str(data['tokenBalance']['balance'])),
                                    'decimals': data['tokenBalance']['decimals'],
                                    'mint': data['tokenBalance']['mint']
                                }
                            return True, result
                    
                    logger.error(f"Balance check failed: {response.status}")
                    return False, None

        except Exception as e:
            logger.error(f"Error checking balance: {str(e)}")
            return False, None

    def check_mint_balance(self, mint_address: str) -> Tuple[bool, Optional[Dict]]:
        """Check mint balance and supply information"""
        try:
            response = requests.post(
                f"{self.api_url}/check-mint-balance",
                json={"mintAddress": mint_address},
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, {
                        'balance': Decimal(str(data['balance'])),
                        'decimals': data['decimals'],
                        'rawAmount': data['rawAmount']
                    }
            return False, None
        except Exception as e:
            logger.error(f"Error checking mint balance: {str(e)}")
            return False, None

    def check_transfers(self, from_address: str, to_address: str, 
                       before_time: Optional[int] = None, 
                       after_time: Optional[int] = None) -> Tuple[bool, Optional[List]]:
        """Check transfer history between wallets"""
        try:
            payload = {
                "fromAddress": from_address,
                "toAddress": to_address,
                "beforeTime": before_time,
                "afterTime": after_time
            }
            response = requests.post(
                f"{self.api_url}/check-transfers",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, data.get('transfers', [])
            return False, None
        except Exception as e:
            logger.error(f"Error checking transfers: {str(e)}")
            return False, None

    def get_holder_percentage(self, mint_address: str, holder_address: str) -> Tuple[bool, Optional[Dict]]:
        """Get holder's percentage of total supply"""
        try:
            payload = {
                "mintAddress": mint_address,
                "holderAddress": holder_address
            }
            response = requests.post(
                f"{self.api_url}/holder-percentage",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, data.get('data')
            return False, None
        except Exception as e:
            logger.error(f"Error getting holder percentage: {str(e)}")
            return False, None

    async def burn_tokens(self, from_private_key: str, from_public_key: str,
                          mint_address: str, amount: Decimal, decimals: int) -> Tuple[bool, Optional[str]]:
        """
        Burn tokens using /burn-tokens endpoint, 
        ensuring at most 1 transaction is sent per second.
        """
        try:
            if amount <= Decimal('0'):
                raise ValueError("Burn amount must be greater than 0")
            
            payload = {
                "fromPrivateKey": from_private_key,
                "fromPublicKey": from_public_key,
                "mintAddress": mint_address,
                "amount": str(amount),
                "decimals": decimals
            }
            
            # Wait 1 second before sending the burn request (rate-limit approach)
            await asyncio.sleep(61)

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                for attempt in range(3):
                    try:
                        logger.info(f"Sending burn request (attempt {attempt+1}) for {amount} tokens...")
                        async with session.post(
                            f"{self.api_url}/burn-tokens",
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data.get('status') == 'success':
                                    logger.info(f"Successfully burned {amount} tokens (attempt {attempt+1})")
                                    return True, data.get('signature')
                                else:
                                    logger.error(f"Burn API error: {data.get('message')}")
                            else:
                                error_text = await response.text()
                                logger.error(f"Burn request failed with status {response.status}: {error_text}")
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout while burning tokens (attempt {attempt+1})")
                    except aiohttp.ClientError as e:
                        logger.error(f"Network error while burning tokens: {e}")
                    
                    # Wait 1 second between attempts
                    await asyncio.sleep(1)
                    
            return False, None
        except Exception as e:
            logger.error(f"Error burning tokens: {e}")
            return False, None

    async def buy_tokens(self, private_key: str, token_address: str, 
                         amount_usd: Decimal = Decimal('0.1')) -> Tuple[bool, Optional[Dict]]:
        """
        Buy tokens using Jupiter swap.
        
        - If `amount_usd` < 0.001, force it to 0.001 to avoid 'Bad Request' from Jupiter.
        - Check your environment variables and server logs if you still get 'Bad Request'.
        """
        try:
            if amount_usd < Decimal('0.001'):
                logger.warning(f"Requested amount {amount_usd} is too small. Forcing to 0.001 USD.")
                amount_usd = Decimal('0.001')

            payload = {
                "privateKey": private_key,
                "tokenAddress": token_address,
                "amountUSD": float(amount_usd)
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                try:
                    await asyncio.sleep(2)
                    async with session.post(
                        f"{self.api_url}/buy-tokens",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'success':
                                logger.info(f"Successfully bought tokens via Jupiter swap (amount={amount_usd} USD)")
                                return True, data.get('data')
                            else:
                                logger.error(f"Buy error from server: {data.get('message')}")
                        else:
                            error_text = await response.text()
                            logger.error(f"Buy request failed: {response.status}, {error_text}")
                except asyncio.TimeoutError:
                    logger.error("Timeout while buying tokens")
                except aiohttp.ClientError as e:
                    logger.error(f"Network error while buying tokens: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error buying tokens: {e}")
            return False, None

    async def get_token_price(self, mint_address: str) -> Tuple[bool, Optional[dict]]:
        """Get token price from Jupiter API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.jup.ag/price/v2?ids={mint_address}&showExtraInfo=true"
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Error getting token price: {response.status}")
                        return False, None
                    data = await response.json()
                    if not data.get('data') or not data['data'].get(mint_address):
                        logger.error("No price data available for token")
                        return False, None
                    token_data = data['data'][mint_address]
                    return True, {
                        'price': Decimal(str(token_data['price'])),
                        'type': token_data['type'],
                        'extra_info': token_data.get('extraInfo'),
                        'last_updated': token_data.get('lastUpdated')
                    }
        except Exception as e:
            logger.error(f"Error in get_token_price: {e}")
            return False, None

    async def get_token_marketcap(self, mint_address: str) -> Tuple[bool, Optional[Decimal]]:
        """Calculate token marketcap based on price and total supply"""
        try:
            logger.info(f"Fetching marketcap for token: {mint_address}")
            TOTAL_SUPPLY = Decimal('20999909')

            DEFAULT_BONDING_CURVE_MC = Decimal('5000')
            success, price_data = await self.get_token_price(mint_address)
            
            if not success or not price_data:
                logger.info(f"Token {mint_address} appears to be on bonding curve, using default marketcap: {DEFAULT_BONDING_CURVE_MC}")
                return True, DEFAULT_BONDING_CURVE_MC
            
            marketcap = price_data['price'] * TOTAL_SUPPLY
            logger.info(f"Calculated marketcap: {marketcap} (price: {price_data['price']})")
            return True, marketcap
        except Exception as e:
            logger.error(f"Error calculating marketcap: {e}")
            return False, None

    # -------------------------
    # Private helper methods
    # -------------------------
    def _load_wallet_credentials(self) -> dict:
        """Load wallet credentials from file"""
        try:
            if self.wallet_file.exists():
                with open(self.wallet_file, 'r') as f:
                    return json.load(f)
            else:
                credentials = {
                    "public_key": None,
                    "private_key": None,
                    "secret_key": None
                }
                with open(self.wallet_file, 'w') as f:
                    json.dump(credentials, f, indent=4)
                return credentials
        except Exception as e:
            logger.error(f"Error loading wallet credentials: {e}")
            return {}

    def _save_wallet_credentials(self) -> bool:
        """Save wallet credentials to file"""
        try:
            with open(self.wallet_file, 'w') as f:
                json.dump(self.wallet_credentials, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving wallet credentials: {e}")
            return False

    def set_wallet_credentials(self, public_key: str, private_key: str, secret_key: str) -> bool:
        """Set wallet credentials and ensure they are saved to file"""
        try:
            self.wallet_credentials = {
                "public_key": public_key,
                "private_key": private_key,
                "secret_key": secret_key
            }
            self.data_dir.mkdir(exist_ok=True)
            with open(self.wallet_file, 'w') as f:
                json.dump(self.wallet_credentials, f, indent=4)
            logger.info(f"Successfully saved wallet credentials to {self.wallet_file}")
            return True
        except Exception as e:
            logger.error(f"Error setting wallet credentials: {e}")
            return False

    def get_wallet_credentials(self) -> dict:
        """Get stored wallet credentials"""
        return self.wallet_credentials
