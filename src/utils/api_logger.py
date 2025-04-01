import logging
import json
from functools import wraps
import time
import os

class APILogger:
    """Utility for logging API requests and responses in detail"""
    
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Configure logger
        self.logger = logging.getLogger('api_logger')
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        file_handler = logging.FileHandler(f'{log_dir}/api_requests.log')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def log_api_call(self, func):
        """Decorator to log API calls"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Extract method name and arguments
            method_name = func.__name__
            self.logger.info(f"Calling {method_name}")
            
            # Log arguments if they're not too large
            try:
                arg_str = json.dumps(kwargs, indent=2, default=str)
                if len(arg_str) > 1000:
                    arg_str = arg_str[:1000] + "... [truncated]"
                self.logger.debug(f"Arguments: {arg_str}")
            except:
                self.logger.debug("Could not serialize arguments")
            
            try:
                # Call the original function
                result = func(*args, **kwargs)
                
                # Log completion time
                elapsed_time = time.time() - start_time
                self.logger.info(f"{method_name} completed in {elapsed_time:.2f} seconds")
                
                # Log the result structure
                try:
                    if isinstance(result, dict):
                        # Create a shallow copy to avoid modifying the original
                        result_to_log = result.copy()
                        
                        # Handle large content fields
                        for key, value in result.items():
                            if isinstance(value, str) and len(value) > 500:
                                result_to_log[key] = f"{value[:500]}... [truncated, total length: {len(value)}]"
                        
                        result_str = json.dumps(result_to_log, indent=2, default=str)
                        self.logger.debug(f"Result structure: {result_str}")
                    else:
                        self.logger.debug(f"Result type: {type(result).__name__}")
                except:
                    self.logger.debug("Could not serialize result")
                
                return result
                
            except Exception as e:
                # Log any exceptions
                self.logger.error(f"Error in {method_name}: {str(e)}", exc_info=True)
                raise
        
        return wrapper

# Example of how to use this with AIGenerator
def patch_ai_generator():
    """
    Patch the AIGenerator class to log API calls
    
    Example usage:
    ```
    from utils.api_logger import patch_ai_generator
    patch_ai_generator()
    from src.ai_generator import AIGenerator
    ai_gen = AIGenerator()  # Now with logging
    ```
    """
    from src.ai_generator import AIGenerator
    
    # Create logger instance
    api_logger = APILogger()
    
    # Patch methods
    original_fetch = AIGenerator.fetch_crypto_news
    original_transform = AIGenerator.transform_crypto_news
    
    AIGenerator.fetch_crypto_news = api_logger.log_api_call(original_fetch)
    AIGenerator.transform_crypto_news = api_logger.log_api_call(original_transform)
    
    logging.info("AIGenerator methods have been patched with API logging") 