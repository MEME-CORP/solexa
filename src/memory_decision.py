from openai import OpenAI
import json
import logging
from src.config import Config
import os
import yaml
from typing import Union, Tuple, List, Optional
from src.database.supabase_client import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('memory_decision')

def load_yaml_prompt(filename):
    """Load a prompt from a YAML file"""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts_config', filename)
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)
            return prompt_config.get('memory_selection_prompt', '')
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {e}")
        return None



class MemoryDecision:
    def __init__(self):
        # Try to get the API key from the environment first
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # If not available, try to read directly from .env file
        if not openai_api_key:
            try:
                # Look for .env in multiple locations
                env_paths = [
                    os.path.join(os.getcwd(), '.env'),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
                    '/app/.env'
                ]
                
                for env_path in env_paths:
                    if os.path.exists(env_path):
                        print(f"Found .env file at {env_path}")
                        with open(env_path, 'r') as f:
                            for line in f:
                                if line.strip() and not line.startswith('#'):
                                    key, value = line.strip().split('=', 1)
                                    if key == 'OPENAI_API_KEY':
                                        openai_api_key = value
                                        os.environ['OPENAI_API_KEY'] = value  # Set for future use
                                        print("Successfully loaded OPENAI_API_KEY from .env file")
                                        break
                        if openai_api_key:
                            break
            except Exception as e:
                print(f"Error loading .env file: {e}")
        
        # If we have an API key, initialize the client
        if openai_api_key:
            self.client = OpenAI(
                api_key=openai_api_key,
                base_url=os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')
            )
        else:
            # Fallback for development/testing without breaking
            print("WARNING: No OpenAI API key found. Using dummy client.")
            self.client = None  # Or implement a dummy client if needed
        self.db = DatabaseService()
        
        # Load prompt from YAML file
        self.memory_selection_prompt = load_yaml_prompt('memory_selection_prompt.yaml')
        if not self.memory_selection_prompt:
            raise ValueError("Failed to load memory selection prompt from YAML file")

    def select_relevant_memories(self, user_identifier: str, user_message: str, return_details=False) -> Union[str, Tuple[str, dict]]:
        """Select relevant memories from existing ones."""
        try:
            all_memories = self.db.get_memories()
            
            if not all_memories:
                return ("no relevant memories for this conversation", {}) if return_details else "no relevant memories for this conversation"

            # Use instance prompt instead of global constant
            prompt = self.memory_selection_prompt.format(
                user_identifier=user_identifier,
                user_message=user_message,
                all_memories="\n".join(all_memories)
            )

            response = self.client.chat.completions.create(
                model=Config.AI_MODEL2,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a memory selection tool. Return only valid JSON with selected memories."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=100
            )
            
            response_text = response.choices[0].message.content.strip()
            
            memories = self._process_memory_response(response_text, all_memories)
            
            if return_details:
                details = {
                    'model': Config.AI_MODEL2,
                    'temperature': 0.0,
                    'max_tokens': 100,
                    'prompt': prompt,
                    'response': response_text
                }
                return memories, details
            
            return memories
            
        except Exception as e:
            logger.error(f"Error selecting memories: {e}")
            return ("no relevant memories for this conversation", {}) if return_details else "no relevant memories for this conversation"

    def _process_memory_response(self, response_text: str, all_memories: list) -> str:
        """Process the memory response and return the selected memories."""
        try:
            # Clean any markdown formatting
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            # Handle potential JSON parsing errors due to special characters
            response_text = response_text.replace("'", "\\'").replace('"', '\\"')
            try:
                selection = json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract memories directly using regex
                import re
                memory_matches = re.findall(r'"([^"]+)"', response_text)
                if memory_matches:
                    selection = {"selected_memories": memory_matches}
                else:
                    logger.error(f"Could not parse memories from response: {response_text[:100]}...")
                    return "no relevant memories for this conversation"
            
            if not isinstance(selection, dict) or "selected_memories" not in selection:
                logger.error("Invalid response structure")
                return "no relevant memories for this conversation"
            
            valid_memories = [mem for mem in selection["selected_memories"] if mem in all_memories]
            
            if not valid_memories:
                return "no relevant memories for this conversation"
                
            return "\n".join(valid_memories)
                
        except Exception as e:
            logger.error(f"Error processing memory response: {e}\nRaw response: {response_text[:200]}")
            return "no relevant memories for this conversation"

    def get_all_memories(self) -> List[str]:
        """Get all memories from the database"""
        try:
            memories = self.db.get_memories()
            logger.info(f"Retrieved {len(memories) if memories else 0} memories")
            return memories if memories else []
        except Exception as e:
            logger.error(f"Error retrieving all memories: {e}")
            return []

    def get_memories_sync(self) -> List[str]:
        """Synchronous version of get_all_memories"""
        try:
            memories = self.db.get_memories_sync()
            logger.info(f"Retrieved {len(memories) if memories else 0} memories synchronously")
            return memories if memories else []
        except Exception as e:
            logger.error(f"Error retrieving memories synchronously: {e}")
            return []

# Create singleton instance
_memory_decision = MemoryDecision()

# Module-level function
def select_relevant_memories(user_identifier: str, user_message: str, return_details=False) -> Union[str, Tuple[str, dict]]:
    """Module-level function to select memories using singleton instance"""
    logger.info(f"Selecting memories for user {user_identifier} and message: {user_message}")
    memories = _memory_decision.select_relevant_memories(user_identifier, user_message)
    logger.info(f"Found {len(memories) if memories else 0} relevant memories")
    return memories