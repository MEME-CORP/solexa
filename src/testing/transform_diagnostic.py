#!/usr/bin/env python
# src/testing/transform_diagnostic.py

import logging
import sys
import json
import os
from pathlib import Path
import yaml
import time
import random
import traceback

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('transform_diagnostic.log')
    ]
)

# Create a dedicated logger for this diagnostic
logger = logging.getLogger('transform_diagnostic')

# Add project root to system path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import the AIGenerator and related modules
from src.ai_generator import AIGenerator


class TransformDiagnostic:
    """A diagnostic tool for testing the AI transformation process."""
    
    def __init__(self):
        """Initialize the diagnostic tool."""
        logger.info("Initializing transformation diagnostic tool")
        
        # Load the transform system prompt to display in diagnostics
        self.transform_prompt = self._load_transform_prompt()
        
        # Create instances of AI generators for different platforms
        logger.info("Initializing AIGenerator instances")
        self.twitter_generator = AIGenerator(mode='twitter')
        self.telegram_generator = AIGenerator(mode='discord_telegram')
        
        # Track timing information
        self.start_time = 0
        self.end_time = 0
    
    def _load_transform_prompt(self):
        """Load the transformation system prompt for reference using the improved path handling."""
        try:
            # Try primary location
            prompt_path = project_root / 'src' / 'prompts_config' / 'transform_system_prompt.yaml'
            logger.info(f"Loading transform system prompt from: {prompt_path}")
            
            # Follow same fallback logic as in AIGenerator
            if not prompt_path.exists():
                logger.warning(f"Transform system prompt file not found at: {prompt_path}")
                # Try alternate location
                alt_path = Path(__file__).parent.parent / 'prompts_config' / 'transform_system_prompt.yaml'
                if alt_path.exists():
                    prompt_path = alt_path
                    logger.info(f"Found transform prompt at alternate location: {alt_path}")
                else:
                    logger.error(f"Transform system prompt not found at alternate location either: {alt_path}")
                    return "Error: Transform system prompt file not found"
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if 'system_prompt' in config:
                    prompt_content = config['system_prompt']
                    logger.info(f"Successfully loaded transformation system prompt: {prompt_content[:100]}...")
                    return prompt_content
                logger.error("No system_prompt found in transform_system_prompt.yaml")
                return "Error: Could not load system prompt"
        except Exception as e:
            logger.error(f"Error loading transformation system prompt: {e}")
            logger.error(traceback.format_exc())
            return f"Error loading prompt: {str(e)}"
    
    def run_diagnostic(self, user_message, platform='twitter', custom_memories=None):
        """
        Run a complete diagnostic test on the transformation process.
        
        Args:
            user_message (str): The message to transform
            platform (str): The platform to use ('twitter' or 'telegram')
            custom_memories (list, optional): Custom memories to use for the test
            
        Returns:
            dict: Diagnostic results including input, output, and timing info
        """
        logger.info(f"=============== STARTING NEW DIAGNOSTIC ===============")
        logger.info(f"Platform: {platform}")
        logger.info(f"Input message: '{user_message}'")
        
        # Select the appropriate generator based on platform
        generator = self.twitter_generator if platform == 'twitter' else self.telegram_generator
        logger.info(f"Using {platform} generator with model: {generator.model}")
        
        # Step 1: Log the input
        diagnostic_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform,
            "input_message": user_message,
            "input_length": len(user_message),
            "process_steps": [],
        }
        
        try:
            # Step 1.5: Check memory status before transformation
            if custom_memories:
                memory_status = f"Using {len(custom_memories)} custom provided memories"
                memories_to_use = custom_memories
            elif generator.memories:
                memories_count = len(generator.memories) if isinstance(generator.memories, list) else 1
                memory_status = f"Using {memories_count} existing memories from generator"
                # Sample random memories like ai_generator.py does
                if isinstance(generator.memories, list):
                    memories_to_use = random.sample(generator.memories, min(3, len(generator.memories)))
                else:
                    memories_to_use = generator.memories
            else:
                memory_status = "No memories available for context"
                memories_to_use = None
            
            logger.info(f"Memory status: {memory_status}")
            
            # Add memory info to diagnostic results
            diagnostic_results["process_steps"].append({
                "step": "memory_preparation",
                "description": "Memory context preparation",
                "memory_status": memory_status,
                "memory_sample": str(memories_to_use)[:200] + "..." if memories_to_use and len(str(memories_to_use)) > 200 else str(memories_to_use)
            })
            
            # Step 2: Get the system prompt that will be used
            logger.info("Preparing transformation system prompt")
            # Use custom memories if provided
            kwargs = {"user_message": user_message}
            if memories_to_use:
                kwargs["memories"] = memories_to_use
                
            transform_messages = generator._prepare_transform_messages(**kwargs)
            system_prompt = transform_messages[0]["content"] if transform_messages else "No system prompt available"
            
            # Add the prepared system prompt to results
            diagnostic_results["process_steps"].append({
                "step": "system_prompt_preparation",
                "description": "System prompt prepared for transformation",
                "system_prompt_preview": system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt,
                "system_prompt_length": len(system_prompt)
            })
            
            # Step 3: Get the user prompt that will be sent to the model
            user_prompt = transform_messages[1]["content"] if len(transform_messages) > 1 else "No user prompt available"
            
            # Add the user prompt to results
            diagnostic_results["process_steps"].append({
                "step": "user_prompt_preparation",
                "description": "User prompt prepared for transformation",
                "user_prompt": user_prompt
            })
            
            # Step 4: Time the transformation process
            logger.info("Starting transformation process")
            self.start_time = time.time()
            
            # Call the actual transformation method with the same kwargs
            transformed_content = generator.transform_message(**kwargs)
            
            self.end_time = time.time()
            processing_time = self.end_time - self.start_time
            
            # Add the transformation timing to results
            diagnostic_results["process_steps"].append({
                "step": "transformation_execution",
                "description": "Message transformed by AI model",
                "processing_time_seconds": processing_time,
                "model_used": generator.model,
                "temperature": generator.temperature,
                "max_tokens": generator.max_tokens
            })
            
            # Step 5: Log the output
            logger.info(f"Transformation complete in {processing_time:.2f} seconds")
            logger.info(f"Transformed output: '{transformed_content}'")
            
            # Add the final output to results
            diagnostic_results["transformed_message"] = transformed_content
            diagnostic_results["output_length"] = len(transformed_content)
            diagnostic_results["processing_time"] = processing_time
            diagnostic_results["success"] = True
            
            # Step 6: Log character differences
            char_diff = len(transformed_content) - len(user_message)
            char_diff_percent = (char_diff / len(user_message)) * 100 if len(user_message) > 0 else 0
            
            diagnostic_results["character_difference"] = {
                "diff": char_diff,
                "percent_change": f"{char_diff_percent:.2f}%",
                "direction": "longer" if char_diff > 0 else "shorter" if char_diff < 0 else "same length"
            }
            
            logger.info(f"Character difference: {char_diff} ({char_diff_percent:.2f}%)")
            
            # Step 7: Analyze Solexa style markers
            style_markers = self._analyze_style_markers(transformed_content)
            diagnostic_results["style_analysis"] = style_markers
            
        except Exception as e:
            logger.error(f"Error during transformation diagnostic: {e}", exc_info=True)
            diagnostic_results["success"] = False
            diagnostic_results["error"] = str(e)
            diagnostic_results["error_traceback"] = traceback.format_exc()
            
        logger.info(f"=============== DIAGNOSTIC COMPLETE ===============")
        return diagnostic_results
    
    def _analyze_style_markers(self, text):
        """Analyze the text for Solexa style markers."""
        style_markers = {
            "british_slang": False,
            "crypto_terminology": False,
            "casual_tone": False,
            "cockneyisms": False,
            "abbreviated_words": False
        }
        
        # Simple checks for style markers
        british_slang = ["innit", "mate", "blimey", "proper", "geezer", "quid", "dodgy", "cheeky"]
        crypto_terms = ["btc", "eth", "defi", "nft", "bitcoin", "blockchain", "token", "crypto"]
        cockneyisms = ["apples and pears", "dog and bone", "adam and eve", "bread and honey"]
        abbreviations = ["lol", "btw", "tbh", "idk", "rn", "af"]
        
        # Convert to lowercase for case-insensitive matching
        lower_text = text.lower()
        
        # Check for each type of marker
        style_markers["british_slang"] = any(term in lower_text for term in british_slang)
        style_markers["crypto_terminology"] = any(term in lower_text for term in crypto_terms)
        style_markers["cockneyisms"] = any(term in lower_text for term in cockneyisms)
        style_markers["abbreviated_words"] = any(term in lower_text for term in abbreviations)
        
        # Check for casual tone (simple heuristic)
        casual_indicators = ["!", "...", "?!", "haha", "lol", "just", "like", "gonna", "wanna"]
        style_markers["casual_tone"] = any(term in lower_text for term in casual_indicators)
        
        # Count style markers present
        style_markers["marker_count"] = sum(1 for key, value in style_markers.items() if value and key != "marker_count")
        
        return style_markers
    
    def save_results(self, results, filename=None):
        """Save diagnostic results to a JSON file."""
        if filename is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"transform_diagnostic_{timestamp}.json"
        
        output_path = Path(filename)
        logger.info(f"Saving diagnostic results to: {output_path}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Diagnostic results saved successfully")
        return output_path


