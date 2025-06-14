#!/usr/bin/env python3
"""Generate v3 TTS audio with emotive tags using the ElevenLabs API"""

import os
import httpx
from pathlib import Path

# Set the API key
api_key = "sk_da5157040e6b27a7d1eb9f73ab2b2891aaead490991d2bcf"

# Test text with emotive tags
test_text = """Hello there! [cheerful] I'm so excited to demonstrate the new v3 model capabilities. [laughing] Did you hear that? I can actually laugh now! 

[whispering] Let me tell you a secret... this new model is absolutely amazing. [normal] But seriously, [thoughtful] when you think about it, the ability to convey emotions through speech synthesis is quite remarkable.

[excited] Oh! And here's something really cool - [dramatic pause] I can create dramatic pauses for effect! [giggling] Sorry, I just find this technology fascinating.

[serious] On a more serious note, this technology has incredible potential for accessibility and creative applications. [gentle] It can help people communicate in ways that feel more natural and human.

[playful] Want to hear me try different emotions? [singing] La la la! [normal] Okay, maybe I shouldn't sing too much. [laughing] But you get the idea!

[contemplative] The future of AI voice synthesis is truly exciting, don't you think? [warm] Thank you for letting me demonstrate these capabilities for you."""

# Use Rachel's voice ID (v3-optimized)
voice_id = "21m00Tcm4TlvDq8ikWAM"

# Sanitize text for JSON
sanitized_text = test_text.replace('...', '.').replace('\n', ' ')

# Make the API request
try:
    response = httpx.post(
        "https://api.elevenlabs.io/v1/text-to-dialogue/stream",
        json={
            "inputs": [{
                "text": sanitized_text,
                "voice_id": voice_id
            }],
            "model_id": "eleven_v3",
            "settings": {
                "quality": None,
                "similarity_boost": 0.75,
                "stability": 0.5
            }
        },
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        },
        timeout=120.0
    )
    
    if response.status_code == 200:
        # Save the audio file
        output_path = Path.home() / "Desktop" / "elevenlabs_v3_emotive_demo.mp3"
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"Success! Audio file saved to: {output_path}")
        print(f"File size: {len(response.content) / 1024:.2f} KB")
    else:
        print(f"API Error: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()