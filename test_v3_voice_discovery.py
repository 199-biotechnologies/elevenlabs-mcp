#!/usr/bin/env python3
"""Test script to discover v3-compatible voices dynamically"""

import os
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

api_key = os.getenv("ELEVENLABS_API_KEY")
if not api_key:
    raise ValueError("ELEVENLABS_API_KEY environment variable is required")

def get_voice_details(voice_id):
    """Get detailed voice metadata"""
    url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
    headers = {"xi-api-key": api_key}
    
    response = httpx.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def list_all_voices():
    """List all available voices"""
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}
    
    response = httpx.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def check_v3_compatibility():
    """Check voices for v3 compatibility indicators"""
    print("Fetching all voices...")
    voices_data = list_all_voices()
    
    if not voices_data:
        print("Failed to fetch voices")
        return
    
    voices = voices_data.get("voices", [])
    print(f"Found {len(voices)} voices\n")
    
    # Known v3 voice IDs from test files
    known_v3_ids = ["21m00Tcm4TlvDq8ikWAM", "5l5f8iK3YPeGga21rQIX"]
    
    # Analyze known v3 voices first
    print("=== Analyzing Known v3 Voices ===")
    for voice_id in known_v3_ids:
        voice = next((v for v in voices if v["voice_id"] == voice_id), None)
        if voice:
            print(f"\nVoice: {voice.get('name')} ({voice_id})")
            print(f"Category: {voice.get('category')}")
            print(f"Labels: {voice.get('labels', {})}")
            
            # Get detailed metadata
            details = get_voice_details(voice_id)
            if details:
                # Check for model compatibility fields
                if "high_quality_base_model_ids" in details:
                    print(f"High Quality Models: {details['high_quality_base_model_ids']}")
                if "supported_models" in details:
                    print(f"Supported Models: {details['supported_models']}")
                
                # Check fine-tuning status
                fine_tuning = details.get("fine_tuning", {})
                print(f"Fine-tuning state: {fine_tuning.get('state')}")
                
                # Check for any v3-specific fields
                for key, value in details.items():
                    if "v3" in str(key).lower() or "v3" in str(value).lower():
                        print(f"V3 indicator found - {key}: {value}")
    
    # Look for patterns in all voices
    print("\n\n=== Searching for V3 Patterns in All Voices ===")
    potential_v3_voices = []
    
    for voice in voices[:10]:  # Check first 10 voices for patterns
        voice_id = voice["voice_id"]
        details = get_voice_details(voice_id)
        
        if details:
            # Check various potential indicators
            indicators = []
            
            # Check model IDs
            model_ids = details.get("high_quality_base_model_ids", [])
            if "eleven_v3" in model_ids:
                indicators.append("eleven_v3 in model IDs")
            
            # Check category
            if voice.get("category") in ["generated", "premade", "default"]:
                indicators.append(f"category: {voice.get('category')}")
            
            # Check creation date (newer voices might be v3 optimized)
            if "created_at" in details:
                indicators.append(f"created: {details.get('created_at')}")
            
            # Check labels for hints
            labels = voice.get("labels", {})
            if any("v3" in str(v).lower() for v in labels.values()):
                indicators.append("v3 in labels")
            
            if indicators:
                print(f"\n{voice.get('name')} ({voice_id}):")
                for ind in indicators:
                    print(f"  - {ind}")
                potential_v3_voices.append(voice_id)
    
    # Save findings
    findings = {
        "known_v3_voices": known_v3_ids,
        "potential_v3_voices": potential_v3_voices,
        "total_voices_checked": len(voices)
    }
    
    with open("v3_voice_discovery_results.json", "w") as f:
        json.dump(findings, f, indent=2)
    
    print(f"\n\nResults saved to v3_voice_discovery_results.json")

if __name__ == "__main__":
    check_v3_compatibility()