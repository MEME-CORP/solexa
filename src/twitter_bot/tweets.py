from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import List
import os
import logging
from pathlib import Path
from src.database.supabase_client import DatabaseService
import re

class TweetManager:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.logger = logging.getLogger('TweetManager')
        self.processed_tweets = set()
        self.db = DatabaseService()
        self.load_processed_tweets()
        
        # Process any pending tweets right after initialization
        self._process_pending_announcements()

    def _process_pending_announcements(self):
        """Process any pending announcements right after initialization"""
        from src.announcement_broadcaster import AnnouncementBroadcaster
        
        if not hasattr(AnnouncementBroadcaster, '_pending_tweets'):
            return
            
        pending = AnnouncementBroadcaster._pending_tweets[:]  # Make a copy
        
        for message in pending:
            try:
                self.send_tweet(message)
                AnnouncementBroadcaster._pending_tweets.remove(message)
                self.logger.info(f"Successfully posted pending announcement: {message[:30]}...")
            except Exception as e:
                self.logger.error(f"Failed to post pending announcement: {e}")

    def load_processed_tweets(self):
        """Load processed tweet IDs from database"""
        try:
            tweet_ids = self.db.get_processed_tweets()
            self.processed_tweets = set(tweet_ids)
            self.logger.info(f"Loaded {len(self.processed_tweets)} processed tweet IDs")
        except Exception as e:
            self.logger.error(f"Error loading processed tweets: {e}")
            self.processed_tweets = set()

    def save_processed_tweets(self):
        """Save processed tweet IDs to database"""
        try:
            # Convert set to list for database storage
            tweet_ids = list(self.processed_tweets)
            
            # Store in database using existing db service
            for tweet_id in tweet_ids:
                self.db.add_processed_tweet(tweet_id)
                
            self.logger.info(f"Saved {len(tweet_ids)} processed tweet IDs to database")
        except Exception as e:
            self.logger.error(f"Error saving processed tweets: {e}")

    def extract_tweet_id(self, article) -> str:
        """Extract tweet ID from article element"""
        try:
            timestamp = article.find_element(By.CSS_SELECTOR, "time").find_element(By.XPATH, "./..")
            url = timestamp.get_attribute("href")
            return url.split("/status/")[1]
        except Exception as e:
            self.logger.error(f"Error extracting tweet ID: {e}")
            return None

    def has_already_replied(self, article) -> bool:
        """Check if we've already replied to this tweet"""
        try:
            username = os.getenv("TWITTER_USERNAME", "agent47ai").lower()
            
            try:
                timestamp = article.find_element(By.CSS_SELECTOR, "time").find_element(By.XPATH, "./..")
                self.driver.execute_script("arguments[0].click();", timestamp)
                time.sleep(2)
                
                replies = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                
                for reply in replies:
                    try:
                        author_element = reply.find_element(By.CSS_SELECTOR, "[data-testid='User-Name']")
                        if f"@{username}" in author_element.text.lower():
                            self.logger.info(f"Found existing reply from {username}")
                            return True
                    except:
                        continue
                
                self.driver.get("https://twitter.com/notifications/mentions")
                time.sleep(2)
                return False
                
            except Exception as e:
                self.logger.error(f"Error checking replies in article: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in has_already_replied: {e}")
            return False

    def clear_text_box(self) -> None:
        try:
            tweet_box = self.driver.find_element(By.XPATH, "//div[@aria-label='Post text']")
            tweet_box.send_keys('\ue009' + 'a')  # Ctrl+A
            tweet_box.send_keys('\ue003')  # Backspace
            time.sleep(0.5)
        except:
            pass

    def send_tweet(self, content: str) -> None:
        """Send a new tweet with enhanced error handling and selectors"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1} to send tweet...")
                
                # Navigate to home page
                self.logger.info("Navigating to home page...")
                self.driver.get("https://twitter.com/home")
                time.sleep(3)
                
                # Core working selectors from proven implementation
                tweet_box_selectors = [
                    ("xpath", "//div[@aria-label='Post text']"),
                    ("xpath", "//div[@aria-label='Tweet text']"),
                    ("css", "div[aria-label='Post text']"),
                    ("css", "div[data-testid='tweetTextarea_0']"),
                    ("css", "div[role='textbox'][aria-label='Post text']")
                ]
                
                # Find tweet box using proven selectors
                tweet_box = None
                for method, selector in tweet_box_selectors:
                    try:
                        self.logger.debug(f"Trying selector: {selector}")
                        if method == "xpath":
                            tweet_box = self.driver.find_element(By.XPATH, selector)
                        else:
                            tweet_box = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if tweet_box and tweet_box.is_displayed():
                            self.logger.info(f"Found tweet box with selector: {selector}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Selector {selector} failed: {str(e)}")
                        continue
                
                if not tweet_box:
                    raise Exception("Could not find tweet input box")
                
                # Click and clear the input box
                self.logger.info("Clicking tweet box...")
                self.driver.execute_script("arguments[0].click();", tweet_box)
                time.sleep(1)
                self.clear_text_box()
                
                # Input content
                self.logger.info("Entering tweet content...")
                tweet_box.send_keys(content)
                time.sleep(1)
                
                # Use proven button selectors
                button_selectors = [
                    ("css", "[data-testid='tweetButton']"),
                    ("css", "div[role='button'][data-testid='tweetButtonInline']"),
                    ("css", "div.css-175oi2r.r-kemksi.r-jumn1c.r-xd6kpl.r-gtdqiz.r-ipm5af.r-184en5c > div:nth-child(2) > div > div > div > button"),
                    # Add new selectors to match current Twitter UI
                    ("css", "button[data-testid='tweetButtonInline']"),
                    ("css", "[data-testid='tweetButtonInline']")
                ]
                
                # Find post button
                post_button = None
                for method, selector in button_selectors:
                    try:
                        self.logger.debug(f"Trying button selector: {selector}")
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                post_button = element
                                self.logger.info(f"Found post button with selector: {selector}")
                                break
                        if post_button:
                            break
                    except Exception as e:
                        self.logger.debug(f"Button selector {selector} failed: {str(e)}")
                        continue
                
                if not post_button:
                    raise Exception("Could not find post button")
                
                # Click post button
                self.logger.info("Clicking post button...")
                self.driver.execute_script("arguments[0].click();", post_button)
                time.sleep(2)
                
                self.logger.info("Tweet posted successfully")
                return
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info("Retrying...")
                    time.sleep(2)
                    continue
                raise Exception(f"Failed to send tweet after {max_retries} attempts: {str(e)}")

    def clean_content(self, content: str) -> str:
        """Clean tweet content"""
        # Remove only specific markers if present, otherwise keep full content
        if "**()" in content:
            content = content.split("**()")[0].strip()
        return content.strip()

    def sanitize_text(self, text: str) -> str:
        """Sanitize text"""
        text = self.clean_content(text)
        return ''.join(char for char in text if ord(char) < 0xFFFF)

    def reply_to_tweet(self, tweet_data: dict, content: str) -> None:
        """Reply to a tweet"""
        max_retries = 3
        success = False
        
        try:
            # Sanitize content and remove self-mentions
            content = self.sanitize_text(content)
            username = os.getenv("TWITTER_USERNAME", "agent47ai").lower()
            
            # Remove @username mentions from the reply content
            content = re.sub(f"@{username}\\b", "", content, flags=re.IGNORECASE)
            content = content.strip()
            
            self.logger.info(f"Replying with content: {content}")
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        self.driver.get("https://twitter.com/notifications")
                        time.sleep(3)
                    
                    articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                    target_article = None
                    
                    for article in articles:
                        try:
                            tweet_id = self.extract_tweet_id(article)
                            if tweet_id == tweet_data['tweet_id']:
                                target_article = article
                                break
                        except:
                            continue
                    
                    if not target_article:
                        raise Exception("Could not find target tweet")
                    
                    reply_button = target_article.find_element(By.CSS_SELECTOR, "[data-testid='reply']")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", reply_button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", reply_button)
                    time.sleep(2)
                    
                    editor = self.driver.find_element(By.CSS_SELECTOR, "div[data-testid='tweetTextarea_0']")
                    self.driver.execute_script("arguments[0].click();", editor)
                    time.sleep(1)
                    
                    editor.send_keys('\ue009' + 'a')
                    editor.send_keys('\ue003')
                    time.sleep(1)
                    
                    editor.send_keys(content)
                    time.sleep(1)
                    
                    post_button = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='tweetButton']")
                    self.driver.execute_script("arguments[0].click();", post_button)
                    time.sleep(3)
                    
                    success = True
                    self.logger.info(f"Successfully replied to tweet {tweet_data['tweet_id']}")
                    break
                    
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise
                
            if success:
                self.mark_tweet_processed(tweet_data['tweet_id'])
                self.logger.info(f"Marked tweet {tweet_data['tweet_id']} as processed")
                
        except Exception as e:
            self.logger.error(f"Error replying to tweet: {e}")
        finally:
            self.logger.info("Returning to notifications page...")
            self.driver.get("https://twitter.com/notifications")
            time.sleep(3)

    def check_notifications(self) -> List[dict]:
        """Check notifications for mentions"""
        try:
            self.driver.get("https://twitter.com/notifications")
            time.sleep(5)
            
            username = os.getenv("TWITTER_USERNAME", "agent47ai").lower()
            self.logger.info(f"Checking notifications for @{username}")
            
            notifications = []
            processed_count = 0
            max_scroll_attempts = 5
            scroll_attempt = 0
            
            while scroll_attempt < max_scroll_attempts:
                articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                self.logger.info(f"Found {len(articles)} articles, processed {processed_count}")
                
                if processed_count >= len(articles):
                    break
                
                for article in articles[processed_count:]:
                    try:
                        tweet_id = self.extract_tweet_id(article)
                        if not tweet_id or self.is_tweet_processed(tweet_id):
                            continue
                        
                        tweet_text = article.find_element(By.CSS_SELECTOR, "div[data-testid='tweetText']").text
                        
                        if f"@{username}" in tweet_text.lower():
                            notifications.append({
                                "text": tweet_text,
                                "tweet_id": tweet_id,
                                "element": article
                            })
                    except Exception as e:
                        self.logger.error(f"Error processing article: {e}")
                        continue
                
                processed_count = len(articles)
                
                if articles:
                    try:
                        last_article = articles[-1]
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", last_article)
                        time.sleep(2)
                        scroll_attempt += 1
                    except Exception as e:
                        self.logger.error(f"Error scrolling: {e}")
                        break
                else:
                    break

            self.logger.info(f"Found {len(notifications)} new mentions")
            return notifications

        except Exception as e:
            self.logger.error(f"Error checking notifications: {e}")
            return []

    def check_and_process_mentions(self, generator):
        """Check and process mentions"""
        try:
            notifications = self.check_notifications()
            
            if notifications:
                self.logger.info(f"Processing {len(notifications)} mentions...")
                for notification in notifications:
                    try:
                        reply_content = generator.generate_content(
                            user_message=f"reply to: {notification['text']}", 
                            topic='',
                            conversation_context='',
                            username=''
                        )
                        
                        if reply_content and isinstance(reply_content, str):
                            self.logger.info(f"Generated reply: {reply_content[:50]}...")
                            self.reply_to_tweet(notification, reply_content)
                            self.processed_tweets.add(notification['tweet_id'])
                            self.save_processed_tweets()
                            self.logger.info(f"Replied to tweet ID: {notification['tweet_id']}")
                            time.sleep(2)
                    except Exception as e:
                        self.logger.error(f"Error processing notification: {e}")
                        continue
            else:
                self.logger.info("No new mentions to process")
                
        except Exception as e:
            self.logger.error(f"Error in check_and_process_mentions: {e}")

    def is_tweet_processed(self, tweet_id: str) -> bool:
        """Check if a tweet has already been processed"""
        return tweet_id in self.processed_tweets

    def mark_tweet_processed(self, tweet_id: str) -> None:
        """Mark a tweet as processed and save to database"""
        if not tweet_id:
            return
            
        self.processed_tweets.add(tweet_id)
        try:
            # Save individual tweet right after processing
            self.db.add_processed_tweet(tweet_id)
            self.logger.info(f"Marked tweet {tweet_id} as processed")
        except Exception as e:
            self.logger.error(f"Error marking tweet as processed: {e}")