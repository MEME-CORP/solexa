#!/usr/bin/env python
# unified_service.py - Runs all services in a single process

import os
import sys
import time
import signal
import logging
import subprocess

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.environ.get('LOGLEVEL', 'INFO').upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('UnifiedService')

# Global flag for controlling service shutdown
running = True
service_processes = []

def signal_handler(signum, frame):
    """Handle termination signals for graceful shutdown"""
    global running
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    running = False
    
    # Send signal to all child processes
    for name, p in service_processes:
        if p.poll() is None:
            logger.info(f"Sending signal to {name} process {p.pid}")
            try:
                os.kill(p.pid, signum)
            except Exception as e:
                logger.error(f"Error sending signal to {name} process: {e}")
    
    # Wait for processes to terminate
    for name, p in service_processes:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"{name} process {p.pid} did not terminate, forcing...")
            p.terminate()

def run_subprocess(cmd, env=None, shell=False):
    """Run a command as a subprocess with logging"""
    logger.info(f"Running command: {cmd if shell else ' '.join(cmd)}")
    
    if not env:
        env = os.environ.copy()
    
    # Add commonly needed environment variables
    env["HEADLESS_BROWSER"] = "true"
    env["CHROME_NO_SANDBOX"] = "true"
    env["PYTHONPATH"] = "/app:" + env.get("PYTHONPATH", "")
    
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
        shell=shell
    )
    
    # Log output in real-time
    def log_output():
        for line in iter(process.stdout.readline, ''):
            if line.strip():  # Only log non-empty lines
                logger.info(f"[{process.pid}] {line.rstrip()}")
    
    import threading
    log_thread = threading.Thread(target=log_output, daemon=True)
    log_thread.start()
    
    return process

def main():
    """Main function to run all services"""
    global service_processes
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting unified service...")
    
    # Ensure needed environment variables 
    os.environ["HEADLESS_BROWSER"] = "true"
    os.environ["CHROME_NO_SANDBOX"] = "true"
    
    # Start all services using subprocess for maximum isolation
    try:
        # Clone current environment
        env = os.environ.copy()
        
        # Start web interface - using main.py with the correct arguments
        web_process = run_subprocess(
            ["python", "main.py", "--bots", "web", "--web-host", "0.0.0.0", "--web-port", "5000"],
            env=env
        )
        if web_process:
            service_processes.append(("Web Interface", web_process))
        
        # Give the web interface time to start
        time.sleep(5)
        
        # Start Twitter bot - using main.py with the correct arguments
        twitter_process = run_subprocess(
            ["python", "main.py", "--bots", "twitter"],
            env=env
        )
        if twitter_process:
            service_processes.append(("Twitter Bot", twitter_process))
        
        # Start Telegram bot - using main.py with the correct arguments
        telegram_process = run_subprocess(
            ["python", "main.py", "--bots", "telegram"],
            env=env
        )
        if telegram_process:
            service_processes.append(("Telegram Bot", telegram_process))
        
        # Monitor child processes
        while running:
            for i, (name, process) in enumerate(list(service_processes)):
                # Check if process is still running
                if process.poll() is not None:
                    exit_code = process.poll()
                    logger.warning(f"{name} process exited with code {exit_code}")
                    
                    # Remove from active processes
                    service_processes.pop(i)
                    
                    # Restart if we're still running
                    if running:
                        logger.info(f"Attempting to restart {name}...")
                        if name == "Web Interface":
                            web_process = run_subprocess(
                                ["python", "main.py", "--bots", "web", "--web-host", "0.0.0.0", "--web-port", "5000"],
                                env=env
                            )
                            if web_process:
                                service_processes.append(("Web Interface", web_process))
                        elif name == "Twitter Bot":
                            twitter_process = run_subprocess(
                                ["python", "main.py", "--bots", "twitter"],
                                env=env
                            )
                            if twitter_process:
                                service_processes.append(("Twitter Bot", twitter_process))
                        elif name == "Telegram Bot":
                            telegram_process = run_subprocess(
                                ["python", "main.py", "--bots", "telegram"],
                                env=env
                            )
                            if telegram_process:
                                service_processes.append(("Telegram Bot", telegram_process))
            
            # Sleep to avoid CPU thrashing
            time.sleep(1)
        
    except Exception as e:
        logger.error(f"Error running unified service: {e}", exc_info=True)
    finally:
        logger.info("Unified service shutting down...")
        # Terminate all child processes
        for name, process in service_processes:
            if process.poll() is None:  # If process is still running
                logger.info(f"Terminating {name} process")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Killing {name} process forcefully")
                    process.kill()

if __name__ == "__main__":
    main() 