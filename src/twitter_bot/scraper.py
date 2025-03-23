# src/twitter_bot/scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from typing import Optional
from .authenticator import Authenticator
from .tweets import TweetManager
import logging
import time
import os
from pathlib import Path
from datetime import datetime

# Configure logging
logger = logging.getLogger('Scraper')

class Scraper:
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.driver = None
        self.auth = None
        self.tweets = None

    def _initialize_driver(self) -> bool:
        """Initialize Chrome driver with retry logic"""
        attempts = 3
        for attempt in range(attempts):
            try:
                chrome_options = Options()
                chrome_options.add_argument("--start-maximized")
                
                # Add remote debugging support
                remote_debugging = os.getenv("ENABLE_REMOTE_DEBUGGING", "false").lower() == "true"
                remote_debugging_port = os.getenv("REMOTE_DEBUGGING_PORT", "9222")
                
                if remote_debugging:
                    chrome_options.add_argument(f"--remote-debugging-port={remote_debugging_port}")
                    chrome_options.add_argument("--remote-debugging-address=0.0.0.0")
                    logger.info(f"Remote debugging enabled on port {remote_debugging_port}")
                
                if self.proxy and self.proxy.strip() and self.proxy.lower() != "proxy_url_if_needed":
                    chrome_options.add_argument(f'--proxy-server={self.proxy}')
                
                try:
                    # Try to use webdriver_manager if available
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        self.driver = webdriver.Chrome(
                            service=ChromeService(ChromeDriverManager().install()), 
                            options=chrome_options
                        )
                        logger.info("Successfully initialized Chrome using WebDriver Manager")
                    except ImportError:
                        logger.warning("webdriver_manager not found. Please install with: pip install webdriver-manager")
                        logger.info("Falling back to default Chrome configuration")
                        chrome_options.add_argument("--log-level=3")
                        self.driver = webdriver.Chrome(options=chrome_options)
                        logger.info("Successfully initialized Chrome using default configuration")
                    return True
                    
                except Exception as e:
                    logger.error(f"Failed to initialize Chrome driver: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{attempts} failed: {e}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                if attempt == attempts - 1:
                    return False
                time.sleep(2)
        return False

    def initialize(self) -> bool:
        """Initialize the scraper and authenticate with retry logic"""
        try:
            if not self._initialize_driver():
                logger.error("Failed to initialize driver")
                return False
                
            self.auth = Authenticator(self.driver)
            self.tweets = TweetManager(self.driver)
            
            # Try to load session
            if not self.auth.load_session():
                logger.info("No valid session found, attempting login...")
                if not self.auth.login():
                    # Note: We don't handle verification here anymore
                    # That's handled separately to avoid circular dependency
                    logger.error("Login failed")
                    return False
            
            logger.info("Scraper initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing scraper: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            return False

    def close(self):
        """Close the scraper and cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Driver closed successfully")
        except Exception as e:
            logger.error(f"Error closing driver: {e}")
            # Try to force kill if needed
            try:
                try:
                    import psutil
                    process = psutil.Process(self.driver.service.process.pid)
                    process.kill()
                    logger.info("Process killed using psutil")
                except ImportError:
                    logger.warning("psutil not found. Please install with: pip install psutil")
                    # Fallback to os._exit in extreme cases
                    logger.warning("Using fallback cleanup method")
                    if hasattr(self.driver, 'service') and hasattr(self.driver.service, 'process'):
                        os.kill(self.driver.service.process.pid, 9)
                        logger.info("Process killed using os.kill")
            except Exception as cleanup_error:
                logger.error(f"Failed to force kill process: {cleanup_error}")

    def is_verification_screen(self):
        """Detect if current page is a verification screen asking for code"""
        try:
            # Look for verification elements with a short timeout
            verification_texts = [
                "Sieh in deiner E-Mail nach",  # German
                "Check your email",            # English
                "Bestätigungscode",            # German
                "verification code"            # English
            ]
            
            for text in verification_texts:
                elements = self.driver.find_elements("xpath", f"//*[contains(text(), '{text}')]")
                if elements:
                    return True
                
            # Check for verification input field
            code_fields = self.driver.find_elements("xpath", "//input[contains(@placeholder, 'code') or contains(@placeholder, 'Code')]")
            if code_fields:
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking for verification screen: {e}")
            return False

    def handle_verification_screen(self, timeout_minutes=30):
        """Handle the verification screen by notifying admin and waiting for code entry
        
        Args:
            timeout_minutes: Maximum time to wait for verification in minutes
            
        Returns:
            bool: True if verification was successful, False otherwise
        """
        try:
            if not self.is_verification_screen():
                return True
            
            logger.warning("VERIFICATION REQUIRED: Twitter is asking for a verification code")
            
            # Capture screenshot for remote verification
            screenshot_path = self._capture_verification_screenshot()
            
            # Generate a unique verification session ID
            verification_id = f"verify_{int(time.time())}"
            
            # Store verification status in global registry
            from src.verification_manager import VerificationManager
            VerificationManager.register_verification(
                verification_id=verification_id,
                screenshot_path=screenshot_path,
                driver=self.driver
            )
            
            # Broadcast notification if AnnouncementBroadcaster is available
            try:
                from src.announcement_broadcaster import AnnouncementBroadcaster
                verification_url = os.getenv("ADMIN_BASE_URL", "http://localhost:5000")
                verification_url = f"{verification_url}/admin/verification/{verification_id}"
                
                AnnouncementBroadcaster.broadcast_urgent_message(
                    f"URGENT: Twitter verification code required. Access verification panel at: {verification_url}"
                )
            except Exception as e:
                logger.error(f"Failed to broadcast notification: {e}")
            
            # Wait for code entry with periodic checks
            logger.warning(f"Waiting up to {timeout_minutes} minutes for verification code to be entered")
            max_attempts = timeout_minutes * 6  # Check every 10 seconds
            
            for attempt in range(max_attempts):
                # Check if verification was completed via admin panel
                if VerificationManager.is_verification_completed(verification_id):
                    logger.info("Verification completed successfully via admin panel")
                    return True
                
                # Check if verification screen is still present
                if not self.is_verification_screen():
                    logger.info("Verification completed successfully")
                    VerificationManager.complete_verification(verification_id)
                    return True
                
                # Every minute, remind about the verification
                if attempt % 6 == 0 and attempt > 0:
                    minutes_passed = attempt // 6
                    logger.warning(f"Still waiting for verification code ({minutes_passed}/{timeout_minutes} minutes passed)")
                
                # Sleep for 10 seconds before checking again
                time.sleep(10)
            
            logger.error(f"Verification timeout after {timeout_minutes} minutes")
            VerificationManager.cancel_verification(verification_id)
            return False
            
        except Exception as e:
            logger.error(f"Error handling verification screen: {e}")
            return False

    def _capture_verification_screenshot(self):
        """Capture a screenshot of the verification screen"""
        try:
            screenshots_dir = Path(__file__).parent.parent.parent / "static" / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"verification_{timestamp}.png"
            filepath = screenshots_dir / filename
            
            if self.driver.save_screenshot(str(filepath)):
                logger.info(f"Screenshot saved to {filepath}")
                return str(filepath)
            else:
                logger.error("Failed to save screenshot")
                return None
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return None

    def submit_verification_code(self, code):
        """Submit verification code programmatically"""
        try:
            if not code or not isinstance(code, str):
                logger.error("Invalid verification code")
                return False
            
            # Find and fill the verification code input field
            input_field = None
            
            # Try different selectors for the input field
            selectors = [
                "input[name='text']", 
                "input[placeholder*='code']",
                "input[placeholder*='Code']"
            ]
            
            for selector in selectors:
                try:
                    input_field = self.driver.find_element("css selector", selector)
                    if input_field:
                        break
                except:
                    continue
                
            if not input_field:
                logger.error("Could not find verification code input field")
                return False
            
            # Clear field and enter code
            input_field.clear()
            input_field.send_keys(code)
            
            # Find and click submit button
            submit_button = None
            
            # Try different selectors for the submit button
            button_selectors = [
                "button[type='submit']",
                "button:contains('Next')",
                "button:contains('Verify')",
                "button:contains('Submit')"
            ]
            
            for selector in button_selectors:
                try:
                    submit_button = self.driver.find_element("css selector", selector)
                    if submit_button:
                        break
                except:
                    continue
                
            if not submit_button:
                logger.error("Could not find submit button")
                return False
            
            # Click the button
            submit_button.click()
            logger.info("Verification code submitted")
            
            # Wait a moment for the submission to process
            time.sleep(3)
            
            # Check if verification screen is still present
            if not self.is_verification_screen():
                logger.info("Verification successful")
                return True
            else:
                logger.error("Verification screen still present after code submission")
                return False
            
        except Exception as e:
            logger.error(f"Error submitting verification code: {e}")
            return False
