#!/usr/bin/env python3
"""
Example of how to use the V3 voice checker in the server implementation
"""

from elevenlabs_mcp.v3_voice_checker import V3VoiceChecker

# Example usage
def demo_v3_voice_checking():
    checker = V3VoiceChecker()
    
    # Example voice metadata (would come from API)
    voice_metadata = {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "name": "Rachel",
        "category": "default",
        "labels": {"accent": "american", "gender": "female"},
        "fine_tuning": {"state": "not_started"}
    }
    
    # Check if voice is v3 optimized
    if checker.is_v3_optimized(voice_metadata['voice_id']):
        print(f"✓ {voice_metadata['name']} is v3-optimized!")
        info = checker.get_v3_voice_info(voice_metadata['voice_id'])
        print(f"  Info: {info}")
    
    # Check potential compatibility
    if checker.is_potentially_v3_compatible(voice_metadata):
        print(f"✓ {voice_metadata['name']} is potentially v3-compatible")
    
    # Example: Filter voices for v3
    all_voices = [
        {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "category": "default"},
        {"voice_id": "xyz123", "name": "Custom PVC", "category": "cloned", "fine_tuning": {"state": "fine_tuned"}},
        {"voice_id": "5l5f8iK3YPeGga21rQIX", "name": "Unknown", "category": "default"}
    ]
    
    v3_voices = checker.get_all_v3_voices(all_voices)
    print(f"\nFound {len(v3_voices)} v3-compatible voices:")
    for voice in v3_voices:
        print(f"  - {voice['name']} ({voice['voice_id']})")

if __name__ == "__main__":
    demo_v3_voice_checking()