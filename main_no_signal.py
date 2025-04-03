# Create this file in the project root

# Import the patch first
import main_patch

# Then import main
import main

def main_no_signal():
    """
    Version of main.main() that doesn't register signal handlers
    """
    import os
    import logging
    
    logger = logging.getLogger('main_no_signal')
    service_name = os.environ.get("SERVICE_NAME", "Unknown")
    logger.info(f"Starting {service_name} service without signal handlers")
    
    # Skip signal handling in main.py
    original_setup_signal_handlers = main.setup_signal_handlers
    main.setup_signal_handlers = lambda: None
    
    try:
        # Call the original main function
        main.main()
    except Exception as e:
        logger.error(f"Error in {service_name} service: {e}", exc_info=True)
    finally:
        # Restore the original function
        main.setup_signal_handlers = original_setup_signal_handlers

# Add this function to the main module
main.main_no_signal = main_no_signal 