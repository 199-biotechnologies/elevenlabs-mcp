#!/usr/bin/env python3
"""Test script to generate v3 TTS with emotive tags"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the module directory to Python path
module_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(module_dir))

# Import the text_to_speech function
from elevenlabs_mcp.server import text_to_speech

# Load environment variables
load_dotenv()

# Test text with multiple emotive tags
test_text = """Hello there! [cheerful] I'm so excited to demonstrate the new v3 model capabilities. [laughing] Did you hear that? I can actually laugh now! 

[whispering] Let me tell you a secret... this new model is absolutely amazing. [normal] But seriously, [thoughtful] when you think about it, the ability to convey emotions through speech synthesis is quite remarkable.

[excited] Oh! And here's something really cool - [dramatic pause] I can create dramatic pauses for effect! [giggling] Sorry, I just find this technology fascinating.

[serious] On a more serious note, this technology has incredible potential for accessibility and creative applications. [gentle] It can help people communicate in ways that feel more natural and human.

[playful] Want to hear me try different emotions? [singing] La la la! [normal] Okay, maybe I shouldn't sing too much. [laughing] But you get the idea!

[contemplative] The future of AI voice synthesis is truly exciting, don't you think? [warm] Thank you for letting me demonstrate these capabilities for you."""

# Call the text_to_speech function
try:
    result = text_to_speech(
        text=test_text,
        model="v3",
        voice_name="Rachel",  # Using Rachel as it's listed in v3_voices_config.json
        output_directory="/Users/biobook/Desktop",
        stability=0.5,
        similarity_boost=0.75,
        style=0,
        use_speaker_boost=True,
        speed=1.0,
        language="en"
    )
    print(f"Success! {result.text}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()