# src/twitter_bot/twitter_bot.py

import logging
import time
import random
from datetime import datetime
from pathlib import Path
import json
import os
from dotenv import load_dotenv
from src.ai_generator import AIGenerator
from .scraper import Scraper
from .tweets import TweetManager
from src.announcement_broadcaster import AnnouncementBroadcaster
from .twitter_service import twitter_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TwitterBot')

class TwitterBot:
    def __init__(self, handle_signals=False, initialize_now=True):
        logger.info("Initializing Twitter bot...")
        
        # Get the absolute path to the .env file
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / '.env'
        
        logger.info("Loading environment variables...")
        if not load_dotenv(dotenv_path=env_path, override=True):
            raise ValueError(f"Could not load .env file from {env_path}")
        
        # Initialize components
        self.generator = AIGenerator(mode='twitter')
        self.proxy = os.getenv("PROXY_URL")
        self.running = False
        self.is_cleaning_up = False
        
        # Reference to the twitter service (not creating our own anymore)
        self.service = twitter_service
        
        # Only initialize if requested
        if initialize_now:
            self.initialize()
        
        logger.info("Twitter bot initialization complete!")

    def initialize(self) -> bool:
        """Initialize the Twitter bot components"""
        try:
            if not self.generator:
                logger.error("AI Generator not initialized")
                return False

            # Initialize the twitter service
            if not self.service.is_initialized():
                # For the main bot, use default port
                os.environ.pop("REMOTE_DEBUGGING_PORT", None)  # Remove if set
                
                # Initialize the service
                initialization_success = self.service.initialize(proxy_url=self.proxy)
                
                if not initialization_success:
                    logger.error("Failed to initialize Twitter service")
                    return False
            
            # Set up broadcaster with the service's driver
            if self.service.driver:
                from src.announcement_broadcaster import AnnouncementBroadcaster
                AnnouncementBroadcaster.set_twitter_driver(self.service.driver)
                
            # Verify all components
            if not all([self.generator, self.service.is_initialized()]):
                logger.error("Not all components initialized properly")
                return False
                
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Twitter bot: {e}")
            return False

    def run(self):
        """Run the main loop of the Twitter bot"""
        try:
            logger.info("Initializing Twitter bot components...")
            if not self.initialize():
                logger.error("Failed to initialize Twitter bot components")
                return

            logger.info("Twitter bot initialized successfully!")
            self.running = True
            
            # Execute initial tasks
            logger.info("=== Initial Tasks ===")
            if self.service.get_tweet_manager() and self.generator:
                self.service.get_tweet_manager().check_and_process_mentions(self.generator)
                self.generate_and_send_tweet()
            
            # Set timers
            last_tweet_time = time.time()
            last_notification_check = time.time()
            tweet_interval = random.randint(1200, 3600)  # 5-30 minutes
            notification_interval = 300  # 5 minutes

            logger.info(f"Next tweet in {tweet_interval/60:.1f} minutes")
            logger.info(f"Next notification check in {notification_interval/60:.1f} minutes")

            while self.running:
                try:
                    if not all([self.generator, self.service.is_initialized()]):
                        logger.error("Critical components lost during runtime")
                        if not self.initialize():  # Try to reinitialize
                            logger.error("Could not recover components")
                            break

                    current_time = time.time()

                    if self.is_cleaning_up:
                        logger.info("Cleanup in progress. Exiting run loop.")
                        break

                    # Check notifications
                    if current_time - last_notification_check >= notification_interval:
                        logger.info("=== Checking Notifications ===")
                        tweet_manager = self.service.get_tweet_manager()
                        if tweet_manager and self.generator:
                            try:
                                tweet_manager.check_and_process_mentions(self.generator)
                            except Exception as e:
                                logger.error(f"Error checking notifications: {e}")
                        last_notification_check = current_time
                        logger.info(f"Next notification check in {notification_interval/60:.1f} minutes")

                    # Check for verification screens periodically
                    if self.service.scraper and self.service.scraper.is_verification_screen():
                        logger.warning("Verification screen detected during operation")
                        verification_success = self.service.scraper.handle_verification_screen()
                        
                        if verification_success:
                            logger.info("Verification completed, continuing normal operation")
                        else:
                            logger.warning("Verification failed or timed out, will retry on next cycle")
                            
                        # Skip the rest of this cycle
                        continue

                    # Post tweets
                    if current_time - last_tweet_time >= tweet_interval:
                        logger.info("=== Generating Tweet ===")
                        try:
                            self.generate_and_send_tweet()
                        except Exception as e:
                            logger.error(f"Error generating tweet: {e}")
                        last_tweet_time = current_time
                        tweet_interval = random.randint(2600, 3600)
                        logger.info(f"Next tweet in {tweet_interval/60:.1f} minutes")

                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Error in run loop: {e}")
                    time.sleep(10)

        except Exception as e:
            logger.error(f"Critical error in Twitter bot: {e}")
        finally:
            self.stop()
            if not self.is_cleaning_up:
                self.cleanup()

    def generate_and_send_tweet(self):
        """Generate and send a tweet"""
        tweet_manager = self.service.get_tweet_manager()
        if not all([self.generator, tweet_manager]):
            logger.error("Cannot generate and send tweet - missing components")
            return

        try:
            # Check for verification before attempting to tweet
            if self.service.scraper and self.service.scraper.is_verification_screen():
                logger.warning("Verification screen detected before tweeting")
                verification_success = self.service.scraper.handle_verification_screen()
                
                if not verification_success:
                    logger.warning("Tweet generation postponed due to verification issues")
                    return
            
            # Generate content using AIGenerator - no topic needed
            content = self.generator.generate_content(
                conversation_context='',
                username=''
            )

            if not content or not isinstance(content, str):
                logger.error("No valid content generated")
                return

            # Sanitize content before sending
            content = tweet_manager.sanitize_text(content)

            # Use the service to queue the tweet
            self.service.send_tweet(content, priority=1, source="automated")
            logger.info("Tweet queued successfully")

        except Exception as e:
            logger.error(f"Error generating/sending tweet: {e}")

    def stop(self):
        """Stop the bot gracefully"""
        logger.info("Stopping Twitter bot...")
        self.running = False
        self.is_cleaning_up = True

    def cleanup(self):
        """Cleanup resources"""
        if self.is_cleaning_up:
            logger.info("Cleanup already in progress.")
            return

        self.is_cleaning_up = True
        try:
            logger.info("Starting cleanup process...")
            self.running = False
            
            # Service is now shared, so we don't close it here
            # Just indicate that the bot is no longer using it
            logger.info("TwitterBot no longer active, but service remains available")
            
            logger.info("Cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_tweet_manager(self):
        """Get the tweet manager, initializing if needed"""
        if not self.service.is_initialized():
            if not self.initialize():
                raise Exception("Could not initialize Twitter bot components")
        return self.service.get_tweet_manager()
