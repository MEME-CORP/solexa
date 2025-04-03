import logging
import time
import json
from datetime import datetime, timedelta
from threading import Lock
from pathlib import Path
import os
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('VerificationManager')

class VerificationManager:
    """Manages verification sessions across services within the same process"""
    
    # Storage for active verification sessions
    _verifications: Dict[str, Dict[str, Any]] = {}
    _lock = Lock()
    
    @classmethod
    def register_verification(cls, verification_id: str, screenshot_path: str, driver=None) -> bool:
        """Register a new verification session"""
        with cls._lock:
            cls._verifications[verification_id] = {
                'id': verification_id,
                'screenshot_path': screenshot_path,
                'timestamp': datetime.now(),  # Use datetime object directly
                'status': 'pending',  # Add explicit 'pending' status
                'driver': driver,
                'code': None
            }
            
            # Also save to disk for persistence
            cls._save_verifications()
            
            logger.info(f"Registered new verification session: {verification_id}")
            return True
    
    @classmethod
    def complete_verification(cls, verification_id: str) -> bool:
        """Mark a verification as completed"""
        with cls._lock:
            if verification_id in cls._verifications:
                cls._verifications[verification_id]['completed'] = True
                cls._save_verifications()
                return True
            return False
    
    @classmethod
    def cancel_verification(cls, verification_id: str) -> bool:
        """Cancel a verification session"""
        with cls._lock:
            if verification_id in cls._verifications:
                cls._verifications.pop(verification_id)
                cls._save_verifications()
                return True
            return False
    
    @classmethod
    def is_verification_completed(cls, verification_id: str) -> bool:
        """Check if a verification session is completed (with improved safety)"""
        with cls._lock:
            try:
                if verification_id in cls._verifications:
                    verification = cls._verifications[verification_id]
                    # Safely check for 'completed' key with a default value of False
                    return verification.get('completed', False) or verification.get('status') == 'completed'
                return False
            except Exception as e:
                logger.error(f"Error checking verification completion: {e}")
                return False
    
    @classmethod
    def get_verification(cls, verification_id: str) -> Optional[Dict[str, Any]]:
        """Get verification details by ID"""
        with cls._lock:
            return cls._verifications.get(verification_id)
    
    @classmethod
    def get_all_verifications(cls) -> Dict[str, Dict[str, Any]]:
        """Get all active verifications"""
        with cls._lock:
            # Create a copy without the driver object (not serializable)
            result = {}
            for id, verification in cls._verifications.items():
                result[id] = {k: v for k, v in verification.items() if k != 'driver'}
            return result
    
    @classmethod
    def submit_verification_code(cls, verification_id: str, code: str) -> bool:
        """Submit a verification code for a session with better error handling"""
        with cls._lock:
            try:
                if verification_id not in cls._verifications:
                    logger.error(f"Verification ID not found: {verification_id}")
                    return False
                
                verification = cls._verifications[verification_id]
                driver = verification.get('driver')
                
                if not driver:
                    logger.error(f"No driver associated with verification: {verification_id}")
                    
                    # Try to get current driver from TwitterService as fallback
                    try:
                        from src.twitter_bot.twitter_service import twitter_service
                        if twitter_service and twitter_service.scraper and twitter_service.scraper.driver:
                            logger.info("Using active Twitter service driver as fallback")
                            driver = twitter_service.scraper.driver
                        else:
                            return False
                    except Exception as import_error:
                        logger.error(f"Error getting fallback driver: {import_error}")
                        return False
                    
                # Import here to avoid circular imports
                from src.twitter_bot.scraper import Scraper
                scraper_instance = Scraper()
                scraper_instance.driver = driver
                
                # Try to submit the code
                success = scraper_instance.submit_verification_code(code)
                
                if success:
                    verification['completed'] = True
                    verification['status'] = 'completed' # Add both flags for consistency
                    verification['code'] = code
                    cls._save_verifications()
                    logger.info(f"Verification completed for ID: {verification_id}")
                    return True
                else:
                    logger.error(f"Failed to submit verification code for ID: {verification_id}")
                    return False
            except Exception as e:
                logger.error(f"Error submitting verification code: {e}")
                return False
    
    @classmethod
    def _save_verifications(cls) -> None:
        """Save verifications to disk for persistence"""
        try:
            # Get verification file path from environment or use default
            verification_file_path = os.getenv('VERIFICATION_FILE_PATH', '/app/static/verifications.json')
            
            # Create directory if it doesn't exist
            path = Path(verification_file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create a serializable copy without driver objects and with ISO formatted datetimes
            serializable_verifications = {}
            for id, verification in cls._verifications.items():
                serializable_verification = {}
                for k, v in verification.items():
                    if k == 'driver':
                        # Skip driver objects - not serializable
                        continue
                    elif k == 'timestamp' and isinstance(v, datetime):
                        # Convert datetime to ISO format string
                        serializable_verification[k] = v.isoformat()
                    else:
                        serializable_verification[k] = v
                serializable_verifications[id] = serializable_verification
            
            # Write to file
            with open(verification_file_path, 'w') as f:
                json.dump(serializable_verifications, f, indent=2)
            
            logger.info(f"Saved {len(serializable_verifications)} verifications to disk")
            
        except Exception as e:
            logger.error(f"Error saving verifications: {e}")
    
    @classmethod
    def load_verifications(cls) -> None:
        """Load verifications from disk on startup"""
        try:
            verification_file_path = os.getenv('VERIFICATION_FILE_PATH', '/app/static/verifications.json')
            path = Path(verification_file_path)
            
            if path.exists():
                with open(verification_file_path, 'r') as f:
                    loaded_verifications = json.load(f)
                    
                # Only load verifications that aren't completed
                with cls._lock:
                    for id, verification in loaded_verifications.items():
                        if not verification.get('completed', True):
                            # Add to in-memory storage without driver (will be reconnected later if needed)
                            verification['driver'] = None
                            cls._verifications[id] = verification
                            
                logger.info(f"Loaded {len(cls._verifications)} active verifications from disk")
        except FileNotFoundError:
            logger.info("No verification file found, starting with empty verification list")
        except Exception as e:
            logger.error(f"Error loading verifications: {e}")
        
    @classmethod
    def _load_verifications(cls):
        """Load verifications from file with age filtering and error recovery"""
        try:
            file_path = os.getenv("VERIFICATION_FILE_PATH", os.path.join(os.path.dirname(__file__), "verifications.json"))
            
            # Skip if file doesn't exist
            if not os.path.exists(file_path):
                return False
            
            # Try to load the file
            try:
                with open(file_path, 'r') as f:
                    loaded_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in verification file: {e}")
                # Create backup of corrupted file
                backup_path = f"{file_path}.corrupted"
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Created backup of corrupted verification file at: {backup_path}")
                    # Create empty file to start fresh
                    with open(file_path, 'w') as f:
                        f.write('{}')
                    logger.info("Created empty verification file")
                except Exception as backup_error:
                    logger.error(f"Failed to create backup: {backup_error}")
                return False
                
            # Reset verifications dictionary to avoid duplicates
            cls._verifications = {}
            
            # Get cutoff time (1 hour ago)
            cutoff_time = datetime.now().timestamp() - (60 * 60)  # 1 hour in seconds
            
            # Process each verification with proper timestamp handling
            for verification_id, data in loaded_data.items():
                # Parse timestamp properly
                timestamp = data.get("timestamp")
                timestamp_obj = None
                
                if isinstance(timestamp, str):
                    try:
                        # Try ISO format first
                        timestamp_obj = datetime.fromisoformat(timestamp)
                    except ValueError:
                        try:
                            # Try numerical timestamp
                            timestamp_value = float(timestamp)
                            timestamp_obj = datetime.fromtimestamp(timestamp_value)
                        except:
                            # Use current time if parsing fails
                            timestamp_obj = datetime.now()
                elif isinstance(timestamp, (int, float)):
                    timestamp_obj = datetime.fromtimestamp(float(timestamp))
                else:
                    # Default to current time if timestamp is invalid
                    timestamp_obj = datetime.now()
                
                # Skip old verifications (older than cutoff)
                if timestamp_obj.timestamp() < cutoff_time:
                    logger.info(f"Skipping old verification: {verification_id} (too old)")
                    continue
                    
                # Skip completed verifications
                if data.get("completed", False) or data.get("status") == "completed":
                    logger.info(f"Skipping verification: {verification_id} (already completed)")
                    continue
                
                # Add valid verification to memory
                cls._verifications[verification_id] = {
                    "id": verification_id,
                    "timestamp": timestamp_obj,
                    "screenshot_path": data.get("screenshot_path", ""),
                    "status": "pending",  # Force status to pending for consistency
                    "driver": None,  # Driver object can't be stored in JSON
                    "completed": False  # Explicitly set to False
                }
            
            logger.info(f"Loaded {len(cls._verifications)} active verifications from disk")
            return True
        except Exception as e:
            logger.error(f"Error loading verifications: {e}")
            return False

    @classmethod
    def list_pending_verifications(cls):
        """List all pending verification requests with age filtering"""
        with cls._lock:
            # Load verifications first
            cls._load_verifications()
            
            # Get cutoff time (verifications older than 1 hour are ignored)
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            pending = {}
            for vid, v in cls._verifications.items():
                # Skip if verification is completed
                if v.get('completed', False) or v.get('status') == 'completed':
                    continue
                    
                # Get timestamp
                timestamp = v.get('timestamp')
                
                # Skip if timestamp is too old
                if timestamp < cutoff_time:
                    continue
                
                # Add to pending list
                pending[vid] = {
                    'timestamp': timestamp,
                    'screenshot_path': v.get('screenshot_path', ''),
                    'status': 'pending'
                }
            
            logger.info(f"Found {len(pending)} valid pending verifications")
            return pending
    
    @classmethod
    def cleanup_old_verifications(cls, max_age_hours=1):
        """Remove old verification records"""
        with cls._lock:
            # Get current time
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(hours=max_age_hours)
            
            to_remove = []
            for vid, verification in cls._verifications.items():
                # Get timestamp
                timestamp = verification.get('timestamp')
                
                # Handle string timestamps
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp)
                    except ValueError:
                        # Skip if we can't parse the timestamp
                        continue
                        
                # Skip if timestamp is None
                if timestamp is None:
                    continue
                    
                # Check if verification is too old
                if timestamp < cutoff_time:
                    to_remove.append(vid)
            
            # Remove old verifications
            for vid in to_remove:
                del cls._verifications[vid]
                
            # Save changes to disk
            if to_remove:
                cls._save_verifications()
                logger.info(f"Cleaned up {len(to_remove)} old verification records")

    @classmethod
    def reset_verifications_file(cls):
        """Emergency reset of the verifications file"""
        try:
            file_path = os.getenv("VERIFICATION_FILE_PATH", os.path.join(os.path.dirname(__file__), "verifications.json"))
            # Create an empty JSON object
            with open(file_path, 'w') as f:
                f.write('{}')
            logger.info("Reset verifications file to empty state")
            return True
        except Exception as e:
            logger.error(f"Error resetting verifications file: {e}")
            return False 