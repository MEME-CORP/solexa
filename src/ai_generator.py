# src/ai_generator.py

from openai import OpenAI
import random
import json
from src.config import Config
import logging
import os
import re
import os.path
import traceback
from src.database.supabase_client import DatabaseService
import yaml
from pathlib import Path
from src.memory_decision import MemoryDecision
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ai_generator')

class AIGenerator:
    def __init__(self, mode='twitter'):
        self.mode = mode
        
        # Initialize these first
        logger.info("Initializing AIGenerator")
        self.db = DatabaseService()
        self.memories = None
        
        # Load formats for all modes (needed for transform_message)
        self.length_formats = self.load_length_formats()
        self.emotion_formats = self.load_emotion_formats()
        
        # Mode-specific settings
        if mode == 'twitter':
            self.max_tokens = 70
            self.temperature = 0.0
        elif mode == 'discord':
            self.max_tokens = 40
            self.temperature = 0.9
        else:  # telegram or other
            self.max_tokens = 70
            self.temperature = 0.9
            
        # Load appropriate system prompt based on mode
        self.system_prompt = self._load_system_prompt()
        
        # Add transformation system prompt
        self.transform_system_prompt = self._load_transform_system_prompt()
        
        # Initialize OpenAI client with Gemini configuration
        self.client = OpenAI(
            api_key=Config.GEMINI_API_KEY,
            base_url=Config.GEMINI_BASE_URL
        )
        
        # Use Gemini models
        self.model = Config.GEMINI_MODEL
        
        # Initialize memory decision
        self.memory_decision = MemoryDecision()
        
        # Load memories using memory_decision instead of direct db access
        logger.info("Loading memories")
        try:
            self.memories = self.memory_decision.get_memories_sync()
            logger.info(f"Successfully loaded {len(self.memories)} memories")
        except Exception as e:
            logger.error(f"Error loading memories: {e}")
            self.memories = []

        # Load bot prompts
        self.bot_prompts = self._load_bot_prompts()
        
        logger.info(f"Initialization complete. Memories loaded: {bool(self.memories)}")

    def load_length_formats(self):
        """Load length formats from JSON file"""
        try:
            # Get the path to the length_formats.json file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'length_formats.json')
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    logger.warning("No length formats found in file")
                    return [{"format": "one short sentence", "description": "Single concise sentence"}]
                return formats
                
        except Exception as e:
            logger.error(f"Error loading length formats from file: {e}")
            return [{"format": "one short sentence", "description": "Single concise sentence"}]

    def load_emotion_formats(self):
        """Load emotion formats from JSON file"""
        try:
            # Get the path to the emotion_formats.json file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'emotion_formats.json')
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    logger.warning("No emotion formats found in file")
                    return [{"format": "default response", "description": "Standard emotional response"}]
                return formats
                
        except Exception as e:
            logger.error(f"Error loading emotion formats from file: {e}")
            return [{"format": "default response", "description": "Standard emotional response"}]

    def load_memories(self):
        """Load memories from database through memory decision"""
        try:
            memories = self.memory_decision.get_all_memories()
            logger.info(f"Successfully loaded {len(memories)} memories")
            return memories
        except Exception as e:
            logger.error(f"Error loading memories: {str(e)}")
            return []

    def load_narrative(self):
        """Load narrative context"""
        try:
            story_circle = self.db.get_story_circle_sync()
            if story_circle:
                logger.info("Narrative content:")
                logger.info(f"Current Phase: {story_circle.get('current_phase')}")
                logger.info(f"Events count: {len(story_circle.get('events', []))}")
                logger.info(f"Dialogues count: {len(story_circle.get('dialogues', []))}")
                logger.info(f"Current Event: {story_circle.get('dynamic_context', {}).get('current_event')}")
                logger.info(f"Current Inner Dialogue: {story_circle.get('dynamic_context', {}).get('current_inner_dialogue')}")
                
                # Verify events and dialogues are present
                events = story_circle.get('events', [])
                dialogues = story_circle.get('dialogues', [])
                if events and dialogues:
                    logger.info("Sample of events and dialogues:")
                    for i, (event, dialogue) in enumerate(zip(events[:2], dialogues[:2])):
                        logger.info(f"Event {i+1}: {event}")
                        logger.info(f"Dialogue {i+1}: {dialogue}")
                
                return story_circle
            else:
                logger.warning("No story circle found in database")
                return None
        except Exception as e:
            logger.error(f"Error loading narrative: {e}")
            return None

    def _load_bot_prompts(self):
        """Load bot prompts from YAML file"""
        try:
            prompts_path = Path(__file__).parent / 'prompts_config' / 'bot_prompts.yaml'
            with open(prompts_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading bot prompts: {e}")
            return {}

    def _prepare_messages(self, **kwargs):
        """Prepare messages for API call - exposed for testing"""
        logger.info("Starting message preparation with mode: %s", self.mode)
        
        # Modified memory handling
        memories = kwargs.get('memories', self.memories)
        memory_context = (
            "no relevant memories for this conversation" 
            if not memories
            else memories if isinstance(memories, (str, list))
            else "no relevant memories for this conversation"
        )
        
        # Add logging for memory selection output
        logger.info("Selected memories for context:")
        logger.info("----------------------------------------")
        logger.info(memory_context)
        logger.info("----------------------------------------")
        
        # If memories is a list, format it properly
        if isinstance(memory_context, list):
            memory_context = "\n".join(f"- {memory}" for memory in memory_context)
        
        logger.debug("Memory context prepared: %s", memory_context[:100] + "..." if len(str(memory_context)) > 100 else memory_context)
        
        # Set empty values for narrative elements
        phase_events = "No narrative events"
        phase_dialogues = "No narrative dialogues"
        current_event = ""
        inner_dialogue = ""
        
        # Get the appropriate prompt template based on mode
        if self.mode == 'twitter':
            prompt_template = self.bot_prompts.get('twitter', {}).get('content_prompt', '')
            
            # Check for crypto news if provided
            crypto_news = kwargs.get('crypto_news', '')
            
            # Randomly choose between memories, current instructions, or crypto news
            choice = random.random()
            use_memories = choice < 0.1  # 10% chance to use memories
            use_crypto_news = 0.1 <= choice < 0.6  # 50% chance to use crypto news
            
            logger.info("Content generation mode: %s", 
                       "Using memories" if use_memories else 
                       "Using crypto news" if use_crypto_news else 
                       "Using current instructions")
            
            if use_memories:
                # When using memories, we can now just focus on memories
                # Ensure we're using the memory context
                if self.memories:
                    memory_context = random.choice(self.memories) if isinstance(self.memories, list) else self.memories
                    logger.info(f"Selected memory for generation: {memory_context}")
                else:
                    logger.warning("No memories available for selection")
                    memory_context = "no memories available"
                
                tweet_content = "one of your memories randomly"
                
            elif use_crypto_news and crypto_news:
                # Use crypto news as the tweet content
                tweet_content = f"the following crypto news: {crypto_news}"
                logger.info(f"Using crypto news for tweet: {crypto_news[:100]}...")
                
            else:
                # Default case - use general instructions
                tweet_content = (
                    f"user_message: {kwargs.get('user_message', '')[9:].strip()}" if kwargs.get('user_message', '').startswith('reply to:')
                    else "something interesting about cryptocurrency"
                )
            
            # If using memories, refresh them from database
            if use_memories:
                logger.info("Fetching fresh memories from database")
                self.memories = self.db.get_memories()
                if self.memories:
                    logger.info("Successfully retrieved %d memories", len(self.memories))
                else:
                    logger.warning("No memories found in database")
            
            emotion_format = random.choice(self.emotion_formats)['format']
            length_format = random.choice(self.length_formats)['format']
            
            logger.info("Preparing Twitter prompt with variables:")
            logger.info("- Tweet content: %s", tweet_content)
            logger.info("- Emotion format: %s", emotion_format)
            logger.info("- Length format: %s", length_format)
            
            content_prompt = prompt_template.format(
                tweet_content=tweet_content,
                length_format=length_format,
                emotion_format=emotion_format,
                memory_context=memory_context,
                conversation_context=kwargs.get('conversation_context', ''),
                # Still include these placeholders but with empty values
                phase_events=phase_events,
                phase_dialogues=phase_dialogues,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )
            
            logger.debug("Generated content prompt: %s", content_prompt[:200] + "..." if len(content_prompt) > 200 else content_prompt)
        else:
            # Discord and Telegram format
            prompt_template = self.bot_prompts.get('discord_telegram', {}).get('content_prompt', '')
            emotion_format = random.choice(self.emotion_formats)['format']
            
            content_prompt = prompt_template.format(
                conversation_context=kwargs.get('conversation_context', ''),
                username=kwargs.get('username') or kwargs.get('user_id'),
                user_message=kwargs.get('user_message', ''),
                emotion_format=emotion_format,
                memory_context=memory_context,
                # Include empty placeholders for narrative elements
                phase_events=phase_events,
                phase_dialogues=phase_dialogues,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )

        # Format the system prompt with context variables
        formatted_system_prompt = self.system_prompt.format(
            emotion_format=emotion_format,
            length_format="one short sentence" if self.mode != 'twitter' else length_format,
            memory_context=memory_context,
            phase_events=phase_events,
            phase_dialogues=phase_dialogues
        )

        messages = [
            {
                "role": "system",
                "content": formatted_system_prompt
            },
            {
                "role": "user",
                "content": content_prompt
            }
        ]

        return messages

    def generate_content(self, **kwargs):
        """Generate content synchronously"""
        try:
            logger.info("Starting content generation with mode: %s", self.mode)
            
            # Get relevant memories for all modes
            user_id = kwargs.get('user_id', '')
            user_message = kwargs.get('user_message', '')
            
            try:
                # Select relevant memories based on user message for all modes
                memories = self.memory_decision.select_relevant_memories(
                    user_id or 'system',
                    user_message or 'generate content'
                )
                if memories and memories != "no relevant memories for this conversation":
                    kwargs['memories'] = memories
                    logger.info(f"Retrieved relevant memories for user {user_id or 'system'}")
                else:
                    # If no relevant memories, use a single random memory for variety
                    all_memories = self.memories or []
                    kwargs['memories'] = random.choice(all_memories) if all_memories else "no memories available"
                    logger.info("Using random memory due to no relevant matches")
            except Exception as e:
                logger.error(f"Error selecting memories: {e}")
                kwargs['memories'] = "no memories available"
            
            # Check if marketcap data is provided and add it to the prompt
            marketcap_data = kwargs.get('marketcap_data')
            if marketcap_data:
                # Format marketcap data in a more comprehensive way
                if 'formatted_value' in marketcap_data:
                    # This is data from CryptoDataService with additional info
                    ticker = marketcap_data['ticker']
                    name = marketcap_data.get('name', '')
                    marketcap_info = f"The current marketcap of {name} ({ticker}) is {marketcap_data['formatted_value']}."
                    
                    # Add price data if available
                    if 'price' in marketcap_data:
                        price = f"${marketcap_data['price']:.2f}" if marketcap_data['price'] < 100 else f"${int(marketcap_data['price']):,}"
                        marketcap_info += f" The current price is {price}."
                    
                    # Add 24h change if available
                    if 'percent_change_24h' in marketcap_data:
                        change = marketcap_data['percent_change_24h']
                        direction = "up" if change >= 0 else "down"
                        marketcap_info += f" It's {direction} {abs(change):.2f}% in the last 24 hours."
                else:
                    # This is the original format from wallet_manager
                    formatted_mc = (
                        f"${marketcap_data['value']/1000000000:.2f}B" if marketcap_data['value'] >= 1000000000
                        else f"${marketcap_data['value']/1000000:.2f}M" if marketcap_data['value'] >= 1000000
                        else f"${marketcap_data['value']:.2f}"
                    )
                    marketcap_info = f"The current marketcap of {marketcap_data['ticker']} is {formatted_mc}."
                
                # Add to user message for context but also create a special instruction
                if kwargs.get('user_message'):
                    kwargs['user_message'] = f"{kwargs['user_message']} [FACT: {marketcap_info}]"
                
                # Add to system message instruction to ensure it's included in response
                messages = self._prepare_messages(**kwargs)
                
                # Insert a special instruction to ensure market cap is included in the response
                special_instruction = {
                    "role": "system",
                    "content": f"Make sure to include this important factual information in your response: {marketcap_info} This data is current and accurate."
                }
                
                # Insert the special instruction after the system message
                messages.insert(1, special_instruction)
            else:
                messages = self._prepare_messages(**kwargs)
            
            # Add detailed logging of the complete system prompt
            if self.mode == 'twitter':
                logger.info("Complete Twitter system prompt:")
                logger.info("----------------------------------------")
                for msg in messages:
                    logger.info(f"Role: {msg['role']}")
                    logger.info(f"Content:\n{msg['content']}")
                logger.info("----------------------------------------")
            
            logger.info("Generating content with configuration:")
            logger.info("- Model: %s", self.model)
            logger.info("- Temperature: %s", self.temperature)
            logger.info("- Max tokens: %s", self.max_tokens)
            
            # Log the messages being sent to the LLM
            logger.info("Messages being sent to LLM:")
            for msg in messages:
                logger.info("Role: %s", msg["role"])
                logger.info("Content preview: %s", msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"])
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                
                generated_content = response.choices[0].message.content
                
            except Exception as api_error:
                logger.error(f"Gemini API error: {str(api_error)}")
                
                # Fall back to alternative model if primary fails
                if self.model == Config.GEMINI_MODEL:
                    logger.info("Falling back to alternative Gemini model")
                    self.model = "gemini-1.5-flash"  # Fallback model
                    
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
                    
                    generated_content = response.choices[0].message.content
                else:
                    raise
            
            # Log LLM response details
            logger.info("LLM Response Details:")
            logger.info("- Response length: %d characters", len(generated_content))
            logger.info("- First 100 chars: %s", generated_content[:100])
            logger.info("- Usage tokens: %s", getattr(response, 'usage', {}))
            
            # Validate response
            if not generated_content or not isinstance(generated_content, str):
                logger.error("Invalid response generated")
                raise ValueError("Generated content is invalid")
            
            if self.mode == 'twitter' and len(generated_content) > 280:
                logger.warning("Generated content exceeds Twitter limit, truncating from %d characters", len(generated_content))
                generated_content = generated_content[:277] + "..."
            
            logger.info("Successfully generated content:")
            logger.info("- Content length: %d characters", len(generated_content))
            logger.info("- Generated content: %s", generated_content)
            
            return generated_content

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            logger.error(f"Context: memories={self.memories}")
            raise

    def _load_system_prompt(self):
        """Load system prompt based on mode"""
        try:
            # Use system_prompt.yaml for all modes (Twitter, Telegram, and Discord)
            prompt_file = 'system_prompt.yaml'
            
            prompt_path = Path(__file__).parent / 'prompts_config' / prompt_file
            with open(prompt_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if 'system_prompt' in config:
                    logger.info(f"Successfully loaded system prompt for {self.mode} mode")
                    return config['system_prompt']
                logger.error(f"No system_prompt found in {prompt_file}")
                return ""
        except Exception as e:
            logger.error(f"Error loading system prompt for {self.mode} mode: {e}")
            return ""

    def get_memories_sync(self):
        """Get memories synchronously for response generation"""
        try:
            if not self.memories:  # If memories aren't loaded or are empty
                self.memories = self.db.get_memories_sync()
                logger.info(f"Retrieved {len(self.memories)} memories from database")
            return self.memories
        except Exception as e:
            logger.error(f"Error getting memories synchronously: {e}")
            return []

    def _load_transform_system_prompt(self):
        """Load transformation system prompt"""
        try:
            # Load the transformation prompt from YAML file
            prompt_file = 'transform_system_prompt.yaml'
            
            # Use absolute path to ensure file is found regardless of working directory
            prompt_path = Path(__file__).parent / 'prompts_config' / prompt_file
            
            logger.info(f"Attempting to load transform prompt from: {prompt_path}")
            
            # Check if file exists with more detailed logging
            if not prompt_path.exists():
                logger.warning(f"Transform system prompt file not found at: {prompt_path}")
                # Try alternate location as fallback (project root)
                alt_path = Path(__file__).parent.parent / 'src' / 'prompts_config' / prompt_file
                if alt_path.exists():
                    prompt_path = alt_path
                    logger.info(f"Found transform prompt at alternate location: {alt_path}")
                else:
                    logger.error(f"Transform system prompt not found at alternate location either: {alt_path}")
                    return ""
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if 'system_prompt' in config:
                    prompt_content = config['system_prompt']
                    # Log first 100 chars to verify content
                    logger.info(f"Successfully loaded transformation system prompt: {prompt_content[:100]}...")
                    return prompt_content
                logger.error(f"No system_prompt found in {prompt_file}")
                return ""
        except Exception as e:
            logger.error(f"Error loading transformation system prompt: {e}")
            logger.error(traceback.format_exc())
            return ""

    def _prepare_transform_messages(self, **kwargs):
        """Prepare messages for transformation API call"""
        logger.info("Preparing message transformation with mode: %s", self.mode)
        
        # Check if transform system prompt is loaded
        if not self.transform_system_prompt:
            logger.warning("Transform system prompt is empty, attempting to reload")
            self.transform_system_prompt = self._load_transform_system_prompt()
            
            # If still empty after reload attempt, use a simplified default prompt
            if not self.transform_system_prompt:
                logger.warning("Using default transform prompt as fallback")
                self.transform_system_prompt = "You are Solexa, a crypto expert. Transform the user's message into your distinctive style while preserving the original meaning. Use a casual, crypto-savvy tone with British slang."
        
        # Use the same emotion and length formats for consistency
        emotion_format = random.choice(self.emotion_formats)['format']
        length_format = kwargs.get('length_format', random.choice(self.length_formats)['format'])
        
        # Format the transformation system prompt with the same variables
        try:
            formatted_system_prompt = self.transform_system_prompt.format(
                emotion_format=emotion_format,
                length_format=length_format,
                memory_context="transformation context",
                phase_events="",
                phase_dialogues=""
            )
            logger.info(f"Formatted system prompt length: {len(formatted_system_prompt)}")
        except Exception as e:
            logger.error(f"Error formatting transform system prompt: {e}")
            formatted_system_prompt = self.transform_system_prompt  # Use unformatted as fallback
        
        # Create user prompt that clearly instructs transformation
        user_message = kwargs.get('user_message', '')
        user_prompt = f"Transform this message into your own words and style while maintaining the original meaning: {user_message}"
        
        messages = [
            {"role": "system", "content": formatted_system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Log the first part of the system prompt to verify it's being sent
        logger.info(f"System prompt preview: {formatted_system_prompt[:150]}...")
        
        return messages

    def transform_message(self, **kwargs):
        """Transform user message into Solexa's style"""
        try:
            logger.info("Starting message transformation with mode: %s", self.mode)
            
            # Ensure memories are loaded for context
            if not self.memories:
                logger.info("No memories loaded, fetching memories for context")
                self.memories = self.get_memories_sync()
            
            # Add memory context to kwargs if user didn't provide specific memories
            if 'memories' not in kwargs and self.memories:
                # Pick a few random memories for context variety
                random_memories = random.sample(self.memories, min(3, len(self.memories)))
                kwargs['memories'] = random_memories
                logger.info(f"Added {len(random_memories)} random memories for context")
            
            # Prepare messages for transformation
            messages = self._prepare_transform_messages(**kwargs)
            
            # Log the messages being sent to the LLM
            logger.info("Transformation messages being sent to LLM:")
            for msg in messages:
                logger.info("Role: %s", msg["role"])
                logger.info("Content preview: %s", msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"])
            
            # Use the same model and parameters as generate_content
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            transformed_content = response.choices[0].message.content
            
            # Apply the same validation and character limits
            if self.mode == 'twitter' and len(transformed_content) > 280:
                logger.warning("Transformed content exceeds Twitter limit, truncating from %d characters", len(transformed_content))
                transformed_content = transformed_content[:277] + "..."
            
            logger.info("Successfully transformed message:")
            logger.info("- Content length: %d characters", len(transformed_content))
            logger.info("- Transformed content: %s", transformed_content)
            
            return transformed_content
            
        except Exception as e:
            logger.error(f"Error transforming message: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            raise

    def generate_content_with_image(self, image_path, prompt, **kwargs):
        """Generate content with image input"""
        import base64
        
        # Function to encode the image
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        
        # Getting the base64 string
        base64_image = encode_image(image_path)
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        return response.choices[0].message.content

    def generate_image(self, prompt, **kwargs):
        """Generate an image based on a text prompt using Gemini's capabilities
        
        Args:
            prompt (str): The prompt describing the image to generate
            **kwargs: Additional parameters for image generation
            
        Returns:
            dict: Response containing the generated image data or error information
        """
        logger.info(f"Generating image with prompt: {prompt[:100]}..." if len(prompt) > 100 else prompt)
        
        try:
            # Note: As of current implementation, Gemini might not directly support image generation
            # through the OpenAI-compatible interface used in this code
            # This implementation tries to accommodate that limitation
            
            # First, enhance the prompt to get better results
            enhancement_messages = [
                {"role": "system", "content": "You are Solexa, an AI assistant helping to generate detailed image descriptions. Take the user's image request and enhance it with vivid details for better image generation results."},
                {"role": "user", "content": f"Enhance this image prompt with vivid details while keeping the same meaning (don't make it too long): {prompt}"}
            ]
            
            enhancement_response = self.client.chat.completions.create(
                model=self.model,
                messages=enhancement_messages,
                temperature=0.7,
                max_tokens=150
            )
            
            enhanced_prompt = enhancement_response.choices[0].message.content
            logger.info(f"Enhanced image prompt: {enhanced_prompt}")
            
            # Config for image generation
            api_base_url = kwargs.get('api_base_url', Config.IMAGE_API_URL)
            api_key = kwargs.get('api_key', Config.IMAGE_API_KEY) 
            
            # Check if we have necessary config for external image API
            if api_base_url and api_key:
                import requests
                
                # Prepare request to external image generation API
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                data = {
                    "prompt": enhanced_prompt,
                    "n": 1,
                    "size": kwargs.get("size", "1024x1024")
                }
                
                # Make the request to the image API
                response = requests.post(f"{api_base_url}/images/generations", headers=headers, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info("Successfully generated image through external API")
                    return {
                        "url": result["data"][0]["url"],
                        "success": True
                    }
                else:
                    logger.error(f"External API error: {response.text}")
                    return {
                        "error": f"External API error: {response.status_code}",
                        "success": False,
                        "enhanced_prompt": enhanced_prompt
                    }
            else:
                # If no external API is configured, return the enhanced prompt
                logger.warning("No image generation API configured. Returning enhanced prompt only.")
                return {
                    "success": False,
                    "message": "Direct image generation not available. Enhanced prompt provided.",
                    "enhanced_prompt": enhanced_prompt
                }
                
        except Exception as e:
            logger.error(f"Error in image generation process: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            
            return {
                "error": str(e),
                "success": False
            }

    def fetch_crypto_news(self, specific_topic=None):
        """Fetch latest cryptocurrency news from web search or specific topic"""
        logger.info(f"Fetching latest crypto news via web search{' for topic: ' + specific_topic if specific_topic else ''}")
        
        # Define different topics to ensure variety if no specific topic provided
        topic_categories = [
            "Latest regulatory developments in cryptocurrency",
            "Recent market movements in Bitcoin and Ethereum",
            "Corporate adoption of cryptocurrency news",
            "New cryptocurrency technology developments",
            "Government policy changes regarding cryptocurrency",
            "Cryptocurrency exchange updates and news"
        ]
        
        # If no specific topic provided, choose a random category to ensure variety
        if not specific_topic:
            specific_topic = random.choice(topic_categories)
        
        query = f"What are the latest {specific_topic} today? Format with clear section headers."
        
        logger.info(f"Making web search request with query: {query}")
        
        try:
            # Initialize OpenAI client for search model
            search_client = OpenAI(
                api_key=Config.OPENAI_API_KEY,
                base_url="https://api.openai.com/v1"  # Use standard OpenAI API endpoint
            )
            
            # Make request to GPT-4o mini search preview with correct parameter format
            completion = search_client.chat.completions.create(
                model="gpt-4o-mini-search-preview",
                messages=[{
                    "role": "user",
                    "content": query
                }],
                web_search_options={
                    "search_context_size": "medium"
                }
            )
            
            # Extract and log news content
            news_content = completion.choices[0].message.content
            
            # Extract citations if available
            citations = []
            if hasattr(completion.choices[0].message, 'annotations') and completion.choices[0].message.annotations:
                for annotation in completion.choices[0].message.annotations:
                    if annotation.type == "url_citation":
                        citation = {
                            "title": annotation.url_citation.title,
                            "url": annotation.url_citation.url
                        }
                        citations.append(citation)
            
            logger.info(f"Retrieved crypto news: {news_content[:100]}...")
            logger.info(f"Found {len(citations)} citations")
            
            return {
                "content": news_content,
                "citations": citations
            }
        except Exception as e:
            logger.error(f"Error fetching crypto news: {e}")
            logger.error(traceback.format_exc())
            return {
                "content": "Unable to fetch latest crypto news at this time.",
                "citations": []
            }

    def transform_crypto_news(self, news_data):
        """Transform crypto news into Solexa's style using the transform system prompt"""
        logger.info("Transforming crypto news into Solexa's style")
        
        try:
            # Extract content and prepare for transformation
            news_content = news_data.get("content", "")
            if not news_content or news_content == "Unable to fetch latest crypto news at this time.":
                return "chur team, tried to grab the latest crypto goss but the web's acting up. we'll try again soon, yeah?"
            
            # Prepare messages for transformation
            messages = [
                {"role": "system", "content": self.transform_system_prompt},
                {"role": "user", "content": f"Transform this crypto news into your own words and style: {news_content}"}
            ]
            
            # Generate transformed content
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=self.max_tokens * 2,  # Allow longer responses for news
            )
            
            transformed_content = response.choices[0].message.content
            
            # Ensure we don't exceed Twitter's character limit
            if self.mode == 'twitter' and len(transformed_content) > 280:
                transformed_content = transformed_content[:277] + "..."
            
            logger.info(f"Transformed news content: {transformed_content[:100]}...")
            return transformed_content
            
        except Exception as e:
            logger.error(f"Error transforming crypto news: {e}")
            logger.error(traceback.format_exc())
            return "tried to scope some crypto buzz but my circuits are fried. back in a tick, yeah?"

    def fetch_and_store_crypto_news(self, count=5, specific_topic=None):
        """Fetch crypto news and store in database"""
        logger.info(f"Fetching and storing {count} crypto news items")
        
        # Define different topic categories to ensure variety
        topic_categories = [
            "regulatory developments in cryptocurrency",
            "market movements in cryptocurrency",
            "corporate adoption of cryptocurrency",
            "cryptocurrency technology innovations", 
            "cryptocurrency policy changes"
        ]
        
        stored_count = 0
        attempts = 0
        max_attempts = count * 2  # Allow extra attempts to reach desired count
        
        while stored_count < count and attempts < max_attempts:
            try:
                # Use a different topic category for each attempt to ensure variety
                current_topic = specific_topic
                if not current_topic:
                    current_topic = topic_categories[attempts % len(topic_categories)]
                
                # Fetch a news item with the current topic
                news_data = self.fetch_crypto_news(current_topic)
                
                # Skip if no valid content
                if not news_data or not news_data.get("content") or news_data.get("content") == "Unable to fetch latest crypto news at this time.":
                    logger.warning("No valid news content retrieved")
                    attempts += 1
                    continue
                    
                # Store in database - will return False if duplicate
                if self.db.store_crypto_news(news_data):
                    stored_count += 1
                    logger.info(f"Stored news item {stored_count}/{count} on topic: {current_topic}")
                    # Add a small delay between requests to avoid rate limiting
                    time.sleep(1)
                else:
                    logger.info("News item not stored (likely duplicate)")
                
                attempts += 1
                
            except Exception as e:
                logger.error(f"Error fetching and storing news: {e}")
                attempts += 1
        
        logger.info(f"Successfully stored {stored_count} news items after {attempts} attempts")
        return stored_count

    def get_crypto_news_for_tweet(self):
        """Get an unused crypto news item for tweet generation"""
        logger.info("Getting unused crypto news for tweet")
        
        # Check if we need to refresh the news
        unused_count = self.db.check_unused_crypto_news_count()
        
        # If no unused news, fetch and store new ones
        if unused_count == 0:
            logger.info("No unused news available, fetching new batch")
            stored_count = self.fetch_and_store_crypto_news(5)
            
            if stored_count == 0:
                logger.warning("Could not store any new news items")
                return None
            
            # Try to get a news item again
            news_item = self.db.get_unused_crypto_news()
        else:
            # Get a random unused news item
            news_item = self.db.get_unused_crypto_news()
        
        if not news_item:
            logger.warning("Could not retrieve any unused news")
            return None
        
        # Mark this news as used
        self.db.mark_crypto_news_as_used(news_item['id'])
        
        # Return in expected format for transformation
        return {
            "content": news_item['content'],
            "citations": news_item.get('sources', [])
        }

    def initialize_crypto_news(self):
        """Check if we need to populate initial crypto news"""
        try:
            # Check if we have any news stored
            count = self.db.check_unused_crypto_news_count()
            
            if count == 0:
                logger.info("No crypto news found in database, performing initial fetch")
                self.fetch_and_store_crypto_news(10)  # Get 10 news items initially
            else:
                logger.info(f"Found {count} unused crypto news items in database")
                
        except Exception as e:
            logger.error(f"Error initializing crypto news: {e}")

