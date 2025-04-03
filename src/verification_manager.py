import logging
import time
import json
from datetime import datetime
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
                'timestamp': datetime.now().isoformat(),
                'completed': False,
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
        """Check if a verification session is completed"""
        with cls._lock:
            if verification_id in cls._verifications:
                return cls._verifications[verification_id]['completed']
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
        """Submit a verification code for a session"""
        with cls._lock:
            if verification_id not in cls._verifications:
                logger.error(f"Verification ID not found: {verification_id}")
                return False
            
            verification = cls._verifications[verification_id]
            driver = verification.get('driver')
            
            if not driver:
                logger.error(f"No driver associated with verification: {verification_id}")
                return False
                
            # Import here to avoid circular imports
            from src.twitter_bot.scraper import Scraper
            scraper_instance = Scraper()
            scraper_instance.driver = driver
            
            # Try to submit the code
            success = scraper_instance.submit_verification_code(code)
            
            if success:
                verification['completed'] = True
                verification['code'] = code
                cls._save_verifications()
                logger.info(f"Verification completed for ID: {verification_id}")
                return True
            else:
                logger.error(f"Failed to submit verification code for ID: {verification_id}")
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
            
            # Create a serializable copy without driver objects
            serializable_verifications = {}
            for id, verification in cls._verifications.items():
                serializable_verifications[id] = {k: v for k, v in verification.items() if k != 'driver'}
            
            # Write to file
            with open(verification_file_path, 'w') as f:
                json.dump(serializable_verifications, f, indent=2)
                
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
        """Alias for load_verifications for backward compatibility"""
        return cls.load_verifications()

    @classmethod
    def list_pending_verifications(cls):
        """List all pending verification requests"""
        with cls._lock:
            # Load latest verifications
            cls.load_verifications()
            
            return {
                vid: {
                    'timestamp': v['timestamp'],
                    'screenshot_path': v['screenshot_path'],
                    'status': v['status']
                }
                for vid, v in cls._verifications.items()
                if v['status'] == 'pending'
            }
    
    @classmethod
    def cleanup_old_verifications(cls, max_age_hours=24):
        """Remove old verification records"""
        with cls._lock:
            # Load latest verifications
            cls.load_verifications()
            
            current_time = datetime.now()
            to_remove = []
            
            for vid, verification in cls._verifications.items():
                age = (current_time - verification['timestamp']).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(vid)
            
            for vid in to_remove:
                del cls._verifications[vid]
                
            if to_remove:
                cls._save_verifications()
                logger.info(f"Cleaned up {len(to_remove)} old verification records") 