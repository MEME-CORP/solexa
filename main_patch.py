# main_patch.py - Patches main.py to work in unified mode

import os
import sys
import importlib.util
import types

def patch_main_module():
    """
    Patch the main module to skip signal handling in unified mode
    This is called before importing main.py
    """
    # Check if we're in unified mode
    if os.environ.get("UNIFIED_SERVICE_MODE") == "true":
        # Define a replacement for setup_signal_handlers that does nothing
        def noop_signal_handler(*args, **kwargs):
            import logging
            logging.getLogger('MainPatch').info("Signal handler registration skipped in unified mode")
            return
        
        # If main module is already loaded, patch it
        if 'main' in sys.modules:
            sys.modules['main'].setup_signal_handlers = noop_signal_handler
            
        # Patch the signal module for good measure
        import signal as signal_module
        original_signal = signal_module.signal
        
        def patched_signal(signalnum, handler):
            # Skip signal registration in threads
            import threading
            if threading.current_thread() is not threading.main_thread():
                import logging
                logging.getLogger('MainPatch').debug(f"Ignoring signal registration for {signalnum} in non-main thread")
                return
            return original_signal(signalnum, handler)
        
        signal_module.signal = patched_signal

# Apply the patch immediately
patch_main_module() 