def run_sample_tests():
    """Run sample tests with various inputs and platforms."""
    diagnostic = TransformDiagnostic()
    
    # Define test cases with different message types
    test_cases = [
        {
            "name": "simple_statement",
            "message": "The market is looking very volatile today.",
            "platform": "twitter"
        },
        {
            "name": "question",
            "message": "What do you think about the latest Bitcoin price movement?",
            "platform": "twitter"
        },
        {
            "name": "technical_analysis",
            "message": "BTC is forming a bearish divergence on the 4h chart with declining volume.",
            "platform": "twitter"
        },
        {
            "name": "telegram_casual",
            "message": "Hey everyone, just wanted to check in about today's market moves.",
            "platform": "telegram"
        },
        {
            "name": "emotional_reaction",
            "message": "I'm so excited about this new DeFi protocol launch!",
            "platform": "twitter"
        },
        {
            "name": "with_custom_memory",
            "message": "I think we might see a market correction soon.",
            "platform": "twitter",
            "custom_memories": [
                "I once lost 80% of my portfolio in a bear market",
                "HODL is always the best strategy in crypto",
                "Market corrections are healthy for long-term growth"
            ]
        }
    ]
    
    # Run diagnostics for each test case
    all_results = {}
    for test in test_cases:
        logger.info(f"Running test case: {test['name']}")
        
        # Check if this test has custom memories
        custom_memories = test.get("custom_memories")
        
        # Run the diagnostic with appropriate parameters
        if custom_memories:
            results = diagnostic.run_diagnostic(
                test['message'], 
                test['platform'],
                custom_memories=custom_memories
            )
        else:
            results = diagnostic.run_diagnostic(test['message'], test['platform'])
            
        all_results[test['name']] = results
        
        # Save individual test results
        diagnostic.save_results(results, f"transform_diagnostic_{test['name']}.json")
        
        # Brief pause between tests to avoid rate limiting
        time.sleep(1)
    
    # Save consolidated results
    consolidated_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_count": len(test_cases),
        "test_results": all_results,
    }
    
    diagnostic.save_results(consolidated_report, "transform_diagnostic_consolidated.json")
    
    print("\nDiagnostic testing complete!")
    print(f"Generated {len(test_cases)} individual test reports and 1 consolidated report.")
    print("Check the log file and JSON output files for detailed results.")


