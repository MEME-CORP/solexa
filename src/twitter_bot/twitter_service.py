import logging
import time
import threading
import queue
from typing import Optional, Dict, Any
from selenium.webdriver.remote.webdriver import WebDriver

from .scraper import Scraper
from .tweets import TweetManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TwitterService')

class TwitterService:
    """
    Singleton service for managing Twitter interactions through a single browser instance.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                logger.info("Creating TwitterService singleton instance")
                cls._instance = super(TwitterService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        logger.info("Initializing TwitterService")
        self.scraper = None
        self.tweet_manager = None
        self.driver = None
        self.is_initializing = False
        self.tweet_queue = queue.Queue()
        self.processing_thread = None
        self.running = False
        self._initialized = True
    
    def initialize(self, proxy_url=None) -> bool:
        """Initialize the Twitter service components"""
        if self.is_initializing:
            logger.info("Initialization already in progress")
            return False
            
        if self.scraper and self.tweet_manager:
            logger.info("TwitterService already initialized")
            return True
            
        try:
            self.is_initializing = True
            logger.info("Initializing Twitter components")
            
            # Initialize scraper with browser
            self.scraper = Scraper(proxy=proxy_url)
            initialization_success = self.scraper.initialize()
            
            # Check if verification screen is detected
            if not initialization_success and self.scraper and self.scraper.driver:
                if self.scraper.is_verification_screen():
                    logger.warning("Verification required during initialization")
                    verification_success = self.scraper.handle_verification_screen()
                    
                    if verification_success:
                        # Complete login after verification
                        if self.scraper.auth and self.scraper.auth.complete_login_after_verification():
                            logger.info("Successfully logged in after verification")
                            initialization_success = True
                        else:
                            logger.error("Failed to complete login after verification")
                    else:
                        logger.error("Verification failed or timed out")
            
            if not initialization_success:
                logger.error("Failed to initialize scraper")
                self.is_initializing = False
                return False
                
            # Store reference to the driver
            self.driver = self.scraper.driver
            
            # Initialize tweet manager
            self.tweet_manager = TweetManager(self.driver)
            
            # Start the tweet processing thread
            self.running = True
            self.processing_thread = threading.Thread(target=self._process_tweet_queue, daemon=True)
            self.processing_thread.start()
            
            logger.info("TwitterService initialized successfully")
            self.is_initializing = False
            return True
            
        except Exception as e:
            logger.error(f"Error initializing TwitterService: {e}")
            self.is_initializing = False
            return False
    
    def get_driver(self) -> Optional[WebDriver]:
        """Get the WebDriver instance"""
        return self.driver
    
    def get_tweet_manager(self) -> Optional[TweetManager]:
        """Get the TweetManager instance"""
        return self.tweet_manager
    
    def send_tweet(self, content: str, priority: int = 1, source: str = "unknown") -> bool:
        """
        Queue a tweet to be sent
        
        Args:
            content: The tweet content
            priority: Priority level (lower numbers = higher priority)
            source: Source of the tweet request (e.g., "web", "automated")
            
        Returns:
            bool: Whether the tweet was successfully queued
        """
        try:
            # Ensure service is initialized
            if not self.is_initialized():
                logger.warning("TwitterService not initialized, initializing now")
                if not self.initialize():
                    logger.error("Failed to initialize TwitterService")
                    return False
            
            # Add to queue
            tweet_data = {
                "content": content,
                "priority": priority,
                "source": source,
                "timestamp": time.time()
            }
            
            self.tweet_queue.put(tweet_data)
            logger.info(f"Tweet from {source} queued (queue size: {self.tweet_queue.qsize()})")
            
            # If it's a high priority tweet (from web UI), process immediately
            if priority == 0 and self.tweet_manager:
                # Direct processing for immediate feedback
                try:
                    self.tweet_manager.send_tweet(content)
                    logger.info(f"High priority tweet from {source} sent immediately")
                    return True
                except Exception as e:
                    logger.error(f"Error sending high priority tweet: {e}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error queuing tweet: {e}")
            return False
    
    def _process_tweet_queue(self):
        """Background thread to process queued tweets"""
        logger.info("Tweet queue processor started")
        
        while self.running:
            try:
                # Process any tweets in the queue
                if not self.tweet_queue.empty() and self.tweet_manager:
                    tweet_data = self.tweet_queue.get(timeout=1)
                    
                    try:
                        logger.info(f"Processing queued tweet from {tweet_data['source']}")
                        self.tweet_manager.send_tweet(tweet_data["content"])
                        logger.info(f"Successfully sent queued tweet from {tweet_data['source']}")
                    except Exception as e:
                        logger.error(f"Error processing queued tweet: {e}")
                    finally:
                        self.tweet_queue.task_done()
                else:
                    # No tweets to process, sleep
                    time.sleep(5)
                    
            except queue.Empty:
                # No tweets in queue, continue
                pass
            except Exception as e:
                logger.error(f"Error in tweet queue processor: {e}")
                time.sleep(10)  # Sleep on error to avoid tight loop
    
    def is_initialized(self) -> bool:
        """Check if the service is initialized"""
        return self.scraper is not None and self.tweet_manager is not None
    
    def close(self):
        """Close the service and clean up resources"""
        self.running = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            logger.info("Waiting for tweet processor to finish")
            self.processing_thread.join(timeout=30)
        
        if self.scraper:
            logger.info("Closing scraper")
            try:
                self.scraper.close()
            except Exception as e:
                logger.error(f"Error closing scraper: {e}")
            finally:
                self.scraper = None
                self.driver = None
                self.tweet_manager = None
                
        logger.info("TwitterService closed")

# Create singleton instance
twitter_service = TwitterService() 