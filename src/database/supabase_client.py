# src/database/supabase_client.py
from supabase import create_client
from src.config import Config
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Union
import os
import requests
import random

logger = logging.getLogger('database')

class DatabaseService:
    def __init__(self):
        """Initialize database service with storage access"""
        # Initialize Supabase client
        self.client = Config.get_supabase_client()
        logger.info("Initialized database service")
        # No bucket creation/checking - assume bucket exists

    def get_memories(self) -> List[str]:
        """Get all memories from database"""
        try:
            # Get memories directly from memories table
            response = self.client.table('memories').select('memory').execute()
            
            if response.data:
                memories = [record['memory'] for record in response.data]
                logger.info(f"Retrieved {len(memories)} memories from database")
                return memories
            
            return []
        except Exception as e:
            logger.error(f"Error fetching memories: {e}")
            return []

    def get_story_circle(self):
        """Get current story circle data with all related data"""
        try:
            # First, ensure only one story circle is current
            self._ensure_single_current_circle()
            
            # Get the current active story circle
            story = self.client.table('story_circle')\
                .select('*')\
                .eq('is_current', True)\
                .limit(1)\
                .single()\
                .execute()

            if not story.data:
                logger.info("No current story circle found, creating new one")
                return self.create_story_circle()

            story_circle_id = story.data['id']
            logger.info(f"Retrieved story circle {story_circle_id}")

            # Get narrative JSON and extract existing dynamic context
            narrative_json = story.data.get('narrative', {})
            existing_context = narrative_json.get('dynamic_context', {})
            logger.debug(f"Retrieved existing context: {existing_context}")

            # Get phases for this story circle
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .order('phase_number')\
                .execute()

            # Get current phase
            current_phase = next(
                (phase for phase in phases.data if phase.get('is_current', False)),
                phases.data[0] if phases.data else None
            )
            
            if not current_phase:
                current_phase = phases.data[0] if phases.data else None
                current_phase_number = 1
            else:
                current_phase_number = current_phase['phase_number']

            # Get events and dialogues for current phase
            events_dialogues = self.get_events_dialogues(story_circle_id, current_phase_number)
            
            # Extract events and dialogues
            events = [ed['event'] for ed in events_dialogues]
            dialogues = [ed['inner_dialogue'] for ed in events_dialogues]

            # Determine dynamic context based on existing data
            if existing_context.get("current_event"):
                # Keep existing dynamic context from narrative
                dynamic_context = {
                    "current_event": existing_context["current_event"],
                    "current_inner_dialogue": existing_context.get("current_inner_dialogue", ""),
                    "next_event": existing_context.get("next_event", "")
                }
                logger.info("Using existing dynamic context from narrative")
            else:
                # Initialize with first event if no existing context
                dynamic_context = {
                    "current_event": events[0] if events else "",
                    "current_inner_dialogue": dialogues[0] if dialogues else "",
                    "next_event": events[1] if len(events) > 1 else ""
                }
                logger.info("Initialized new dynamic context from first event")

            # Construct and return story circle data
            return {
                "id": story_circle_id,
                "current_phase": current_phase['phase_name'] if current_phase else 'You',
                "current_phase_number": current_phase_number,
                "is_current": story.data['is_current'],
                "phases": [
                    {
                        "phase": phase['phase_name'],
                        "phase_number": phase['phase_number'],
                        "description": phase['phase_description'] or ""
                    }
                    for phase in phases.data
                ],
                "events": events,
                "dialogues": dialogues,
                "dynamic_context": dynamic_context
            }

        except Exception as e:
            logger.error(f"Error fetching story circle: {e}")
            logger.exception("Full traceback:")
            return None

    def _ensure_single_current_circle(self):
        """Ensure only one story circle is marked as current"""
        try:
            # Get all current circles with explicit column selection
            current_circles = self.client.table('story_circle')\
                .select('id, is_current')\
                .eq('is_current', True)\
                .execute()
            
            if len(current_circles.data) > 1:
                logger.warning(f"Found {len(current_circles.data)} current story circles, fixing...")
                
                # Keep the most recent one current, using 'date' instead of 'created_at'
                most_recent = self.client.table('story_circle')\
                    .select('id')\
                    .eq('is_current', True)\
                    .order('date', desc=True)\
                    .limit(1)\
                    .single()\
                    .execute()
                
                if most_recent.data:
                    # Update all others to not current
                    self.client.table('story_circle')\
                        .update({'is_current': False})\
                        .neq('id', most_recent.data['id'])\
                        .eq('is_current', True)\
                        .execute()
                    
                    logger.info(f"Set story circle {most_recent.data['id']} as current")
            
        except Exception as e:
            logger.error(f"Error ensuring single current circle: {e}")
            raise

    def update_story_circle(self, story_circle):
        """Update story circle and its phases"""
        try:
            if 'narrative' not in story_circle:
                story_circle = {'narrative': story_circle}

            narrative = story_circle['narrative']
            
            # Validate required fields
            required_fields = ['events', 'next_phase', 'current_phase', 'dynamic_context', 
                             'inner_dialogues', 'current_story_circle']
            
            for field in required_fields:
                if field not in narrative:
                    logger.error(f"Missing required field in story circle: {field}")
                    return False

            # Save main story circle data
            result = self.client.table('story_circle').insert({
                'narrative': {
                    'events': narrative['events'],
                    'next_phase': narrative['next_phase'],
                    'current_phase': narrative['current_phase'],
                    'dynamic_context': narrative['dynamic_context'],
                    'inner_dialogues': narrative['inner_dialogues']
                }
            }).execute()

            if not result.data:
                logger.error("Failed to save story circle")
                return False

            story_circle_id = result.data[0]['id']

            # Save phases
            for phase in narrative['current_story_circle']:
                self.client.table('story_phases').insert({
                    'story_circle_id': story_circle_id,
                    'phase': phase['phase'],
                    'description': phase['description']
                }).execute()

            return True

        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            return False

    def get_circle_memories_sync(self):
        """Get circle memories synchronously"""
        try:
            response = self.client.table('circle_memories').select('memory').execute()
            if response.data:
                return {"memories": [record['memory'] for record in response.data]}
            return {"memories": []}
        except Exception as e:
            logger.error(f"Error fetching circle memories synchronously: {e}")
            return {"memories": []}

    def update_circle_memories(self, circles_memory):
        """Update circle memories in database - unified method"""
        try:
            self.client.table('circle_memories').upsert({
                'memories': circles_memory
            }).execute()
        except Exception as e:
            logger.error(f"Error updating circle memories: {e}")
            raise

    def get_topics(self):
        """Get all topics"""
        try:
            response = self.client.table('topics').select('topic').execute()
            return [{'topic': record['topic']} for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching topics: {e}")
            return []

    def get_emotion_formats(self):
        """Get all emotion formats"""
        try:
            response = self.client.table('emotion_formats').select('*').execute()
            return [{'format': record['format'], 'description': record['description']} 
                   for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching emotion formats: {e}")
            return []

    def get_length_formats(self):
        """Get all length formats"""
        try:
            response = self.client.table('length_formats').select('*').execute()
            return [{'format': record['format'], 'description': record['description']} 
                   for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching length formats: {e}")
            return []

    def get_processed_tweets(self):
        """Get all processed tweet IDs"""
        try:
            response = self.client.table('processed_tweets').select('tweet_id').execute()
            return [record['tweet_id'] for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching processed tweets: {e}")
            return []

    def add_memories(self, new_memories: List[str]) -> None:
        """Add new memories to database"""
        try:
            # Insert each memory as a separate record
            for memory in new_memories:
                response = self.client.table('memories').insert({
                    'memory': memory
                }).execute()
                
            logger.info(f"Added {len(new_memories)} new memories to database")
                    
        except Exception as e:
            logger.error(f"Error adding memories: {e}")
            raise

    def create_story_circle(self):
        """Create a new story circle"""
        try:
            # First ensure no other circles are current
            self._ensure_single_current_circle()
            
            # Create new story circle entry with minimal required fields
            story = self.client.table('story_circle').insert({
                'is_current': True,
                'narrative': {}
            }).execute()

            if not story.data:
                raise Exception("Failed to create story circle")

            story_circle_id = story.data[0]['id']
            logger.info(f"Created new story circle {story_circle_id}")

            # Set phases of old story circles to not current
            try:
                # Get IDs of completed story circles
                completed_circles = self.client.table('story_circle')\
                    .select('id')\
                    .eq('is_current', False)\
                    .execute()
                
                if completed_circles.data:
                    # Update phases for completed circles
                    completed_ids = [circle['id'] for circle in completed_circles.data]
                    for circle_id in completed_ids:
                        self.client.table('story_phases')\
                            .update({'is_current': False})\
                            .eq('story_circle_id', circle_id)\
                            .execute()
                    
                    logger.info(f"Reset phases for {len(completed_ids)} completed story circles")
            except Exception as e:
                logger.error(f"Error resetting old phases: {e}")
                # Continue with creation even if reset fails

            # Create initial phases
            phase_order = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
            for i, phase_name in enumerate(phase_order, 1):
                self.client.table('story_phases').insert({
                    'story_circle_id': story_circle_id,
                    'phase_name': phase_name,
                    'phase_number': i,
                    'phase_description': '',
                    'is_current': i == 1  # First phase is current
                }).execute()

            logger.info(f"Created phases for story circle {story_circle_id}")

            # Return the newly created circle
            return self.get_story_circle()

        except Exception as e:
            logger.error(f"Error creating story circle: {e}")
            raise

    def update_story_circle_state(self, story_circle):
        """Update story circle state including phases and events"""
        try:
            story_circle_id = story_circle['id']
            
            # Update only the is_current flag and narrative
            update_data = {
                'is_current': story_circle.get('is_current', True),
                'narrative': {
                    'current_phase': story_circle['current_phase'],
                    'current_phase_number': story_circle['current_phase_number'],
                    'events': story_circle['events'],
                    'dialogues': story_circle['dialogues'],
                    'dynamic_context': story_circle['dynamic_context']
                }
            }
            
            logger.info(f"Updating story circle with data: {json.dumps(update_data, indent=2)}")
            
            # Update the story circle
            self.client.table('story_circle')\
                .update(update_data)\
                .eq('id', story_circle_id)\
                .execute()
            
            # Update phases
            for phase in story_circle['phases']:
                phase_update = {
                    'phase_name': phase['phase'],
                    'phase_number': phase['phase_number'],
                    'phase_description': phase['description'],
                    'is_current': phase['phase'] == story_circle['current_phase']
                }
                
                self.client.table('story_phases')\
                    .update(phase_update)\
                    .eq('story_circle_id', story_circle_id)\
                    .eq('phase_name', phase['phase'])\
                    .execute()
            
            # Get current phase number
            current_phase_number = story_circle['current_phase_number']
            
            # Clear existing events/dialogues for current phase
            self.client.table('events_dialogues')\
                .delete()\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_number', current_phase_number)\
                .execute()
            
            # Insert new events/dialogues for current phase with event_order
            events_dialogues = [
                {
                    'story_circle_id': story_circle_id,
                    'phase_number': current_phase_number,
                    'event': event,
                    'inner_dialogue': dialogue,
                    'event_order': idx + 1
                }
                for idx, (event, dialogue) in enumerate(zip(story_circle['events'], story_circle['dialogues']))
            ]
            
            # Log the events being inserted
            logger.debug(f"Inserting events/dialogues: {json.dumps(events_dialogues, indent=2)}")
            
            # Insert events one by one to better handle any errors
            for event_data in events_dialogues:
                try:
                    self.client.table('events_dialogues').insert(event_data).execute()
                    logger.debug(f"Successfully inserted event {event_data['event_order']}")
                except Exception as e:
                    logger.error(f"Error inserting event {event_data['event_order']}: {e}")
                    raise
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating story circle state: {e}")
            logger.exception("Full traceback:")
            raise

    def insert_circle_memories(self, story_circle_id, memories):
        """Insert memories for a completed story circle"""
        try:
            # Validate inputs
            if not story_circle_id or not memories:
                logger.error("Invalid inputs for circle memories")
                return False
            
            # Ensure memories is a list
            if not isinstance(memories, list):
                memories = [memories]
            
            # Insert memories with timestamp
            result = self.client.table('circle_memories').insert({
                'story_circle_id': story_circle_id,
                'memory': memories,  # Store as list
                'date': datetime.now().isoformat()
            }).execute()
            
            if not result.data:
                logger.error("No data returned from memory insertion")
                return False
            
            logger.info(f"Successfully added memories for story circle {story_circle_id}")
            logger.debug(f"Inserted memories: {memories}")
            return True
            
        except Exception as e:
            logger.error(f"Error inserting circle memories: {e}")
            logger.exception("Full traceback:")
            return False

    def get_circle_memories(self):
        """Get all circle memories"""
        try:
            response = self.client.table('circle_memories').select('memory').execute()
            # Transform the response to match expected format
            memories = []
            for record in response.data:
                if record.get('memory'):
                    if isinstance(record['memory'], list):
                        memories.extend(record['memory'])
                    else:
                        memories.append(record['memory'])
            # Return in expected format
            return {"memories": memories}
        except Exception as e:
            logger.error(f"Error getting circle memories: {e}")
            return {"memories": []}

    def update_story_circle(self, story_circle_id, updates):
        """Update specific story circle fields - synchronous"""
        try:
            self.client.table('story_circle')\
                .update(updates)\
                .eq('id', story_circle_id)\
                .execute()
        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            raise

    def get_story_phases(self, story_circle_id=None):
        """Get phases for story circle. If no ID provided, gets phases for current story circle"""
        try:
            if story_circle_id is None:
                # Get current story circle id
                story = self.client.table('story_circle')\
                    .select('id')\
                    .eq('is_current', True)\
                    .single()\
                    .execute()
                
                if not story.data:
                    logger.error("No current story circle found")
                    return []
                
                story_circle_id = story.data['id']
            
            # Get phases for this story circle
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .order('phase_number')\
                .execute()
            
            return phases.data
        
        except Exception as e:
            logger.error(f"Error fetching story phases: {e}")
            return []

    def get_events_dialogues(self, story_circle_id, phase_number):
        """Get events and dialogues for a phase, ordered by event_order"""
        try:
            query = self.client.table('events_dialogues')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_number', phase_number)\
                .order('event_order')
            
            result = query.execute()
            
            if not result.data:
                logger.warning(f"No events found for story_circle_id={story_circle_id}, phase={phase_number}")
                return []
            
            logger.info(f"Retrieved {len(result.data)} events in order")
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting events and dialogues: {e}")
            logger.error(f"Parameters: story_circle_id={story_circle_id}, phase_number={phase_number}")
            logger.exception("Full traceback:")
            return []

    def update_phase_description(self, story_circle_id: int, phase_name: str, description: str) -> bool:
        """Update a specific phase description"""
        try:
            # Log the update attempt
            logger.info(f"Updating phase description for story_circle_id={story_circle_id}, phase={phase_name}")
            logger.debug(f"New description: {description}")
            
            # Update the phase description
            response = self.client.table('story_phases')\
                .update({
                    'phase_description': description
                })\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_name', phase_name)\
                .execute()
            
            success = bool(response.data)
            if success:
                logger.info(f"Successfully updated phase description for {phase_name}")
                logger.debug(f"Updated description: {description}")
            else:
                logger.warning(f"No phase was updated - phase {phase_name} might not exist")
                
            return success
            
        except Exception as e:
            logger.error(f"Error updating phase description: {e}")
            logger.exception("Full traceback:")
            return False

    def sync_story_circle(self, memory_state):
        """Synchronize in-memory story circle state with database"""
        try:
            # Get current database state
            db_state = self.get_story_circle()
            if not db_state:
                logger.error("No story circle found in database")
                return memory_state

            # Compare states
            if self._states_match(memory_state, db_state):
                logger.info("Story circle states are synchronized")
                return memory_state

            logger.warning("Story circle state mismatch detected - reconciling...")
            return self._reconcile_story_states(memory_state, db_state)

        except Exception as e:
            logger.error(f"Error synchronizing story circle: {e}")
            raise

    def _states_match(self, memory_state, db_state):
        """Compare critical fields between memory and database states"""
        try:
            # Define critical fields to compare
            critical_fields = [
                'current_phase',
                'current_phase_number',
                'dynamic_context',
                'events',
                'dialogues'
            ]

            # Log comparison for debugging
            for field in critical_fields:
                if field not in memory_state or field not in db_state:
                    logger.warning(f"Missing field in state comparison: {field}")
                    return False
                
                if memory_state[field] != db_state[field]:
                    logger.info(f"Mismatch in {field}:")
                    logger.info(f"Memory: {memory_state[field]}")
                    logger.info(f"Database: {db_state[field]}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error comparing states: {e}")
            return False

    def _reconcile_story_states(self, memory_state, db_state):
        """Reconcile differences between memory and database states"""
        try:
            # Log initial state
            logger.info("Beginning state reconciliation")
            logger.debug(f"Memory state: {json.dumps(memory_state, indent=2)}")
            logger.debug(f"Database state: {json.dumps(db_state, indent=2)}")

            # Update critical fields from database state
            fields_to_sync = {
                'current_phase': 'Current phase',
                'current_phase_number': 'Phase number',
                'dynamic_context': 'Dynamic context',
                'events': 'Events',
                'dialogues': 'Dialogues'
            }

            for field, description in fields_to_sync.items():
                if memory_state.get(field) != db_state.get(field):
                    logger.warning(f"{description} mismatch detected - updating from database")
                    memory_state[field] = db_state[field]

            # Ensure phase descriptions are consistent
            if 'phases' in memory_state and 'phases' in db_state:
                for mem_phase, db_phase in zip(memory_state['phases'], db_state['phases']):
                    if mem_phase.get('description') != db_phase.get('description'):
                        logger.warning(f"Phase description mismatch for phase {mem_phase.get('phase')}")
                        mem_phase['description'] = db_phase['description']

            # Update event order if needed
            if 'events' in memory_state and 'events' in db_state:
                events_dialogues = self.get_events_dialogues(
                    memory_state['id'],
                    memory_state['current_phase_number']
                )
                if events_dialogues:
                    # Sort by event_order
                    events_dialogues.sort(key=lambda x: x.get('event_order', 0))
                    memory_state['events'] = [e['event'] for e in events_dialogues]
                    memory_state['dialogues'] = [e['inner_dialogue'] for e in events_dialogues]

            # Save reconciled state
            self.update_story_circle_state(memory_state)
            logger.info("State reconciliation completed")

            return memory_state

        except Exception as e:
            logger.error(f"Error reconciling states: {e}")
            logger.exception("Full traceback:")
            raise

    def verify_story_circle_state(self, story_circle):
        """Verify story circle state consistency"""
        try:
            # Check required fields
            required_fields = [
                'id', 'current_phase', 'current_phase_number',
                'is_current', 'phases', 'events', 'dialogues',
                'dynamic_context'
            ]

            missing_fields = [f for f in required_fields if f not in story_circle]
            if missing_fields:
                logger.error(f"Story circle missing required fields: {missing_fields}")
                return False

            # Verify phase consistency
            if not self._verify_phases(story_circle):
                return False

            # Verify events and dialogues
            if not self._verify_events_dialogues(story_circle):
                return False

            logger.info("Story circle state verification passed")
            return True

        except Exception as e:
            logger.error(f"Error verifying story circle state: {e}")
            return False

    def _verify_phases(self, story_circle):
        """Verify phase consistency"""
        try:
            phases = story_circle.get('phases', [])
            
            # Check phase order
            expected_phases = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
            phase_names = [p.get('phase') for p in phases]
            
            if phase_names != expected_phases:
                logger.error(f"Invalid phase order. Expected: {expected_phases}, Got: {phase_names}")
                return False

            # Verify current phase is valid
            if story_circle['current_phase'] not in expected_phases:
                logger.error(f"Invalid current phase: {story_circle['current_phase']}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error verifying phases: {e}")
            return False

    def _verify_events_dialogues(self, story_circle):
        """Verify events and dialogues consistency"""
        try:
            events = story_circle.get('events', [])
            dialogues = story_circle.get('dialogues', [])

            # Check events and dialogues match
            if len(events) != len(dialogues):
                logger.error(f"Events and dialogues length mismatch: {len(events)} vs {len(dialogues)}")
                return False

            # Verify dynamic context
            context = story_circle.get('dynamic_context', {})
            if context.get('current_event') and context['current_event'] not in events:
                logger.error("Current event not found in events list")
                return False

            return True

        except Exception as e:
            logger.error(f"Error verifying events and dialogues: {e}")
            return False

    def _get_next_phase(self, current_phase):
        """Get the next phase in the story circle"""
        phases = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
        current_index = phases.index(current_phase)
        next_index = (current_index + 1) % len(phases)
        return phases[next_index]

    def create_events_for_phase(self, story_circle_id, phase_number, events, dialogues):
        """Create events and dialogues for a phase"""
        try:
            # Validate inputs
            if len(events) != len(dialogues):
                logger.error("Events and dialogues must have same length")
                return False
            
            # Create events and dialogues - Updated to use inner_dialogue
            for i, (event, dialogue) in enumerate(zip(events, dialogues)):
                self.client.table('events_dialogues').insert({
                    'story_circle_id': story_circle_id,
                    'phase_number': phase_number,
                    'event_order': i + 1,
                    'event': event,
                    'inner_dialogue': dialogue  # Changed from 'dialogue' to 'inner_dialogue'
                }).execute()
            
            return True
        
        except Exception as e:
            logger.error(f"Error creating events for phase: {e}")
            return False

    def get_memories_sync(self):
        """Get memories synchronously - used by AI generator"""
        try:
            response = self.client.table('memories').select('memory').execute()
            if response.data:
                return [record['memory'] for record in response.data]
            return []
        except Exception as e:
            logger.error(f"Error fetching memories synchronously: {e}")
            return []

    def get_story_circle_sync(self):
        """Get current story circle data synchronously"""
        try:
            # Get current story circle
            response = self.client.table('story_circle')\
                .select('*')\
                .eq('is_current', True)\
                .limit(1)\
                .execute()

            if not response.data:
                logger.warning("No current story circle found")
                return None

            story_circle = response.data[0]
            
            # Extract narrative data
            narrative = story_circle.get('narrative', {})
            if not narrative:
                logger.warning("No narrative data found in story circle")
                return None

            # Get phases for this story circle
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story_circle['id'])\
                .order('phase_number')\
                .execute()

            # Extract events and dialogues directly from narrative JSONB
            events = narrative.get('events', [])
            dialogues = narrative.get('dialogues', [])
            logger.info(f"Retrieved {len(events)} events and {len(dialogues)} dialogues from narrative")

            # Structure the response
            return {
                'id': story_circle['id'],
                'is_current': story_circle['is_current'],
                'current_phase': narrative.get('current_phase', ''),
                'current_phase_number': narrative.get('current_phase_number', 1),
                'events': events,  # Add events from narrative
                'dialogues': dialogues,  # Add dialogues from narrative
                'dynamic_context': narrative.get('dynamic_context', {
                    'current_event': '',
                    'current_inner_dialogue': '',
                    'next_event': ''
                }),
                'phases': [
                    {
                        'phase': phase['phase_name'],
                        'phase_number': phase['phase_number'],
                        'description': phase.get('phase_description', '')
                    }
                    for phase in phases.data
                ] if phases.data else []
            }

        except Exception as e:
            logger.error(f"Error in get_story_circle_sync: {str(e)}")
            logger.exception("Full traceback:")
            return None

    def add_memory(self, memory: Union[dict, str]) -> bool:
        """
        Add a single memory to the database with proper ID sequencing.
        Accepts either a dictionary with full memory data or a string content.
        Returns True if successful, False otherwise.
        """
        try:
            # First get the current max ID
            max_id_response = self.client.table('memories')\
                .select('id')\
                .order('id', desc=True)\
                .limit(1)\
                .execute()
                
            # Calculate next ID
            next_id = 1  # Default if no records exist
            if max_id_response.data and len(max_id_response.data) > 0:
                next_id = max_id_response.data[0]['id'] + 1
                
            # Convert string input to memory dict if needed
            if isinstance(memory, str):
                memory = {
                    'memory': memory,
                    'created_at': datetime.now().isoformat()
                }
                
            # Ensure memory is a dict
            if not isinstance(memory, dict):
                logger.error("Invalid memory format")
                return False
                
            # Add required fields
            memory['id'] = next_id
            if 'created_at' not in memory:
                memory['created_at'] = datetime.now().isoformat()
                
            # Insert with explicit ID
            response = self.client.table('memories')\
                .insert(memory)\
                .execute()
                
            if response.data:
                logger.info(f"Successfully added memory to database with ID: {next_id}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error adding memory to database: {e}")
            logger.exception("Full traceback:")
            return False

    def add_processed_tweet(self, tweet_id: str) -> None:
        """Add a processed tweet ID to database"""
        try:
            # Check if tweet_id already exists
            existing = self.client.table('processed_tweets').select('tweet_id').eq('tweet_id', tweet_id).execute()
            
            if not existing.data:
                # Insert new tweet_id with processed_at timestamp
                self.client.table('processed_tweets').insert({
                    'tweet_id': tweet_id,
                    'processed_at': datetime.now().isoformat()
                }).execute()
                logger.debug(f"Added tweet ID {tweet_id} to processed tweets")
        except Exception as e:
            logger.error(f"Error adding processed tweet {tweet_id}: {e}")
            raise

    def insert_memory(self, memory_data: dict) -> bool:
        """Insert a memory into the database with proper validation"""
        try:
            # Ensure required fields with proper names
            required_fields = {
                'memory': str,
                'created_at': str
            }
            
            # Validate fields
            for field, field_type in required_fields.items():
                if field not in memory_data:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not isinstance(memory_data[field], field_type):
                    logger.error(f"Invalid type for field {field}")
                    return False
            
            # Clean memory data to match schema
            clean_memory_data = {
                'memory': memory_data['memory'],
                'created_at': memory_data['created_at']
            }
            
            # Insert memory
            response = self.client.table('memories')\
                .insert(clean_memory_data)\
                .execute()
            
            if response.data:
                logger.info(f"Successfully inserted memory: {clean_memory_data['memory'][:100]}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error inserting memory: {e}")
            logger.exception("Full traceback:")
            return False

    def store_crypto_news(self, news_data):
        """Store cryptocurrency news in the database"""
        try:
            # Extract content
            content = news_data.get("content", "")
            
            # Skip if content is too short
            if len(content) < 50:
                logger.warning("News content too short, skipping")
                return False
            
            # Check for duplicates by comparing first 100 characters
            content_start = content[:100]
            response = self.client.table('crypto_news')\
                .select('id')\
                .ilike('content', f'{content_start}%')\
                .execute()
            
            if response.data:
                logger.info(f"Similar content already exists in database, skipping")
                return False
            
            # Process citations
            sources = []
            for citation in news_data.get("citations", []):
                sources.append({
                    "title": citation.get("title", ""),
                    "url": citation.get("url", "")
                })
            
            # Extract categories from content if possible
            categories = []
            if "**Regulatory" in content:
                categories.append("Regulatory")
            if "**Corporate" in content:
                categories.append("Corporate")
            if "**Market" in content:
                categories.append("Market")
            
            # Extract a simple title if possible
            title = ""
            lines = content.split("\n")
            for line in lines:
                if line.strip() and not line.startswith("**") and not line.startswith("-"):
                    title = line.strip()
                    break
            
            # Insert the news item
            response = self.client.table('crypto_news').insert({
                'content': content,
                'title': title,
                'category': ", ".join(categories) if categories else "General",
                'summary': content[:200] + "..." if len(content) > 200 else content,
                'sources': sources,
                'retrieved_at': datetime.now().isoformat(),
                'used': False
            }).execute()
            
            logger.info(f"Stored new crypto news item with title: {title[:50]}...")
            return True if response.data else False
            
        except Exception as e:
            logger.error(f"Error storing crypto news: {e}")
            return False

    def get_unused_crypto_news(self):
        """Get a random unused news item from the database"""
        try:
            response = self.client.table('crypto_news')\
                .select('*')\
                .eq('used', False)\
                .execute()
            
            if not response.data:
                logger.info("No unused crypto news found")
                return None
            
            # Select a random news item
            news_item = random.choice(response.data)
            logger.info(f"Retrieved unused crypto news: {news_item.get('title', '')[:50]}...")
            return news_item
            
        except Exception as e:
            logger.error(f"Error getting unused crypto news: {e}")
            return None

    def mark_crypto_news_as_used(self, news_id):
        """Mark a news item as used"""
        try:
            response = self.client.table('crypto_news')\
                .update({'used': True, 'used_at': datetime.now().isoformat()})\
                .eq('id', news_id)\
                .execute()
            
            logger.info(f"Marked crypto news {news_id} as used")
            return True if response.data else False
            
        except Exception as e:
            logger.error(f"Error marking crypto news as used: {e}")
            return False

    def check_unused_crypto_news_count(self):
        """Check if there are any unused news items left"""
        try:
            response = self.client.table('crypto_news')\
                .select('id')\
                .eq('used', False)\
                .execute()
            
            count = len(response.data)
            logger.info(f"Found {count} unused crypto news items")
            return count
            
        except Exception as e:
            logger.error(f"Error checking unused crypto news count: {e}")
            return 0

  