if __name__ == "__main__":
    print("AI Transformation Diagnostic Tool")
    print("=================================")
    
    # Check if user wants to run sample tests or provide custom input
    use_sample = input("Run sample tests? (y/n, default: y): ").strip().lower()
    
    if use_sample != 'n':
        run_sample_tests()
    else:
        # Get user input for custom test
        diagnostic = TransformDiagnostic()
        
        message = input("\nEnter message to transform: ")
        platform = input("Select platform (twitter/telegram, default: twitter): ").strip().lower()
        if platform not in ['twitter', 'telegram']:
            platform = 'twitter'
            
        # Ask if user wants to provide custom memories
        use_custom_memories = input("Use custom memories? (y/n, default: n): ").strip().lower() == 'y'
        custom_memories = None
        
        if use_custom_memories:
            print("Enter up to 3 memories (one per line, blank line to finish):")
            custom_memories = []
            for i in range(3):
                memory = input(f"Memory {i+1}: ").strip()
                if not memory:
                    break
                custom_memories.append(memory)
            
            if not custom_memories:
                custom_memories = None
                print("No custom memories provided, using system memories.")
        
        # Run diagnostic with user input
        results = diagnostic.run_diagnostic(
            message, 
            platform,
            custom_memories=custom_memories
        )
        
        # Save results
        output_path = diagnostic.save_results(results)
        
        print("\nDiagnostic complete!")
        print(f"Results saved to: {output_path}")
        print(f"Original message: '{message}'")
        print(f"Transformed message: '{results.get('transformed_message', 'Error: No transformation')}'")
        print(f"Processing time: {results.get('processing_time', 0):.2f} seconds")
        
        # Show style analysis
        if 'style_analysis' in results:
            print("\nStyle Analysis:")
            for key, value in results['style_analysis'].items():
                if key != 'marker_count':
                    print(f"- {key.replace('_', ' ').title()}: {'Yes' if value else 'No'}")
            print(f"- Total Style Markers: {results['style_analysis'].get('marker_count', 0)}") 