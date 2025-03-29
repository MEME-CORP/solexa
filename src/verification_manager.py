import logging
import time
import json
from datetime import datetime
from threading import Lock
from pathlib import Path
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('VerificationManager')

class VerificationManager:
    """Manages Twitter verification requests"""
    
    # Class variables for verification tracking
    _verifications = {}
    _lock = Lock()
    
    # Shared storage path
    @classmethod
    def _get_storage_path(cls):
        """Get path to shared storage file"""
        # Use the shared volume between containers
        if os.environ.get("DOCKER_ENV") == "true":
            # In Docker, use the shared volume
            return Path("/app/static/verifications.json")
        else:
            # Otherwise use the project root
            return Path(__file__).parent.parent / "static" / "verifications.json"
    
    @classmethod
    def _save_verifications(cls):
        """Save verifications to shared file"""
        try:
            storage_path = cls._get_storage_path()
            # Create parent directory if it doesn't exist
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to serializable format
            serializable = {}
            for vid, verification in cls._verifications.items():
                # Copy without driver which isn't serializable
                serializable[vid] = {
                    'timestamp': verification['timestamp'].isoformat(),
                    'screenshot_path': verification['screenshot_path'],
                    'status': verification['status'],
                    'code': verification['code']
                }
            
            with open(storage_path, 'w') as f:
                json.dump(serializable, f)
                
            logger.info(f"Saved verifications to {storage_path}")
        except Exception as e:
            logger.error(f"Error saving verifications: {e}")
    
    @classmethod
    def _load_verifications(cls):
        """Load verifications from shared file"""
        try:
            storage_path = cls._get_storage_path()
            if not storage_path.exists():
                return
                
            with open(storage_path, 'r') as f:
                serializable = json.load(f)
                
            # Convert back to internal format
            for vid, verification in serializable.items():
                if vid not in cls._verifications:  # Don't overwrite existing entries
                    cls._verifications[vid] = {
                        'timestamp': datetime.fromisoformat(verification['timestamp']),
                        'screenshot_path': verification['screenshot_path'],
                        'status': verification['status'],
                        'code': verification['code'],
                        'driver': None  # Driver isn't serializable
                    }
                    
            logger.info(f"Loaded verifications from {storage_path}")
        except Exception as e:
            logger.error(f"Error loading verifications: {e}")
    
    @classmethod
    def register_verification(cls, verification_id, screenshot_path, driver):
        """Register a new verification request"""
        with cls._lock:
            # Load existing verifications first
            cls._load_verifications()
            
            cls._verifications[verification_id] = {
                'timestamp': datetime.now(),
                'screenshot_path': screenshot_path,
                'driver': driver,
                'status': 'pending',
                'code': None
            }
            
            # Save to shared storage
            cls._save_verifications()
            
            logger.info(f"Registered verification request: {verification_id}")
    
    @classmethod
    def get_verification(cls, verification_id):
        """Get verification details by ID"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            return cls._verifications.get(verification_id)
    
    @classmethod
    def list_pending_verifications(cls):
        """List all pending verification requests"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            
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
    def submit_verification_code(cls, verification_id, code):
        """Submit a verification code for a pending request"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            
            verification = cls._verifications.get(verification_id)
            if not verification:
                logger.error(f"Verification ID not found: {verification_id}")
                return False
            
            if verification['status'] != 'pending':
                logger.error(f"Verification is not pending: {verification_id}")
                return False
            
            driver = verification['driver']
            
            # Update verification status
            verification['status'] = 'processing'
            verification['code'] = code
            
            # Save changes
            cls._save_verifications()
            
        # Submit code to the browser (outside of lock)
        try:
            # Import here to avoid circular import
            from src.twitter_bot.scraper import Scraper
            
            # If we don't have a driver (e.g., when loaded from file in different container)
            if not driver:
                logger.info(f"No driver available in this container, marking as completed")
                with cls._lock:
                    verification['status'] = 'completed'
                    cls._save_verifications()
                return True
            
            # Create a temporary scraper instance with the existing driver
            temp_scraper = Scraper()
            temp_scraper.driver = driver
            
            # Submit the code
            success = temp_scraper.submit_verification_code(code)
            
            with cls._lock:
                if success:
                    verification['status'] = 'completed'
                    logger.info(f"Verification code accepted: {verification_id}")
                else:
                    verification['status'] = 'failed'
                    logger.error(f"Verification code rejected: {verification_id}")
                
                # Save changes
                cls._save_verifications()
                
            return success
        except Exception as e:
            logger.error(f"Error submitting verification code: {e}")
            with cls._lock:
                verification['status'] = 'error'
                cls._save_verifications()
            return False
    
    @classmethod
    def complete_verification(cls, verification_id):
        """Mark a verification as completed"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            
            verification = cls._verifications.get(verification_id)
            if verification:
                verification['status'] = 'completed'
                cls._save_verifications()
                logger.info(f"Verification marked as completed: {verification_id}")
    
    @classmethod
    def cancel_verification(cls, verification_id):
        """Cancel a pending verification"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            
            verification = cls._verifications.get(verification_id)
            if verification:
                verification['status'] = 'cancelled'
                cls._save_verifications()
                logger.info(f"Verification cancelled: {verification_id}")
    
    @classmethod
    def is_verification_completed(cls, verification_id):
        """Check if verification is completed"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            
            verification = cls._verifications.get(verification_id)
            return verification and verification['status'] == 'completed'
    
    @classmethod
    def cleanup_old_verifications(cls, max_age_hours=24):
        """Remove old verification records"""
        with cls._lock:
            # Load latest verifications
            cls._load_verifications()
            
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