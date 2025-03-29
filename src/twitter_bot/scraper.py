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
from selenium.webdriver.common.keys import Keys

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
                
                # Always enable headless mode in production environments
                headless = os.getenv("HEADLESS_BROWSER", "true").lower() == "true"
                if headless:
                    chrome_options.add_argument("--headless=new")  # Updated headless flag
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--no-sandbox")  # Required for running in containers
                    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource issues
                    logger.info("Headless mode enabled with container settings")
                
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
                    # For Render and other cloud environments, use chromedriver-autoinstaller
                    try:
                        import chromedriver_autoinstaller
                        chromedriver_autoinstaller.install()
                        logger.info("Chrome driver installed automatically")
                        
                        self.driver = webdriver.Chrome(options=chrome_options)
                        logger.info("Successfully initialized Chrome driver")
                        return True
                        
                    except ImportError:
                        logger.warning("chromedriver_autoinstaller not found. Falling back to webdriver_manager")
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
        """Detect if current page is a verification screen asking for code or email"""
        try:
            # Look for verification elements with a short timeout
            verification_texts = [
                "Sieh in deiner E-Mail nach",  # German
                "Check your email",            # English
                "Bestätigungscode",            # German
                "verification code",           # English
                "Gib deine Telefonnummer oder E-Mail-Adresse ein",  # German email verification
                "Enter your phone number or email address"          # English email verification
            ]
            
            for text in verification_texts:
                elements = self.driver.find_elements("xpath", f"//*[contains(text(), '{text}')]")
                if elements:
                    return True
                
            # Check for verification input field
            code_fields = self.driver.find_elements("xpath", "//input[contains(@placeholder, 'code') or contains(@placeholder, 'Code')]")
            if code_fields:
                return True
            
            # Check for email verification input field
            email_fields = self.driver.find_elements("xpath", "//input[@data-testid='ocfEnterTextTextInput']")
            if email_fields:
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking for verification screen: {e}")
            return False

    def handle_verification_screen(self, timeout_minutes=30):
        """Handle the verification screen by notifying admin and waiting for code entry"""
        try:
            if not self.is_verification_screen():
                return True
            
            logger.warning("VERIFICATION REQUIRED: Twitter is asking for verification")
            
            # Check if it's an email verification screen first
            email_verification_texts = [
                "Gib deine Telefonnummer oder E-Mail-Adresse ein",
                "Enter your phone number or email address"
            ]
            
            for text in email_verification_texts:
                elements = self.driver.find_elements("xpath", f"//*[contains(text(), '{text}')]")
                if elements:
                    logger.info("Detected email verification screen")
                    
                    # Get the email from config
                    from src.config import Config
                    email = Config.TWITTER_EMAIL
                    
                    # Find the input field
                    try:
                        input_field = self.driver.find_element("xpath", "//input[@data-testid='ocfEnterTextTextInput']")
                        if input_field:
                            input_field.clear()
                            input_field.send_keys(email)
                            logger.info(f"Entered email: {email}")
                            
                            # Find and click the continue button
                            try:
                                continue_button = self.driver.find_element("xpath", "//button[@data-testid='ocfEnterTextNextButton']")
                                if continue_button:
                                    continue_button.click()
                                    logger.info("Clicked continue button after entering email")
                                    time.sleep(3)
                                    
                                    # Check if verification screen is still present
                                    if not self.is_verification_screen():
                                        logger.info("Email verification completed successfully")
                                        return True
                                else:
                                    # Try with role and text
                                    try:
                                        continue_button = self.driver.find_element("xpath", "//button[@role='button']//span[contains(text(), 'Weiter')]/..")
                                        continue_button.click()
                                        logger.info("Clicked continue button after entering email (using text)")
                                        time.sleep(3)
                                        
                                        if not self.is_verification_screen():
                                            logger.info("Email verification completed successfully")
                                            return True
                                    except:
                                        # Try English button text
                                        try:
                                            continue_button = self.driver.find_element("xpath", "//button[@role='button']//span[contains(text(), 'Next')]/..")
                                            continue_button.click()
                                            logger.info("Clicked continue button after entering email (using English text)")
                                            time.sleep(3)
                                            
                                            if not self.is_verification_screen():
                                                logger.info("Email verification completed successfully")
                                                return True
                                        except:
                                            # Try to press Enter key if button not found
                                            input_field.send_keys(Keys.RETURN)
                                            logger.info("Pressed Enter key after entering email")
                                            time.sleep(3)
                                            
                                            if not self.is_verification_screen():
                                                logger.info("Email verification completed successfully")
                                                return True
                            except Exception as e:
                                logger.error(f"Error clicking continue button: {e}")
                    except Exception as e:
                        logger.error(f"Error finding input field: {e}")
            
            # If we're still here, it's a code verification or other type
            # Proceed with the original verification handling
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
            
            # Try to broadcast notification (modified to be more resilient)
            try:
                # Get admin URL
                admin_base_url = os.getenv("ADMIN_BASE_URL", "http://localhost:5000")
                
                # For Docker environment, use the service name
                if os.environ.get("DOCKER_ENV") == "true":
                    admin_base_url = "http://web-interface:5000"
                    
                verification_url = f"{admin_base_url}/admin/verification/{verification_id}"
                
                # Direct HTTP call instead of using AnnouncementBroadcaster
                try:
                    import requests
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry
                    
                    # Setup a retry strategy with backoff
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
                    )
                    
                    # Create a session with the retry strategy
                    session = requests.Session()
                    adapter = HTTPAdapter(max_retries=retry_strategy)
                    session.mount("http://", adapter)
                    session.mount("https://", adapter)
                    
                    # Send notification directly to the admin interface
                    notification_response = session.post(
                        f"{admin_base_url}/api/admin/notifications",
                        json={
                            "message": f"URGENT: Twitter verification code required. Access verification panel at: {verification_url}",
                            "type": "urgent"
                        },
                        timeout=5  # Add timeout to prevent hanging
                    )
                    
                    if notification_response.status_code == 200:
                        logger.info("Notification sent successfully")
                    else:
                        logger.warning(f"Notification API returned status code: {notification_response.status_code}")
                        
                except Exception as notification_error:
                    logger.error(f"Failed to send notification via HTTP: {notification_error}")
                    # Continue anyway, don't fail the verification process
                    
            except Exception as e:
                logger.error(f"Failed to prepare notification: {e}")
                # Continue anyway, admin can still check the dashboard
            
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
            # Use the shared volume in Docker environments
            if os.environ.get("DOCKER_ENV") == "true":
                screenshots_dir = Path("/app/static/screenshots")
            else:
                screenshots_dir = Path(__file__).parent.parent.parent / "static" / "screenshots"
            
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"verification_{timestamp}.png"
            filepath = screenshots_dir / filename
            
            if self.driver.save_screenshot(str(filepath)):
                logger.info(f"Screenshot saved to {filepath}")
                # Return a path relative to static folder for web access
                return f"/static/screenshots/{filename}"
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
                "button[data-testid='ocfEnterTextNextButton']",  # Add the specific data-testid
                "button:contains('Next')",
                "button:contains('Verify')",
                "button:contains('Submit')",
                "button:contains('Continue')",
                "button:contains('Weiter')"  # German "Continue"
            ]
            
            # First try to find by data-testid which is most reliable
            try:
                submit_button = self.driver.find_element("css selector", "button[data-testid='ocfEnterTextNextButton']")
            except:
                # If that fails, try other methods
                for selector in button_selectors:
                    try:
                        if selector.startswith("button:contains"):
                            # For :contains selectors, we need to use a different approach
                            text = selector.split("'")[1]
                            elements = self.driver.find_elements("xpath", f"//button[contains(., '{text}')]")
                            if elements:
                                submit_button = elements[0]
                                break
                        else:
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
