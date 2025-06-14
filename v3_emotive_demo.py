#!/usr/bin/env python3
"""
Demonstration of ElevenLabs v3 Text-to-Speech with Emotive Tags

This script shows how to use the ElevenLabs MCP server's text_to_speech tool
with the v3 model to generate expressive speech using emotive tags.

NOTE: This requires a valid ELEVENLABS_API_KEY to be set in the environment.
"""

# Example usage of the text_to_speech MCP tool with v3 model and emotive tags

# The text with various emotive tags for v3 model
emotive_text = """
Hello there! [cheerful] I'm so excited to demonstrate the new v3 model capabilities. 
[laughing] Did you hear that? I can actually laugh now! 

[whispering] Let me tell you a secret... this new model is absolutely amazing. 
[normal] But seriously, [thoughtful] when you think about it, the ability to convey 
emotions through speech synthesis is quite remarkable.

[excited] Oh! And here's something really cool - [dramatic pause] I can create 
dramatic pauses for effect! [giggling] Sorry, I just find this technology fascinating.

[serious] On a more serious note, this technology has incredible potential for 
accessibility and creative applications. [gentle] It can help people communicate 
in ways that feel more natural and human.

[playful] Want to hear me try different emotions? [singing] La la la! 
[normal] Okay, maybe I shouldn't sing too much. [laughing] But you get the idea!

[contemplative] The future of AI voice synthesis is truly exciting, don't you think? 
[warm] Thank you for letting me demonstrate these capabilities for you.
"""

# MCP tool parameters for v3 TTS
mcp_tool_params = {
    "tool": "text_to_speech",
    "parameters": {
        "text": emotive_text,
        "model": "v3",  # Required for emotive tags support
        "voice_name": "Rachel",  # v3-optimized voice (or use voice_id)
        "output_directory": "/Users/biobook/Desktop",
        "stability": 0.5,  # Lower values = broader emotional range
        "similarity_boost": 0.75,
        "style": 0,
        "use_speaker_boost": True,
        "speed": 1.0,
        "language": "en",
        "output_format": "mp3_44100_128"
    }
}

# Available v3 emotive tags (based on ElevenLabs documentation):
v3_emotive_tags = [
    "[normal]", "[cheerful]", "[laughing]", "[whispering]", "[thoughtful]",
    "[excited]", "[dramatic pause]", "[giggling]", "[serious]", "[gentle]",
    "[playful]", "[singing]", "[contemplative]", "[warm]", "[crying]",
    "[shouting]", "[angry]", "[sad]", "[happy]", "[fearful]", "[disgusted]",
    "[surprised]", "[sarcastic]", "[confident]", "[nervous]", "[tired]",
    "[relieved]", "[disappointed]", "[curious]", "[amused]", "[bored]"
]

# Example of different voice configurations for v3
v3_voice_examples = {
    "Rachel": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "description": "Optimized for v3 emotional expression"
    },
    "Default": {
        "voice_id": "cgSgspJ2msm6clMCkdW9", 
        "description": "Default v3 voice"
    }
}

print("ElevenLabs v3 Text-to-Speech with Emotive Tags")
print("=" * 50)
print("\nMCP Tool Call:")
print(f"Tool: {mcp_tool_params['tool']}")
print("\nParameters:")
for key, value in mcp_tool_params['parameters'].items():
    if key == 'text':
        print(f"  {key}: <text with emotive tags>")
    else:
        print(f"  {key}: {value}")

print("\n\nAvailable v3 Emotive Tags:")
print("-" * 30)
for i in range(0, len(v3_emotive_tags), 5):
    print("  " + ", ".join(v3_emotive_tags[i:i+5]))

print("\n\nText Content with Emotive Tags:")
print("-" * 30)
print(emotive_text)

print("\n\nNote: To actually generate the audio, you need:")
print("1. A valid ELEVENLABS_API_KEY environment variable")
print("2. Access to the v3 model (may require special permissions)")
print("3. The ElevenLabs MCP server running")