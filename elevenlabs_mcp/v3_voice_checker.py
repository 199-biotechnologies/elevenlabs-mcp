"""
V3 Voice Compatibility Checker

Since there's no direct API field for v3 compatibility,
this module provides methods to identify potentially v3-compatible voices.
"""

import json
import os
from typing import Dict, List, Optional

class V3VoiceChecker:
    def __init__(self):
        # Load known v3 voices from config
        config_path = os.path.join(os.path.dirname(__file__), 'v3_voices_config.json')
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.known_v3_ids = set(self.config['v3_optimized_voices'].keys())
        self.v3_categories = set(self.config['v3_voice_categories'])
    
    def is_v3_optimized(self, voice_id: str) -> bool:
        """Check if a voice ID is known to be v3-optimized"""
        return voice_id in self.known_v3_ids
    
    def get_v3_voice_info(self, voice_id: str) -> Optional[Dict]:
        """Get v3-specific information about a voice"""
        return self.config['v3_optimized_voices'].get(voice_id)
    
    def is_potentially_v3_compatible(self, voice_metadata: Dict) -> bool:
        """
        Check if a voice might be v3-compatible based on heuristics.
        
        Current heuristics:
        1. Voice category is in known v3 categories
        2. Voice is not a Professional Voice Clone (PVC)
        3. Voice was created recently (if date available)
        """
        # Check if it's a known v3 voice
        if voice_metadata.get('voice_id') in self.known_v3_ids:
            return True
        
        # Check category
        category = voice_metadata.get('category', '').lower()
        if category in self.v3_categories:
            # Exclude PVCs as they're not optimized for v3 yet
            if not self._is_pvc(voice_metadata):
                return True
        
        return False
    
    def _is_pvc(self, voice_metadata: Dict) -> bool:
        """Check if a voice is a Professional Voice Clone"""
        # PVCs typically have fine_tuning state as 'fine_tuned'
        fine_tuning = voice_metadata.get('fine_tuning', {})
        if fine_tuning.get('state') == 'fine_tuned':
            return True
        
        # Check labels for PVC indicators
        labels = voice_metadata.get('labels', {})
        description = voice_metadata.get('description', '').lower()
        
        pvc_indicators = ['professional', 'clone', 'pvc', 'custom']
        for indicator in pvc_indicators:
            if indicator in description:
                return True
            if any(indicator in str(v).lower() for v in labels.values()):
                return True
        
        return False
    
    def get_all_v3_voices(self, voices_list: List[Dict]) -> List[Dict]:
        """Filter a list of voices to return only v3-compatible ones"""
        v3_voices = []
        
        for voice in voices_list:
            if self.is_potentially_v3_compatible(voice):
                # Add v3 info if available
                v3_info = self.get_v3_voice_info(voice['voice_id'])
                if v3_info:
                    voice['v3_info'] = v3_info
                v3_voices.append(voice)
        
        return v3_voices
    
    def add_v3_voice(self, voice_id: str, name: str, category: str = "default", description: str = ""):
        """Add a new v3-optimized voice to the config"""
        self.config['v3_optimized_voices'][voice_id] = {
            "name": name,
            "category": category,
            "description": description
        }
        self.known_v3_ids.add(voice_id)
        
        # Save updated config
        config_path = os.path.join(os.path.dirname(__file__), 'v3_voices_config.json')
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)