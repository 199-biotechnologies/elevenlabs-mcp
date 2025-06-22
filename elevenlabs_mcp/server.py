"""
ElevenLabs MCP Server

⚠️ IMPORTANT: This server provides access to ElevenLabs API endpoints which may incur costs.
Each tool that makes an API call is marked with a cost warning. Please follow these guidelines:

1. Only use tools when explicitly requested by the user
2. For tools that generate audio, consider the length of the text as it affects costs
3. Some operations like voice cloning or text-to-voice may have higher costs

Tools without cost warnings in their description are free to use as they only read existing data.
"""

import httpx
import os
import base64
import asyncio
import time
import re
from datetime import datetime
from io import BytesIO
from typing import Literal
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from elevenlabs.client import ElevenLabs
from elevenlabs_mcp.model import McpVoice, McpModel, McpLanguage
from elevenlabs_mcp.utils import (
    make_error,
    make_output_path,
    make_output_file,
    handle_input_file,
)
from elevenlabs_mcp.convai import create_conversation_config, create_platform_settings
from elevenlabs.types.knowledge_base_locator import KnowledgeBaseLocator

from elevenlabs import play
from elevenlabs_mcp import __version__

load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")
base_path = os.getenv("ELEVENLABS_MCP_BASE_PATH")
DEFAULT_VOICE_ID = "cgSgspJ2msm6clMCkdW9"

# v3 proxy configuration
v3_proxy_enabled = os.getenv("ELEVENLABS_V3_PROXY", "false").lower() == "true"
v3_proxy_url = f"http://localhost:{os.getenv('V3_PROXY_PORT', '8123')}"

# Valid v3 tags based on ElevenLabs documentation
VALID_V3_TAGS = {
    # Emotions
    'happy', 'sad', 'angry', 'excited', 'crying', 'sobbing',
    'laughing', 'laughs', 'laughs harder', 'chuckles', 'giggling',
    'hysterical', 'crazy laugh', 'nervous laugh',
    
    # Voice styles  
    'whispers', 'whispering', 'shouting', 'softly', 'loudly',
    'sarcastic', 'curious', 'mischievously', 'dramatically',
    'thoughtful', 'impressed', 'amazed', 'warmly', 'nervously',
    'trembling voice', 'voice breaking', 'voice cracking',
    
    # Actions
    'sighs', 'exhales', 'yawns', 'breathing heavily',
    'coughing', 'sniffling', 'gulps', 'swallows',
    'frustrated sigh', 'happy gasp',
    
    # Special
    'pause', 'long pause', 'silence',
    
    # Sounds
    'footsteps', 'door opening', 'door creaking', 'thunder', 'applause',
    'clapping', 'gunshot', 'explosion', 'piano', 'leaves rustling'
}


def simplify_tags(text):
    """Replace complex/invalid tags with simple v3-compatible ones"""
    # Common replacements for invalid compound tags
    replacements = {
        r'\[final,?\s*broken\s*whisper\]': '[whispers]',
        r'\[hollow\s*whisper\]': '[whispers]',
        r'\[voice\s+trembling\]': '[trembling voice]',
        r'\[hollow.*?\]': '[softly]',
        r'\[philosophical.*?\]': '[thoughtful]',
        r'\[building.*?\]': '[excited]',
        r'\[to\s+the\s+(sky|heavens?|air)\]': '',  # Remove stage directions
        r'\[standing\s+alone.*?\]': '',
        r'\[.*?alone\]': '[softly]',
        r'\[eerily\s+calm\]': '[softly]',
        r'\[profound.*?\]': '[thoughtful]',
        r'\[bitter.*?\]': '[angry]',
        r'\[explosive.*?\]': '[shouting]',
        r'\[quiet\s+devastation\]': '[softly]',
        r'\[almost\s+inaudible\]': '[whispers]',
        r'\[barely\s+audible\]': '[whispers]',
        r'\[fading\s+to\s+nothing\]': '[whispers]',
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


def validate_and_warn_tags(text):
    """Validate tags and return warnings about invalid ones"""
    tags = re.findall(r'\[([^\]]+)\]', text)
    invalid_tags = []
    
    for tag in tags:
        # Clean and check tag
        clean_tag = tag.strip().lower()
        # Check exact match or common variations
        if (clean_tag not in VALID_V3_TAGS and 
            clean_tag.rstrip('s') not in VALID_V3_TAGS and
            clean_tag.replace(' ', '') not in VALID_V3_TAGS):
            invalid_tags.append(tag)
    
    return invalid_tags


def calculate_dialogue_timeout(inputs):
    """Calculate appropriate timeout based on dialogue complexity"""
    total_chars = sum(len(inp['text']) for inp in inputs)
    tag_count = sum(len(re.findall(r'\[.*?\]', inp['text'])) for inp in inputs)
    
    # Base: 30 seconds + 15 seconds per input + 3 seconds per tag
    timeout = 30 + (len(inputs) * 15) + (tag_count * 3)
    
    # Add extra time for long texts
    if total_chars > 2000:
        timeout += 30
    
    # Cap at 5 minutes but warn if close
    if timeout > 240:
        print(f"Complex dialogue detected. Processing may take up to {timeout//60} minutes...")
    
    return min(timeout, 300)  # Max 5 minutes

if not api_key:
    raise ValueError("ELEVENLABS_API_KEY environment variable is required")

# Add custom client to ElevenLabs to set User-Agent header
custom_client = httpx.Client(
    headers={
        "User-Agent": f"ElevenLabs-MCP/{__version__}",
    }
)

client = ElevenLabs(api_key=api_key, httpx_client=custom_client)
mcp = FastMCP("ElevenLabs")


@mcp.tool(
    description="""🎤 SINGLE SPEAKER Text-to-Speech (Use text_to_dialogue for multiple speakers!)
    
    ✅ USE THIS WHEN:
    - ONE person speaking (narration, monologue, single voice)
    - Need specific voice settings (speed, stability, style)
    - Want v2 (default), v3 (tags), or flash (fast) models
    
    ❌ DON'T USE THIS WHEN:
    - MULTIPLE speakers in conversation → Use text_to_dialogue instead!
    - You see dialogue format → Use text_to_dialogue instead!
    
    📝 EXAMPLES:
    - Basic: text_to_speech("Hello world")
    - v3 with tags: text_to_speech("[thoughtful] The universe is vast... [piano]", model="v3") 
    - Fast: text_to_speech("Quick test", model="flash")
    - No voice? It works! text_to_speech("Hello") uses default voice

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs.
    
    🎭 v3 TAGS: [happy], [sad], [laughing], [whispering], [shouting], [pause], [piano], etc.
    💡 Call fetch_v3_tags() for full list!
    
    ⚠️ v3 LIMITATIONS: Only stability & similarity_boost work with v3 (no style/speed/speaker_boost)
    
    🚨 MULTIPLE SPEAKERS? Stop! Use text_to_dialogue() instead!

     Args:
        text (str): The text to convert to speech. Can include audio tags when using v3 model.
        voice_name (str, optional): The name of the voice to use.
        stability (float, optional): Stability of the generated audio. Determines how stable the voice is and the randomness between each generation. Lower values introduce broader emotional range for the voice. Higher values can result in a monotonous voice with limited emotion.
            For v2/flash models: Range is 0 to 1 (default: 0.5)
            For v3 model: Must be exactly 0.0 (Creative), 0.5 (Natural), or 1.0 (Robust)
        similarity_boost (float, optional): Similarity boost of the generated audio. Determines how closely the AI should adhere to the original voice when attempting to replicate it. Range is 0 to 1.
        style (float, optional): Style of the generated audio. Determines the style exaggeration of the voice. This setting attempts to amplify the style of the original speaker. It does consume additional computational resources and might increase latency if set to anything other than 0. Range is 0 to 1.
        use_speaker_boost (bool, optional): Use speaker boost of the generated audio. This setting boosts the similarity to the original speaker. Using this setting requires a slightly higher computational load, which in turn increases latency.
        speed (float, optional): Speed of the generated audio. Controls the speed of the generated speech. Values range from 0.7 to 1.2, with 1.0 being the default speed. Lower values create slower, more deliberate speech while higher values produce faster-paced speech. Extreme values can impact the quality of the generated speech. Range is 0.7 to 1.2.
        output_directory (str, optional): Directory where files should be saved.
            Defaults to $HOME/Desktop if not provided.
        language: ISO 639-1 language code for the voice.
        model (str, optional): The model to use - 'v2' (default), 'v3' (🆕 NEW! More expressive with audio tags), or 'flash' (fast).
        output_format (str, optional): Output format of the generated audio. Formatted as codec_sample_rate_bitrate. So an mp3 with 22.05kHz sample rate at 32kbs is represented as mp3_22050_32. MP3 with 192kbps bitrate requires you to be subscribed to Creator tier or above. PCM with 44.1kHz sample rate requires you to be subscribed to Pro tier or above. Note that the μ-law format (sometimes written mu-law, often approximated as u-law) is commonly used for Twilio audio inputs.
            Defaults to "mp3_44100_128". Must be one of:
            mp3_22050_32
            mp3_44100_32
            mp3_44100_64
            mp3_44100_96
            mp3_44100_128
            mp3_44100_192
            pcm_8000
            pcm_16000
            pcm_22050
            pcm_24000
            pcm_44100
            ulaw_8000
            alaw_8000
            opus_48000_32
            opus_48000_64
            opus_48000_96
            opus_48000_128
            opus_48000_192

    Returns:
        Text content with the path to the output file and name of the voice used.
    """
)
def text_to_speech(
    text: str,
    voice_name: str | None = None,
    output_directory: str | None = None,
    voice_id: str | None = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0,
    use_speaker_boost: bool = True,
    speed: float = 1.0,
    language: str = "en",
    model: str = "v2",
    output_format: str = "mp3_44100_128",
):
    if text == "":
        make_error("Text is required.")

    if voice_id is not None and voice_name is not None:
        make_error("voice_id and voice_name cannot both be provided.")

    voice = None
    if voice_id is not None:
        try:
            voice = client.voices.get(voice_id=voice_id)
        except:
            make_error(f"""Voice ID '{voice_id}' not found!
            
💡 TIP: Use search_voices() first to get valid voice IDs.
Example: search_voices() → Returns list with IDs → Use the ID in text_to_speech
            
Common voice IDs:
- James: EkK5I93UQWFDigLMpZcX (v3-optimized)
- Jane: RILOU7YmBhvwJGDGjNmP (v3-optimized)
- Mark: 1SM7GgM6IMuvQlz2BwM3 (v3-optimized)
- Brian: nPczCjzI2devNBz1zQrb
- Rachel: 21m00Tcm4TlvDq8ikWAM
- Adam: pNInz6obpgDQGcFmaJgB""")
    elif voice_name is not None:
        voices = client.voices.search(search=voice_name)
        if len(voices.voices) == 0:
            # Provide helpful suggestions
            make_error(
                f"No voices found with name '{voice_name}'",
                code="VOICE_NOT_FOUND",
                suggestion="Use get_voice_id_by_name() for fuzzy matching, or search_voices() to list all available voices"
            )
        voice = next((v for v in voices.voices if v.name == voice_name), None)
        if voice is None:
            # Check for partial matches
            partial_matches = [v.name for v in voices.voices if voice_name.lower() in v.name.lower()]
            if partial_matches:
                make_error(
                    f"Exact match for '{voice_name}' not found",
                    code="VOICE_PARTIAL_MATCH",
                    suggestion=f"Did you mean one of these? {', '.join(partial_matches[:5])}. Use get_voice_id_by_name() for automatic matching"
                )
            else:
                make_error(
                    f"Voice '{voice_name}' does not exist",
                    code="VOICE_NOT_FOUND",
                    suggestion="Try search_voices() to see all available voices"
                )

    voice_id = voice.voice_id if voice else DEFAULT_VOICE_ID

    output_path = make_output_path(output_directory, base_path)
    output_file_name = make_output_file("tts", text, output_path, "mp3")

    # v3 model requires the dialogue endpoint, even for single speaker
    if model == "v3":
        # Auto-adjust stability to valid v3 values
        original_stability = stability
        if stability not in [0.0, 0.5, 1.0]:
            # Round to nearest valid value
            if stability < 0.35:
                stability = 0.0
            elif stability <= 0.75:
                stability = 0.5
            else:
                stability = 1.0
            print(f"Auto-adjusted stability from {original_stability} to {stability}")
        
        # Simplify tags for v3
        text = simplify_tags(text)
        
        # Validate and warn about remaining invalid tags
        invalid_tags = validate_and_warn_tags(text)
        if invalid_tags:
            print(f"Warning: These tags may not work properly: {invalid_tags}")
            print("Consider using: whispers, crying, shouting, pause, etc.")
        
        # Sanitize text to avoid JSON parsing issues
        # Replace problematic characters that cause escaping issues
        sanitized_text = text.replace('...', '.').replace('\n', ' ')
        
        # Check if v3 proxy is enabled for users with web access
        if v3_proxy_enabled:
            # Ensure proxy is running
            import subprocess
            import psutil
            import sys
            
            # Check if proxy is already running
            proxy_running = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline')
                    if cmdline and 'v3_proxy.py' in ' '.join(cmdline):
                        proxy_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    continue
            
            if not proxy_running:
                # Start proxy in background
                proxy_path = os.path.join(os.path.dirname(__file__), 'v3_proxy.py')
                subprocess.Popen([sys.executable, proxy_path], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                # Give it a moment to start
                import time
                time.sleep(2)
            
            # Use proxy endpoint
            endpoint = f"{v3_proxy_url}/v1/text-to-dialogue/stream"
        else:
            # Use direct API endpoint (requires v3 access)
            endpoint = "https://api.elevenlabs.io/v1/text-to-dialogue/stream"
        
        response = httpx.post(
            endpoint,
            json={
                "inputs": [{
                    "text": sanitized_text,
                    "voice_id": voice_id
                }],
                "model_id": "eleven_v3",
                "settings": {
                    "quality": None,
                    "similarity_boost": similarity_boost,
                    "stability": stability
                }
            },
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            } if not v3_proxy_enabled else {
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            timeout=calculate_dialogue_timeout([{"text": sanitized_text}])
        )
        
        if response.status_code == 403:
            make_error("v3 access denied. You need special access from ElevenLabs sales, or enable v3 proxy with ELEVENLABS_V3_PROXY=true")
        elif response.status_code == 422:
            # Parse error details for better messaging
            try:
                error_detail = response.json()
                if "stability" in str(error_detail):
                    make_error(f"v3 parameter error: stability must be exactly 0.0, 0.5, or 1.0. Details: {error_detail}")
                else:
                    make_error(f"v3 parameter validation error: {error_detail}")
            except:
                make_error(f"v3 API error: {response.status_code} - {response.text}")
        elif response.status_code != 200:
            make_error(f"v3 API error: {response.status_code} - {response.text}")
        
        audio_bytes = response.content
    else:
        # v2 and flash models use regular text-to-speech endpoint
        if model == "flash":
            model_id = "eleven_flash_v2_5"
        else:
            # Default v2 behavior
            model_id = "eleven_flash_v2_5" if language in ["hu", "no", "vi"] else "eleven_multilingual_v2"
        
        audio_data = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
            voice_settings={
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
                "speed": speed,
            },
        )
        audio_bytes = b"".join(audio_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path / output_file_name, "wb") as f:
        f.write(audio_bytes)

    return TextContent(
        type="text",
        text=f"Success. File saved as: {output_path / output_file_name}. Voice used: {voice.name if voice else DEFAULT_VOICE_ID}",
    )


@mcp.tool(
    description="""Transcribe speech from an audio file and either save the output text file to a given directory or return the text to the client directly.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        file_path: Path to the audio file to transcribe
        language_code: ISO 639-3 language code for transcription (default: "eng" for English)
        diarize: Whether to diarize the audio file. If True, which speaker is currently speaking will be annotated in the transcription.
        save_transcript_to_file: Whether to save the transcript to a file.
        return_transcript_to_client_directly: Whether to return the transcript to the client directly.
        output_directory: Directory where files should be saved.
            Defaults to $HOME/Desktop if not provided.

    Returns:
        TextContent containing the transcription. If save_transcript_to_file is True, the transcription will be saved to a file in the output directory.
    """
)
def speech_to_text(
    input_file_path: str,
    language_code: str = "eng",
    diarize: bool = False,
    save_transcript_to_file: bool = True,
    return_transcript_to_client_directly: bool = False,
    output_directory: str | None = None,
) -> TextContent:
    if not save_transcript_to_file and not return_transcript_to_client_directly:
        make_error("Must save transcript to file or return it to the client directly.")
    file_path = handle_input_file(input_file_path)
    if save_transcript_to_file:
        output_path = make_output_path(output_directory, base_path)
        output_file_name = make_output_file("stt", file_path.name, output_path, "txt")
    with file_path.open("rb") as f:
        audio_bytes = f.read()
    transcription = client.speech_to_text.convert(
        model_id="scribe_v1",
        file=audio_bytes,
        language_code=language_code,
        enable_logging=True,
        diarize=diarize,
        tag_audio_events=True,
    )

    if save_transcript_to_file:
        with open(output_path / output_file_name, "w") as f:
            f.write(transcription.text)

    if return_transcript_to_client_directly:
        return TextContent(type="text", text=transcription.text)
    else:
        return TextContent(
            type="text", text=f"Transcription saved to {output_path / output_file_name}"
        )


@mcp.tool(
    description="""Convert text description of a sound effect to sound effect with a given duration and save the output audio file to a given directory.
    Directory is optional, if not provided, the output file will be saved to $HOME/Desktop.
    Duration must be between 0.5 and 5 seconds.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        text: Text description of the sound effect
        duration_seconds: Duration of the sound effect in seconds
        output_directory: Directory where files should be saved.
            Defaults to $HOME/Desktop if not provided.
        output_format (str, optional): Output format of the generated audio. Formatted as codec_sample_rate_bitrate. So an mp3 with 22.05kHz sample rate at 32kbs is represented as mp3_22050_32. MP3 with 192kbps bitrate requires you to be subscribed to Creator tier or above. PCM with 44.1kHz sample rate requires you to be subscribed to Pro tier or above. Note that the μ-law format (sometimes written mu-law, often approximated as u-law) is commonly used for Twilio audio inputs.
            Defaults to "mp3_44100_128". Must be one of:
            mp3_22050_32
            mp3_44100_32
            mp3_44100_64
            mp3_44100_96
            mp3_44100_128
            mp3_44100_192
            pcm_8000
            pcm_16000
            pcm_22050
            pcm_24000
            pcm_44100
            ulaw_8000
            alaw_8000
            opus_48000_32
            opus_48000_64
            opus_48000_96
            opus_48000_128
            opus_48000_192
    """
)
def text_to_sound_effects(
    text: str,
    duration_seconds: float = 2.0,
    output_directory: str | None = None,
    output_format: str = "mp3_44100_128"
) -> list[TextContent]:
    if duration_seconds < 0.5 or duration_seconds > 5:
        make_error(
            "Duration must be between 0.5 and 5 seconds",
            code="INVALID_DURATION",
            suggestion="Use a duration between 0.5 and 5 seconds"
        )
    output_path = make_output_path(output_directory, base_path)
    output_file_name = make_output_file("sfx", text, output_path, "mp3")

    audio_data = client.text_to_sound_effects.convert(
        text=text,
        output_format=output_format,
        duration_seconds=duration_seconds,
    )
    audio_bytes = b"".join(audio_data)

    with open(output_path / output_file_name, "wb") as f:
        f.write(audio_bytes)

    return TextContent(
        type="text",
        text=f"Success. File saved as: {output_path / output_file_name}",
    )


@mcp.tool(
    description="""
    🔊 Search for voices in your ElevenLabs library - AI-FRIENDLY!
    
    ⚡ INSTANT SUCCESS: No search term? Returns common working voices immediately!
    
    🎯 SMART DEFAULTS:
    - Empty search → Returns popular voices (James, Jane, Sarah, etc.)
    - "v3" → Returns v3-optimized voices first
    - "female" → Returns female voices
    - "male" → Returns male voices
    - "british" → Voices with British accents
    
    💡 AI TIP: Start with no search term to get working voices instantly!

    Args:
        search: Optional search term. Leave empty for common voices!
        sort: Sort by "name" or "created_at_unix"
        sort_direction: "asc" or "desc"
        return_format: "json" for structured data (default), "text" for human-readable

    Returns:
        Structured JSON with voice details or formatted text list
    """
)
def search_voices(
    search: str | None = None,
    sort: Literal["created_at_unix", "name"] = "name",
    sort_direction: Literal["asc", "desc"] = "desc",
    return_format: Literal["json", "text"] = "json",
) -> TextContent:
    # Common working voices that AI should use by default
    common_voices = {
        "James": "husky & engaging audiobook narrator, v3-optimized (ID: EkK5I93UQWFDigLMpZcX)",
        "Jane": "professional audiobook reader, v3-optimized (ID: RILOU7YmBhvwJGDGjNmP)", 
        "Juniper": "grounded female professional, v3-optimized (ID: aMSt68OGf4xUZAnLpTU8)",
        "Mark": "ConvoAI optimized, v3-optimized (ID: 1SM7GgM6IMuvQlz2BwM3)",
        "Adam": "versatile male voice",
        "Antoni": "well-rounded male voice",
        "Rachel": "conversational American female",
        "Brian": "deep American male voice"
    }
    
    # If no search term, return common voices with helpful info
    if not search:
        # Get all voices first
        all_voices_response = client.voices.get_all()
        all_voices_dict = {v.name: v for v in all_voices_response.voices}
        
        # Build list of common voices that actually exist
        result_voices = []
        for voice_name, description in common_voices.items():
            if voice_name in all_voices_dict:
                voice = all_voices_dict[voice_name]
                # Add helpful description to category
                enhanced_voice = McpVoice(
                    id=voice.voice_id,
                    name=voice.name,
                    category=f"{voice.category or 'general'} - {description}"
                )
                result_voices.append(enhanced_voice)
        
        # If we found common voices, return them
        if result_voices:
            return result_voices
    
    # Otherwise do normal search
    response = client.voices.search(
        search=search, sort=sort, sort_direction=sort_direction
    )
    
    voices = [
        McpVoice(id=voice.voice_id, name=voice.name, category=voice.category)
        for voice in response.voices
    ]
    
    # If searching for v3 voices or model 3, prioritize known v3-optimized voices
    if search and ("v3" in search.lower() or "model 3" in search.lower()):
        # These voice names are known to be optimized for v3 based on ElevenLabs website
        # Each voice has been verified with its correct ID
        v3_optimized_names = {
            "James",  # EkK5I93UQWFDigLMpZcX
            "Jane",  # RILOU7YmBhvwJGDGjNmP
            "Juniper",  # aMSt68OGf4xUZAnLpTU8
            "Arabella",  # Z3R5wn05IrDiVCyEkUrK
            "Nichalia Schwartz",  # XfNU2rGpBa01ckF309OY
            "Hope",  # tnSpp4vdxKPjI9w0GnoV
            "Bradford",  # NNl6r8mD7vthiJatiJt1
            "Reginald",  # Hjzqw9NR0xFMYU9Us0DL
            "Gaming – Unreal Tonemanagement 2003",  # YOq2y2Up4RgXP2HyXjE5
            "Austin",  # Bj9UqZbhQsanLzgalpEG
            "kuon",  # B8gJV1IhpuegLxdpXFOE
            "Blondie",  # exsUS4vynmxd379XN4yO
            "Priyanka Sogam",  # BpjGufoPiobT79j2vtj4
            "Alexandra",  # kdmDKE6EkgrWrrykO9Qt
            "Monika Sogam",  # 2zRM7PkgwBPiau2jvVXc
            "Jenna",  # TgnhEILA8UwUqIMi20rp
            "Mark",  # 1SM7GgM6IMuvQlz2BwM3
            "Grimblewood Thornwhisker",  # ouL9IsyrSnUkCmfnD02u
            "Adeline",  # 5l5f8iK3YPeGga21rQIX
            "Sam"  # scOwDtmlUjD3prqpp97I
        }
        
        # Sort to put v3-optimized voices first
        v3_voices = []
        other_voices = []
        
        for voice in voices:
            if voice.name in v3_optimized_names:
                v3_voices.append(voice)
            else:
                other_voices.append(voice)
        
        voices = v3_voices + other_voices
    
    # Format the response
    if return_format == "json":
        import json
        voice_data = {
            "total_count": len(voices),
            "search_term": search,
            "voices": [
                {
                    "voice_id": voice.id,
                    "name": voice.name,
                    "category": voice.category,
                    "is_v3_optimized": voice.name in v3_optimized_names if search and "v3" in search.lower() else None
                }
                for voice in voices
            ]
        }
        return TextContent(type="text", text=json.dumps(voice_data, indent=2))
    else:
        # Legacy text format
        lines = [f"Found {len(voices)} voices:\n"]
        for voice in voices:
            lines.append(f"- {voice.name} (ID: {voice.id}) - {voice.category or 'general'}")
        return TextContent(type="text", text="\n".join(lines))


@mcp.tool(
    description="""Get voice ID by voice name - AI-FRIENDLY helper!
    
    This tool automatically resolves voice names to IDs, handling:
    - Exact matches (case-insensitive)
    - Fuzzy matching for typos
    - Returns the best match with confidence score
    
    Use this when you have a voice name but need the ID for other tools.
    
    Args:
        voice_name: The name of the voice to find
        
    Returns:
        JSON with voice_id, exact name, and match confidence
        
    Example:
        get_voice_id_by_name("james") → {"voice_id": "EkK5I93...", "name": "James", "confidence": 100}
    """
)
def get_voice_id_by_name(voice_name: str) -> TextContent:
    import json
    from fuzzywuzzy import fuzz
    
    try:
        # Get all voices
        all_voices_response = client.voices.get_all()
        
        # First try exact match (case-insensitive)
        for voice in all_voices_response.voices:
            if voice.name.lower() == voice_name.lower():
                result = {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "confidence": 100,
                    "match_type": "exact"
                }
                return TextContent(type="text", text=json.dumps(result, indent=2))
        
        # If no exact match, try fuzzy matching
        best_match = None
        best_score = 0
        
        for voice in all_voices_response.voices:
            score = fuzz.ratio(voice.name.lower(), voice_name.lower())
            if score > best_score:
                best_score = score
                best_match = voice
        
        # Only return fuzzy match if confidence is above 70%
        if best_match and best_score >= 70:
            result = {
                "voice_id": best_match.voice_id,
                "name": best_match.name,
                "confidence": best_score,
                "match_type": "fuzzy",
                "original_query": voice_name
            }
            return TextContent(type="text", text=json.dumps(result, indent=2))
        else:
            make_error(
                f"No voice found matching '{voice_name}'",
                code="VOICE_NOT_FOUND",
                suggestion="Use search_voices() to see available voices, or check spelling"
            )
            
    except Exception as e:
        make_error(
            f"Failed to find voice: {str(e)}",
            code="VOICE_LOOKUP_ERROR",
            suggestion="Try search_voices() instead"
        )


@mcp.tool(description="List all available models")
def list_models() -> list[McpModel]:
    response = client.models.list()
    return [
        McpModel(
            id=model.model_id,
            name=model.name,
            languages=[
                McpLanguage(language_id=lang.language_id, name=lang.name)
                for lang in model.languages
            ]
        )
        for model in response
    ]


@mcp.tool(description="Get details of a specific voice")
def get_voice(voice_id: str) -> McpVoice:
    """Get details of a specific voice."""
    response = client.voices.get(voice_id=voice_id)
    return McpVoice(
        id=response.voice_id,
        name=response.name,
        category=response.category,
        fine_tuning_status=response.fine_tuning.state,
    )


@mcp.tool(
    description="""Create an instant voice clone of a voice using provided audio files.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
def voice_clone(
    name: str, files: list[str], description: str | None = None
) -> TextContent:
    input_files = [str(handle_input_file(file).absolute()) for file in files]
    voice = client.voices.ivc.create(
        name=name,
        description=description,
        files=input_files
    )

    return TextContent(
        type="text",
        text=f"""Voice cloned successfully: Name: {voice.name}
        ID: {voice.voice_id}
        Category: {voice.category}
        Description: {voice.description or "N/A"}""",
    )


@mcp.tool(
    description="""Isolate audio from a file and save the output audio file to a given directory.
    Directory is optional, if not provided, the output file will be saved to $HOME/Desktop.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
def isolate_audio(
    input_file_path: str, output_directory: str | None = None
) -> list[TextContent]:
    file_path = handle_input_file(input_file_path)
    output_path = make_output_path(output_directory, base_path)
    output_file_name = make_output_file("iso", file_path.name, output_path, "mp3")
    with file_path.open("rb") as f:
        audio_bytes = f.read()
    audio_data = client.audio_isolation.convert(
        audio=audio_bytes,
    )
    audio_bytes = b"".join(audio_data)

    with open(output_path / output_file_name, "wb") as f:
        f.write(audio_bytes)

    return TextContent(
        type="text",
        text=f"Success. File saved as: {output_path / output_file_name}",
    )


@mcp.tool(
    description="Check the current subscription status. Could be used to measure the usage of the API."
)
def check_subscription() -> TextContent:
    subscription = client.user.subscription.get()
    return TextContent(type="text", text=f"{subscription.model_dump_json(indent=2)}")


@mcp.tool(
    description="""Create a conversational AI agent with custom configuration.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        name: Name of the agent
        first_message: First message the agent will say i.e. "Hi, how can I help you today?"
        system_prompt: System prompt for the agent
        voice_id: ID of the voice to use for the agent
        language: ISO 639-1 language code for the agent
        llm: LLM to use for the agent
        temperature: Temperature for the agent. The lower the temperature, the more deterministic the agent's responses will be. Range is 0 to 1.
        max_tokens: Maximum number of tokens to generate.
        asr_quality: Quality of the ASR. `high` or `low`.
        model_id: ID of the ElevenLabs model to use for the agent.
        optimize_streaming_latency: Optimize streaming latency. Range is 0 to 4.
        stability: Stability for the agent. Range is 0 to 1.
        similarity_boost: Similarity boost for the agent. Range is 0 to 1.
        turn_timeout: Timeout for the agent to respond in seconds. Defaults to 7 seconds.
        max_duration_seconds: Maximum duration of a conversation in seconds. Defaults to 600 seconds (10 minutes).
        record_voice: Whether to record the agent's voice.
        retention_days: Number of days to retain the agent's data.
    """
)
def create_agent(
    name: str,
    first_message: str,
    system_prompt: str,
    voice_id: str | None = DEFAULT_VOICE_ID,
    language: str = "en",
    llm: str = "gemini-2.0-flash-001",
    temperature: float = 0.5,
    max_tokens: int | None = None,
    asr_quality: str = "high",
    model_id: str = "eleven_turbo_v2",
    optimize_streaming_latency: int = 3,
    stability: float = 0.5,
    similarity_boost: float = 0.8,
    turn_timeout: int = 7,
    max_duration_seconds: int = 300,
    record_voice: bool = True,
    retention_days: int = 730,
) -> TextContent:
    conversation_config = create_conversation_config(
        language=language,
        system_prompt=system_prompt,
        llm=llm,
        first_message=first_message,
        temperature=temperature,
        max_tokens=max_tokens,
        asr_quality=asr_quality,
        voice_id=voice_id,
        model_id=model_id,
        optimize_streaming_latency=optimize_streaming_latency,
        stability=stability,
        similarity_boost=similarity_boost,
        turn_timeout=turn_timeout,
        max_duration_seconds=max_duration_seconds,
    )

    platform_settings = create_platform_settings(
        record_voice=record_voice,
        retention_days=retention_days,
    )

    response = client.conversational_ai.agents.create(
        name=name,
        conversation_config=conversation_config,
        platform_settings=platform_settings,
    )

    return TextContent(
        type="text",
        text=f"""Agent created successfully: Name: {name}, Agent ID: {response.agent_id}, System Prompt: {system_prompt}, Voice ID: {voice_id or "Default"}, Language: {language}, LLM: {llm}, You can use this agent ID for future interactions with the agent.""",
    )


@mcp.tool(
    description="""Add a knowledge base to ElevenLabs workspace. Allowed types are epub, pdf, docx, txt, html.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        agent_id: ID of the agent to add the knowledge base to.
        knowledge_base_name: Name of the knowledge base.
        url: URL of the knowledge base.
        input_file_path: Path to the file to add to the knowledge base.
        text: Text to add to the knowledge base.
    """
)
def add_knowledge_base_to_agent(
    agent_id: str,
    knowledge_base_name: str,
    url: str | None = None,
    input_file_path: str | None = None,
    text: str | None = None,
) -> TextContent:
    provided_params = [
        param for param in [url, input_file_path, text] if param is not None
    ]
    if len(provided_params) == 0:
        make_error("Must provide either a URL, a file, or text")
    if len(provided_params) > 1:
        make_error("Must provide exactly one of: URL, file, or text")

    if url is not None:
        response = client.conversational_ai.knowledge_base.documents.create_from_url(
            name=knowledge_base_name,
            url=url,
        )
    else:
        if text is not None:
            text_bytes = text.encode("utf-8")
            text_io = BytesIO(text_bytes)
            text_io.name = "text.txt"
            text_io.content_type = "text/plain"
            file = text_io
        elif input_file_path is not None:
            path = handle_input_file(file_path=input_file_path, audio_content_check=False)
            file = open(path, "rb")

        response = client.conversational_ai.knowledge_base.documents.create_from_file(
            name=knowledge_base_name,
            file=file,
        )

    agent = client.conversational_ai.agents.get(agent_id=agent_id)
    agent.conversation_config.agent.prompt.knowledge_base.append(
        KnowledgeBaseLocator(
            type="file" if file else "url",
            name=knowledge_base_name,
            id=response.id,
        )
    )
    client.conversational_ai.agents.update(
        agent_id=agent_id, conversation_config=agent.conversation_config
    )
    return TextContent(
        type="text",
        text=f"""Knowledge base created with ID: {response.id} and added to agent {agent_id} successfully.""",
    )


@mcp.tool(description="List all available conversational AI agents")
def list_agents() -> TextContent:
    """List all available conversational AI agents.

    Returns:
        TextContent with a formatted list of available agents
    """
    response = client.conversational_ai.agents.list()

    if not response.agents:
        return TextContent(type="text", text="No agents found.")

    agent_info = []
    for agent in response.agents:
        agent_info.append(
            f"Name: {agent.name}\n"
            f"ID: {agent.agent_id}"
        )

    formatted_info = "\n\n".join(agent_info)
    return TextContent(type="text", text=f"Available Agents:\n\n{formatted_info}")


@mcp.tool(description="Get details about a specific conversational AI agent")
def get_agent(agent_id: str) -> TextContent:
    """Get details about a specific conversational AI agent.

    Args:
        agent_id: The ID of the agent to retrieve

    Returns:
        TextContent with detailed information about the agent
    """
    response = client.conversational_ai.agents.get(agent_id=agent_id)

    voice_info = "None"
    if response.conversation_config.tts:
        voice_info = f"Voice ID: {response.conversation_config.tts.voice_id}"

    return TextContent(
        type="text",
        text=f"Agent Details: Name: {response.name}, Agent ID: {response.agent_id}, Voice Configuration: {voice_info}, Created At: {datetime.fromtimestamp(response.metadata.created_at_unix_secs).strftime('%Y-%m-%d %H:%M:%S')}",
    )


@mcp.tool(
    description="""Transform audio from one voice to another using provided audio files.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
def speech_to_speech(
    input_file_path: str,
    voice_name: str = "Adam",
    output_directory: str | None = None,
) -> TextContent:
    voices = client.voices.search(search=voice_name)

    if len(voices.voices) == 0:
        make_error("No voice found with that name.")

    voice = next((v for v in voices.voices if v.name == voice_name), None)

    if voice is None:
        make_error(f"Voice with name: {voice_name} does not exist.")

    file_path = handle_input_file(input_file_path)
    output_path = make_output_path(output_directory, base_path)
    output_file_name = make_output_file("sts", file_path.name, output_path, "mp3")

    with file_path.open("rb") as f:
        audio_bytes = f.read()

    audio_data = client.speech_to_speech.convert(
        model_id="eleven_multilingual_sts_v2",
        voice_id=voice.voice_id,
        audio=audio_bytes,
    )

    audio_bytes = b"".join(audio_data)

    with open(output_path / output_file_name, "wb") as f:
        f.write(audio_bytes)

    return TextContent(
        type="text", text=f"Success. File saved as: {output_path / output_file_name}"
    )


@mcp.tool(
    description="""Create voice previews from a text prompt. Creates three previews with slight variations. Saves the previews to a given directory. If no text is provided, the tool will auto-generate text.

    Voice preview files are saved as: voice_design_(generated_voice_id)_(timestamp).mp3

    Example file name: voice_design_Ya2J5uIa5Pq14DNPsbC1_20250403_164949.mp3

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
def text_to_voice(
    voice_description: str,
    text: str | None = None,
    output_directory: str | None = None,
) -> TextContent:
    if voice_description == "":
        make_error("Voice description is required.")

    previews = client.text_to_voice.create_previews(
        voice_description=voice_description,
        text=text,
        auto_generate_text=True if text is None else False,
    )

    output_path = make_output_path(output_directory, base_path)

    generated_voice_ids = []
    output_file_paths = []

    for preview in previews.previews:
        output_file_name = make_output_file(
            "voice_design", preview.generated_voice_id, output_path, "mp3", full_id=True
        )
        output_file_paths.append(str(output_file_name))
        generated_voice_ids.append(preview.generated_voice_id)
        audio_bytes = base64.b64decode(preview.audio_base_64)

        with open(output_path / output_file_name, "wb") as f:
            f.write(audio_bytes)

    return TextContent(
        type="text",
        text=f"Success. Files saved at: {', '.join(output_file_paths)}. Generated voice IDs are: {', '.join(generated_voice_ids)}",
    )


@mcp.tool(
    description="""Add a generated voice to the voice library. Uses the voice ID from the `text_to_voice` tool.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
def create_voice_from_preview(
    generated_voice_id: str,
    voice_name: str,
    voice_description: str,
) -> TextContent:
    voice = client.text_to_voice.create_voice_from_preview(
        voice_name=voice_name,
        voice_description=voice_description,
        generated_voice_id=generated_voice_id,
    )

    return TextContent(
        type="text",
        text=f"Success. Voice created: {voice.name} with ID:{voice.voice_id}",
    )


@mcp.tool(
    description="""Make an outbound call via Twilio using an ElevenLabs agent.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        agent_id: The ID of the agent that will handle the call
        agent_phone_number_id: The ID of the phone number to use for the call
        to_number: The phone number to call (E.164 format: +1xxxxxxxxxx)

    Returns:
        TextContent containing information about the call
    """
)
def make_outbound_call(
    agent_id: str,
    agent_phone_number_id: str,
    to_number: str,
) -> TextContent:
    response = client.conversational_ai.twilio.outbound_call(
        agent_id=agent_id,
        agent_phone_number_id=agent_phone_number_id,
        to_number=to_number,
    )

    # Format response details
    call_details = f"""Outbound Call Initiated:
Agent ID: {agent_id}
Phone Number ID: {agent_phone_number_id}
To: {to_number}
Status: Success"""

    # If response has additional info, include it
    if hasattr(response, '__dict__'):
        for key, value in response.__dict__.items():
            if key not in ['agent_id', 'agent_phone_number_id', 'to_number']:
                call_details += f"\n{key.replace('_', ' ').title()}: {value}"

    return TextContent(type="text", text=call_details)


@mcp.tool(
    description="""Search for a voice across the entire ElevenLabs voice library.

    Args:
        page: Page number to return (0-indexed)
        page_size: Number of voices to return per page (1-100)
        search: Search term to filter voices by

    Returns:
        TextContent containing information about the shared voices
    """
)
def search_voice_library(
    page: int = 0,
    page_size: int = 10,
    search: str | None = None,
) -> TextContent:
    response = client.voices.get_shared(
        page=page,
        page_size=page_size,
        search=search,
    )

    if not response.voices:
        return TextContent(
            type="text", text="No shared voices found with the specified criteria."
        )

    voice_list = []
    for voice in response.voices:
        language_info = "N/A"
        if hasattr(voice, "verified_languages") and voice.verified_languages:
            languages = []
            for lang in voice.verified_languages:
                accent_info = (
                    f" ({lang.accent})"
                    if hasattr(lang, "accent") and lang.accent
                    else ""
                )
                languages.append(f"{lang.language}{accent_info}")
            language_info = ", ".join(languages)

        details = [
            f"Name: {voice.name}",
            f"ID: {voice.voice_id}",
            f"Category: {getattr(voice, 'category', 'N/A')}",
        ]
        # TODO: Make cleaner
        if hasattr(voice, "gender") and voice.gender:
            details.append(f"Gender: {voice.gender}")
        if hasattr(voice, "age") and voice.age:
            details.append(f"Age: {voice.age}")
        if hasattr(voice, "accent") and voice.accent:
            details.append(f"Accent: {voice.accent}")
        if hasattr(voice, "description") and voice.description:
            details.append(f"Description: {voice.description}")
        if hasattr(voice, "use_case") and voice.use_case:
            details.append(f"Use Case: {voice.use_case}")

        details.append(f"Languages: {language_info}")

        if hasattr(voice, "preview_url") and voice.preview_url:
            details.append(f"Preview URL: {voice.preview_url}")

        voice_info = "\n".join(details)
        voice_list.append(voice_info)

    formatted_info = "\n\n".join(voice_list)
    return TextContent(type="text", text=f"Shared Voices:\n\n{formatted_info}")


@mcp.tool(description="List all phone numbers associated with the ElevenLabs account")
def list_phone_numbers() -> TextContent:
    """List all phone numbers associated with the ElevenLabs account.

    Returns:
        TextContent containing formatted information about the phone numbers
    """
    response = client.conversational_ai.phone_numbers.list()

    if not response:
        return TextContent(type="text", text="No phone numbers found.")

    phone_info = []
    for phone in response:
        assigned_agent = "None"
        if phone.assigned_agent:
            assigned_agent = f"{phone.assigned_agent.agent_name} (ID: {phone.assigned_agent.agent_id})"

        phone_info.append(
            f"Phone Number: {phone.phone_number}\n"
            f"ID: {phone.phone_number_id}\n"
            f"Provider: {phone.provider}\n"
            f"Label: {phone.label}\n"
            f"Assigned Agent: {assigned_agent}"
        )

    formatted_info = "\n\n".join(phone_info)
    return TextContent(type="text", text=f"Phone Numbers:\n\n{formatted_info}")


@mcp.tool(description="Play an audio file. Supports WAV and MP3 formats.")
def play_audio(input_file_path: str) -> TextContent:
    file_path = handle_input_file(input_file_path)
    play(open(file_path, "rb").read(), use_ffmpeg=False)
    return TextContent(type="text", text=f"Successfully played audio file: {file_path}")


@mcp.tool(
    description="""Get conversation details including full transcript. By default, waits for the conversation to complete.
    
    ⚠️ COST WARNING: This tool makes API calls which may incur costs.
    
    Args:
        conversation_id: The ID of the conversation to retrieve
        wait_for_completion: If True (default), wait for conversation to complete before returning (max 5 minutes). Set to False for immediate return.
        include_analysis: Include conversation analysis data if available
    
    Returns:
        Conversation details including transcript, status, metadata, and analysis
    """
)
async def get_conversation(
    conversation_id: str,
    wait_for_completion: bool = True,
    include_analysis: bool = True
) -> TextContent:
    """Get conversation details with optional waiting for completion."""
    max_attempts = 60 if wait_for_completion else 1  # 5 minutes max wait
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = custom_client.get(
                f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
                headers={"xi-api-key": api_key}
            )
            
            if response.status_code == 404:
                make_error(f"Conversation with ID {conversation_id} not found")
            elif response.status_code == 403:
                make_error(f"No access to conversation {conversation_id}")
            elif response.status_code != 200:
                make_error(f"API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # If waiting for completion and not done yet
            if wait_for_completion and data.get("status") not in ["done", "failed"]:
                attempt += 1
                if attempt < max_attempts:
                    await asyncio.sleep(5)  # Wait 5 seconds between attempts
                    continue
            
            # Format the response
            status = data.get("status", "unknown")
            agent_id = data.get("agent_id", "N/A")
            
            # Format transcript
            transcript_data = data.get("transcript", [])
            if transcript_data:
                transcript_lines = []
                for entry in transcript_data:
                    speaker = entry.get("speaker", "Unknown")
                    text = entry.get("text", "")
                    timestamp = entry.get("timestamp", "")
                    if timestamp:
                        transcript_lines.append(f"[{timestamp}] {speaker}: {text}")
                    else:
                        transcript_lines.append(f"{speaker}: {text}")
                transcript = "\n".join(transcript_lines)
            else:
                transcript = "No transcript available"
            
            # Build response text
            response_text = f"""Conversation Details:
ID: {conversation_id}
Status: {status}
Agent ID: {agent_id}

Transcript:
{transcript}"""
            
            # Add metadata if available
            metadata = data.get("metadata", {})
            if metadata:
                duration = metadata.get("duration_seconds", "N/A")
                started_at = metadata.get("started_at", "N/A")
                response_text += f"\n\nMetadata:\nDuration: {duration} seconds\nStarted: {started_at}"
            
            # Add analysis if requested and available
            if include_analysis and data.get("analysis"):
                analysis = data.get("analysis", {})
                response_text += f"\n\nAnalysis:\n{analysis}"
            
            return TextContent(type="text", text=response_text)
            
        except Exception as e:
            if attempt == 0:  # Only error on first attempt if not waiting
                make_error(f"Failed to fetch conversation: {str(e)}")
            attempt += 1
            if attempt < max_attempts:
                await asyncio.sleep(5)
    
    # If we get here, we timed out waiting
    return TextContent(
        type="text", 
        text=f"Conversation {conversation_id} did not complete within 5 minutes. Current status: {status}"
    )


@mcp.tool(
    description="""List conversations with optional filtering.
    
    Args:
        agent_id: Filter by specific agent ID
        status: Filter by status (initiated, in-progress, processing, done, failed)
        limit: Number of conversations to return (default: 10, max: 100)
        offset: Pagination offset (default: 0)
    
    Returns:
        List of conversations with basic details
    """
)
def list_conversations(
    agent_id: str | None = None,
    status: str | None = None,
    limit: int = 10,
    offset: int = 0
) -> TextContent:
    """List conversations with filtering options."""
    if limit > 100:
        limit = 100
    
    # Build query parameters
    params = {
        "limit": limit,
        "offset": offset
    }
    if agent_id:
        params["agent_id"] = agent_id
    if status:
        params["status"] = status
    
    try:
        response = custom_client.get(
            "https://api.elevenlabs.io/v1/convai/conversations",
            headers={"xi-api-key": api_key},
            params=params
        )
        
        if response.status_code != 200:
            make_error(f"API error: {response.status_code} - {response.text}")
        
        data = response.json()
        conversations = data.get("conversations", [])
        
        if not conversations:
            return TextContent(type="text", text="No conversations found.")
        
        # Format conversation list
        conv_list = []
        for conv in conversations:
            conv_id = conv.get("conversation_id", "N/A")
            conv_status = conv.get("status", "unknown")
            conv_agent = conv.get("agent_id", "N/A")
            conv_started = conv.get("metadata", {}).get("started_at", "N/A")
            
            conv_info = f"""Conversation ID: {conv_id}
Status: {conv_status}
Agent ID: {conv_agent}
Started: {conv_started}"""
            
            conv_list.append(conv_info)
        
        formatted_list = "\n\n".join(conv_list)
        total = data.get("total", len(conversations))
        
        return TextContent(
            type="text", 
            text=f"Conversations (showing {len(conversations)} of {total}):\n\n{formatted_list}"
        )
        
    except Exception as e:
        make_error(f"Failed to list conversations: {str(e)}")


@mcp.tool(
    description="""Get just the transcript from a conversation.
    
    ⚠️ COST WARNING: This tool makes API calls which may incur costs.
    
    This tool returns transcripts in chunks to avoid token limits. Each response includes:
    - The current chunk number and total chunks available
    - A portion of the transcript (default: 100 entries per chunk)
    
    To get the full transcript:
    1. Call with chunk=1 (or no chunk parameter) to get the first chunk
    2. Check the response for total_chunks (shown as "Chunk X/Y" in output)
    3. Make additional calls with chunk=2, chunk=3, etc. until you have all chunks
    
    Args:
        conversation_id: The ID of the conversation
        format: Format for the transcript ('plain', 'timestamps', 'json')
        chunk: Which chunk to retrieve (1-based, default: 1). Start with 1.
        chunk_size: Number of transcript entries per chunk (default: 100)
    
    Returns:
        A chunk of the conversation transcript in the requested format.
        The response always includes chunk metadata (e.g., "[Chunk 1/5]").
        
    Example usage:
        # First call - get chunk 1 and see how many chunks exist
        get_conversation_transcript(conversation_id="abc123")
        # Output: "[Chunk 1/3] Entries 1-100 of 250 ..."
        
        # Get remaining chunks
        get_conversation_transcript(conversation_id="abc123", chunk=2)
        get_conversation_transcript(conversation_id="abc123", chunk=3)
    """
)
async def get_conversation_transcript(
    conversation_id: str,
    format: Literal["plain", "timestamps", "json"] = "plain",
    chunk: int = 1,
    chunk_size: int = 100
) -> TextContent:
    """Get just the transcript from a conversation.
    
    Args:
        conversation_id: The ID of the conversation
        format: Format for the transcript ('plain', 'timestamps', 'json')
        chunk: Which chunk to retrieve (1-based, default: 1)
        chunk_size: Number of transcript entries per chunk (default: 100)
    """
    try:
        response = custom_client.get(
            f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
            headers={"xi-api-key": api_key}
        )
        
        if response.status_code == 404:
            make_error(
                f"Conversation with ID {conversation_id} not found",
                code="CONVERSATION_NOT_FOUND",
                suggestion="Check the conversation ID or use list_conversations() to see available conversations"
            )
        elif response.status_code != 200:
            make_error(
                f"API error: {response.status_code} - {response.text}",
                code="API_ERROR",
                suggestion="Check your API key and network connection"
            )
        
        data = response.json()
        transcript_data = data.get("transcript", [])
        
        if not transcript_data:
            return TextContent(type="text", text="No transcript available for this conversation.")
        
        # Calculate chunks
        total_entries = len(transcript_data)
        total_chunks = (total_entries + chunk_size - 1) // chunk_size
        
        # Validate chunk number
        if chunk < 1 or chunk > total_chunks:
            make_error(f"Invalid chunk {chunk}. Available chunks: 1-{total_chunks}")
        
        # Get the chunk
        start_idx = (chunk - 1) * chunk_size
        end_idx = min(start_idx + chunk_size, total_entries)
        chunk_data = transcript_data[start_idx:end_idx]
        
        # Format the chunk
        if format == "json":
            # Return raw JSON transcript chunk with metadata
            import json
            chunk_info = {
                "chunk": chunk,
                "total_chunks": total_chunks,
                "chunk_size": chunk_size,
                "entries_in_chunk": len(chunk_data),
                "total_entries": total_entries,
                "transcript": chunk_data
            }
            return TextContent(type="text", text=json.dumps(chunk_info, indent=2))
        elif format == "timestamps":
            # Include timestamps
            lines = [f"[Chunk {chunk}/{total_chunks}] Entries {start_idx+1}-{end_idx} of {total_entries}\n"]
            for entry in chunk_data:
                speaker = entry.get("speaker", "Unknown")
                text = entry.get("text", "")
                timestamp = entry.get("timestamp", "")
                if timestamp:
                    lines.append(f"[{timestamp}] {speaker}: {text}")
                else:
                    lines.append(f"{speaker}: {text}")
            return TextContent(type="text", text="\n".join(lines))
        else:  # plain
            # Just speaker and text
            lines = [f"[Chunk {chunk}/{total_chunks}] Entries {start_idx+1}-{end_idx} of {total_entries}\n"]
            for entry in chunk_data:
                speaker = entry.get("speaker", "Unknown")
                text = entry.get("text", "")
                lines.append(f"{speaker}: {text}")
            return TextContent(type="text", text="\n".join(lines))
            
    except Exception as e:
        make_error(f"Failed to fetch transcript: {str(e)}")


def count_dialogue_chars(inputs):
    """Count actual spoken text, excluding tags"""
    total = 0
    for item in inputs:
        # Remove tags before counting
        text_without_tags = re.sub(r'\[.*?\]', '', item['text'])
        total += len(text_without_tags)
    return total


def split_dialogue_chunks(inputs, max_chars=2800):  # Leave buffer for safety
    """Split dialogue into chunks that fit the 3000 char limit"""
    chunks = []
    current_chunk = []
    current_chars = 0
    
    for item in inputs:
        item_chars = len(re.sub(r'\[.*?\]', '', item['text']))
        if current_chars + item_chars > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [item]
            current_chars = item_chars
        else:
            current_chunk.append(item)
            current_chars += item_chars
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


@mcp.tool(
    description="""🎭 Multi-Speaker Dialogue with ElevenLabs v3 (ALWAYS USES v3 MODEL)
    
    ⚡ QUICK START:
    1. This tool AUTOMATICALLY uses v3 model - all v3 audio tags work!
    2. For single speaker with v3 tags, use text_to_speech(model="v3") instead
    3. For full tag list, call fetch_v3_tags() first
    
    ⚠️ LIMITS:
    - 3000 character limit (excluding tags) - auto-splits if exceeded
    - Stability auto-adjusts to nearest valid value (0.0, 0.5, 1.0)
    - COST WARNING: This tool makes API calls to ElevenLabs which may incur costs
    
    💡 AUTOMATIC FEATURES:
    - Long dialogues split into multiple files automatically
    - Stability values rounded to nearest valid option
    - Character count excludes tags so they don't reduce your content
    
    🎯 COMMON TAGS YOU CAN USE:
    Emotions: [happy], [sad], [angry], [excited], [crying], [laughing], [whispering], [shouting]
    Actions: [breathing heavily], [sighs], [coughing], [sniffling], [sobbing]
    Sounds: [footsteps], [door opening], [thunder], [applause], [wind]
    Voice: [soft], [loud], [fast], [slow], [trembling voice], [voice breaking]
    Special: [pause], [long pause], [silence]
    
    📝 EXAMPLE - Simple conversation:
    inputs = [
        {"text": "Hey, how are you?", "voice_name": "James"},
        {"text": "I'm doing great, thanks!", "voice_name": "Jane"}
    ]
    
    📝 EXAMPLE - Emotional scene with tags:
    inputs = [
        {"text": "[whispering] Are you there? [footsteps approaching]", "voice_name": "Sarah"},
        {"text": "[startled] Oh! [nervous laugh] You scared me!", "voice_name": "Mike"},
        {"text": "[apologetic] Sorry... [pause] I have something to tell you.", "voice_name": "Sarah"}
    ]
    
    💡 PRO TIPS:
    - Combine tags: "[whispering] [crying] I miss you..."
    - Environmental sounds work: "[rain falling] [thunder in distance]"
    - Use pauses for drama: "I... [long pause] I love you."
    - v3-optimized voices work best (James, Jane, Sarah, etc.)
    
    Args:
        inputs: List of dialogue turns, each dict must have:
            - text: The dialogue text with v3 audio tags
            - voice_id OR voice_name: The voice to use
        stability: Auto-adjusts to 0.0, 0.5, or 1.0 (default 0.5)
        similarity_boost: Voice similarity (0-1, default 0.75)
        output_directory: Where to save (default $HOME/Desktop)
    """
)
def text_to_dialogue(
    inputs: list[dict],
    output_directory: str | None = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> TextContent:
    try:
        # Auto-adjust stability to valid v3 values
        original_stability = stability
        if stability not in [0.0, 0.5, 1.0]:
            # Round to nearest valid value
            if stability < 0.35:
                stability = 0.0
            elif stability <= 0.75:
                stability = 0.5
            else:
                stability = 1.0
            print(f"Auto-adjusted stability from {original_stability} to {stability}")
        
        # Validate inputs
        if not inputs or not isinstance(inputs, list):
            make_error("inputs must be a non-empty list of dialogue turns")
        
        # Simplify tags for all inputs
        for input_item in inputs:
            if 'text' in input_item:
                input_item['text'] = simplify_tags(input_item['text'])
                
                # Validate and warn about invalid tags
                invalid_tags = validate_and_warn_tags(input_item['text'])
                if invalid_tags:
                    print(f"Warning: Invalid tags found: {invalid_tags}")
        
        # Process inputs to get voice IDs
        processed_inputs = []
        for i, input_item in enumerate(inputs):
            if not isinstance(input_item, dict):
                make_error(f"Input {i} must be a dict with 'text' and 'voice_name'/'voice_id'")
            
            if "text" not in input_item:
                make_error(f"Input {i} missing required 'text' field")
            
            if "voice_name" in input_item and "voice_id" not in input_item:
                # Look up voice by name
                voices = client.voices.get_all()
                voice = next((v for v in voices.voices if v.name == input_item["voice_name"]), None)
                if not voice:
                    # Get list of available voice names for better error message
                    available_voices = [v.name for v in voices.voices]
                    v3_voices = ["James", "Jane", "Juniper", "Mark", "Arabella", "Hope"]
                    available_v3 = [v for v in v3_voices if v in available_voices]
                    
                    make_error(f"""Voice '{input_item['voice_name']}' not found for dialogue!
                    
🎯 QUICK FIX - Use these v3-optimized voices:
{chr(10).join(f'- "{v}"' for v in available_v3[:6])}

📝 EXAMPLE FIX:
inputs = [
    {{"text": "[excited] Hello!", "voice_name": "James"}},
    {{"text": "[happy] Hi there!", "voice_name": "Jane"}}
]

💡 PRO TIP: Call search_voices("v3") to see all v3-optimized voices!""")
                voice_id = voice.voice_id
            else:
                voice_id = input_item.get("voice_id")
                if not voice_id:
                    make_error(f"Input {i} must have either voice_id or voice_name")
            
            processed_inputs.append({
                "text": input_item["text"],
                "voice_id": voice_id
            })
        
        # Check character count and split if needed
        total_chars = count_dialogue_chars(processed_inputs)
        
        if total_chars > 3000:
            print(f"Dialogue exceeds 3000 char limit ({total_chars} chars). Auto-splitting into chunks...")
            chunks = split_dialogue_chunks(processed_inputs)
            print(f"Split into {len(chunks)} chunks")
        else:
            chunks = [processed_inputs]
        
        # Process each chunk
        output_files = []
        
        for chunk_idx, chunk in enumerate(chunks):
            # Check if v3 proxy is enabled
            if v3_proxy_enabled:
                # Ensure proxy is running
                import subprocess
                import psutil
                import sys
                
                # Check if proxy is already running
                proxy_running = False
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline')
                        if cmdline and 'v3_proxy.py' in ' '.join(cmdline):
                            proxy_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        continue
                
                if not proxy_running:
                    # Start proxy in background
                    proxy_path = os.path.join(os.path.dirname(__file__), 'v3_proxy.py')
                    subprocess.Popen([sys.executable, proxy_path], 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
                    # Give it a moment to start
                    import time
                    time.sleep(2)
                
                # Use proxy endpoint
                endpoint = f"{v3_proxy_url}/v1/text-to-dialogue/stream"
            else:
                # Use direct API endpoint (requires v3 access)
                endpoint = "https://api.elevenlabs.io/v1/text-to-dialogue/stream"
            
            # Make API call to text-to-dialogue endpoint
            response = httpx.post(
            endpoint,
            json={
                "inputs": chunk,
                "model_id": "eleven_v3",
                "settings": {
                    "quality": None,
                    "similarity_boost": similarity_boost,
                    "stability": stability
                }
            },
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            } if not v3_proxy_enabled else {
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            timeout=calculate_dialogue_timeout(chunk)
            )
            
            if response.status_code == 403:
                make_error("v3 access denied. You need special access from ElevenLabs sales")
            elif response.status_code == 422:
                try:
                    error_detail = response.json()
                    make_error(f"Parameter validation error: {error_detail}")
                except:
                    make_error(f"API error: {response.status_code} - {response.text}")
            elif response.status_code != 200:
                make_error(f"API error: {response.status_code} - {response.text}")
            
            # Save audio file
            output_path = make_output_path(output_directory, base_path)
            if len(chunks) > 1:
                output_file_name = make_output_file("dialogue", f"v3_dialogue_part{chunk_idx+1}", output_path, "mp3")
            else:
                output_file_name = make_output_file("dialogue", "v3_dialogue", output_path, "mp3")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path / output_file_name, "wb") as f:
                f.write(response.content)
            
            output_files.append(output_path / output_file_name)
        
        # Return success message
        if len(output_files) == 1:
            return TextContent(
                type="text",
                text=f"Success. Dialogue saved as: {output_files[0]}"
            )
        else:
            files_list = "\n".join(f"- Part {i+1}: {f}" for i, f in enumerate(output_files))
            return TextContent(
                type="text",
                text=f"Success. Dialogue split into {len(output_files)} parts:\n{files_list}"
            )
        
    except Exception as e:
        make_error(f"Failed to generate dialogue: {str(e)}")


@mcp.tool(
    description="""Enhance dialogue text with proper formatting for v3 model generation. Analyzes text and suggests audio tags.
    
    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    
    Args:
        dialogue_blocks: List of dialogue text blocks to enhance
        
    Returns:
        Enhanced dialogue with suggested audio tags and formatting
    """
)
def enhance_dialogue(
    dialogue_blocks: list[str],
) -> TextContent:
    try:
        # Make API call to enhance-dialogue endpoint
        response = httpx.post(
            "https://api.elevenlabs.io/v1/enhance-dialogue",
            json={
                "dialogue_blocks": dialogue_blocks
            },
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            make_error(f"API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Format the enhanced dialogue for display
        if isinstance(result, dict) and "enhanced_blocks" in result:
            enhanced_text = "\n\n".join(result["enhanced_blocks"])
        else:
            # Handle different response formats
            enhanced_text = str(result)
        
        return TextContent(
            type="text",
            text=f"Enhanced dialogue:\n\n{enhanced_text}\n\nYou can now use this enhanced text with the text_to_dialogue or text_to_speech tools."
        )
        
    except Exception as e:
        make_error(f"Failed to enhance dialogue: {str(e)}")


@mcp.tool(
    description="""📋 Get list of v3 audio tags - CALL THIS FIRST before using v3!
    
    ⚡ WHEN TO USE:
    - Before using text_to_speech with model="v3"
    - Before using text_to_dialogue (which always uses v3)
    - When user mentions: tags, emotions, sound effects, v3 features
    - When you need examples of available audio tags
    
    🎯 RETURNS:
    - Comprehensive list of emotional tags ([happy], [crying], etc.)
    - Sound effect tags ([footsteps], [thunder], etc.)
    - Voice modulation tags ([whispering], [shouting], etc.)
    - Special control tags ([pause], [silence], etc.)
    
    💡 TIP: Always call this first to see all available options!
    """
)
def fetch_v3_tags() -> TextContent:
    tags_list = """🎭 **ElevenLabs v3 Audio Tags** (not exhaustive - experiment!)

**Emotions & Expressions:**
• [laughs], [laughs harder], [giggling], [chuckles]
• [sighs], [exhales], [frustrated sigh], [happy gasp]
• [whispers], [whispering], [softly], [SHOUTING]
• [sarcastic], [curious], [excited], [mischievously]
• [crying], [snorts], [impressed], [dramatically]
• [delighted], [amazed], [warmly], [nervously]

**Sound Effects:**
• [footsteps], [door creaking], [thunder], [piano]
• [gunshot], [explosion], [applause], [clapping]
• [swallows], [gulps], [leaves rustling]

**Special:**
• [strong X accent] (e.g., [strong British accent])
• [sings], [yawns], [woo]

💡 **Quick Tips:**
- Use CAPITALS for emphasis
- Add ... for pauses
- Match tags to context
- Don't overuse tags

📝 **Example:**
"[softly] In the quiet forest, [footsteps] she walked carefully. [whispers] 'Is anyone there?' [nervous laugh] No response came."

For full guide with best practices, use: get_v3_audio_tags_guide()"""
    
    return TextContent(type="text", text=tags_list)


@mcp.tool(
    description="""Get comprehensive guide for using ElevenLabs v3 audio tags and best practices.
    
    This tool provides:
    - Complete list of available audio tags
    - Detailed best practices for v3 prompting
    - Extended examples of effective tag usage
    - Tips for different use cases
    
    No API call required - returns instructional content.
    """
)
def get_v3_audio_tags_guide() -> TextContent:
    guide = """# ElevenLabs v3 Audio Tags & Best Practices Guide

## 🎭 Available Audio Tags

### Emotional Expression
- **Laughter**: [laughs], [laughs harder], [starts laughing], [wheezing]
- **Vocal Styles**: [whispers], [whispering], [sighs], [exhales], [softly]
- **Emotions**: [sarcastic], [curious], [excited], [crying], [snorts], [mischievously]
- **Extended Emotions**: [frustrated sigh], [happy gasp], [excitedly], [curiously], [impressed], [dramatically], [giggling], [delighted], [amazed], [warmly]
- **Emphasis**: [SHOUTING] or use CAPITALS for emphasis

### Sound Effects
- **Actions**: [gunshot], [applause], [clapping], [explosion], [swallows], [gulps]
- **Environmental**: [footsteps], [door creaking], [thunder], [piano], [leaves rustling]

### Special Tags (Experimental)
- **Accents**: [strong X accent] (replace X with any accent, e.g., [strong British accent])
- **Musical**: [sings], [woo]
- **Other**: [fart] (yes, really!)

## 📝 Example Usage

Here's a complete example showing effective v3 tag usage:

```
In the ancient land of Eldoria, where skies shimmered and forests [whispering] whispered secrets to the wind, lived a dragon named Zephyros. [sarcastic] Not the "burn it all down" kind - [exhales] he was gentle, wise, with eyes like old stars. [softly] Even the birds fell silent when he passed.

[footsteps] The young knight approached the cave. [nervous laugh] "H-hello?" she called out. [SHOUTING] "IS ANYONE THERE?"

[dramatically] "Who dares disturb my slumber?" [yawns] the dragon replied. [impressed] "Ah, a knight! [laughs] How delightfully old-fashioned!"
```

## 💡 Best Practices

1. **Voice Selection Matters**: Choose a voice that matches your intended style. A whispering voice won't shout effectively.
   
   **v3-Optimized Voices** (recommended for best tag responsiveness):
   - **James** (EkK5I93UQWFDigLMpZcX): Husky & engaging, slightly bassy with standard American accent. Perfect for audiobooks and professional voiceover
   - **Jane** (RILOU7YmBhvwJGDGjNmP): Professional English audiobook narrator in her 50s, great for narration and storytelling
   - **Juniper** (aMSt68OGf4xUZAnLpTU8): Grounded female professional, great for podcasts or ConvoAI
   - **Arabella** (Z3R5wn05IrDiVCyEkUrK): Young, mature female narrator with mysterious & emotive tone for fantasy/romance
   - **Nichalia Schwartz** (XfNU2rGpBa01ckF309OY): Friendly, intelligent 20s-30s female American for audiobooks & eLearning
   - **Hope** (tnSpp4vdxKPjI9w0GnoV): Upbeat and clear
   - **Bradford** (NNl6r8mD7vthiJatiJt1): Adult British male storyteller, expressive & articulate
   - **Reginald** (Hjzqw9NR0xFMYU9Us0DL): Dark, brooding intense villain character voice for video games
   - **Gaming – Unreal Tonemanagement 2003** (YOq2y2Up4RgXP2HyXjE5): Retro-futuristic announcer style, sharp metallic authority
   - **Austin** (Bj9UqZbhQsanLzgalpEG): Good ol' Texas boy with strong accent, deep gravelly voice
   - **kuon** (B8gJV1IhpuegLxdpXFOE): Acute female & fantastic voice
   - **Blondie** (exsUS4vynmxd379XN4yO): British woman with warm, natural conversational voice
   - **Priyanka Sogam** (BpjGufoPiobT79j2vtj4): Late night radio voice with neutral accent, smooth & soothing
   - **Alexandra** (kdmDKE6EkgrWrrykO9Qt): Youthful, authentic & conversational, relatable and down-to-earth
   - **Monika Sogam** (2zRM7PkgwBPiau2jvVXc): Indian English accent for social media videos & audiobooks
   - **Jenna** (TgnhEILA8UwUqIMi20rp): 30yo female American, warm & articulate for podcasts and narration
   - **Mark** (1SM7GgM6IMuvQlz2BwM3): ConvoAI optimized
   - **Grimblewood Thornwhisker** (ouL9IsyrSnUkCmfnD02u): British gnome character, high-pitched raspy with snarky comedic timing
   - **Adeline** (5l5f8iK3YPeGga21rQIX): Conversational feminine voice perfect for narration
   - **Sam** (scOwDtmlUjD3prqpp97I): Warm middle-aged American for support agents & audiobooks

2. **Prompt Length**: Use prompts > 250 characters for best results with v3.

3. **Punctuation is Key**:
   - Use ellipses (...) for natural pauses
   - CAPITALS increase emphasis naturally
   - Proper punctuation creates rhythm

4. **Stability Settings** (v3 requires exact values):
   - **0.0 - Creative**: Most expressive but may hallucinate
   - **0.5 - Natural**: Balanced (recommended for most uses) 
   - **1.0 - Robust**: Very stable but less responsive to tags
   ⚠️ v3 ONLY accepts these exact values: 0.0, 0.5, or 1.0

5. **Context Matters**: Tags work better when they make sense in context. Don't overuse them.

## ⚠️ Important Notes

- These tags are **not exhaustive** - experiment with variations!
- Tag effectiveness depends on the voice's training data
- Some tags are experimental and may produce unexpected results
- Professional Voice Clones (PVCs) may not respond to all tags yet
- v3 is in ALPHA - expect improvements and changes

## 🎯 Tips for Success

1. Start simple - add one or two tags and test
2. Match emotional tags to content ([happy gasp] for good news)
3. Use sound effects sparingly for impact
4. Test different voices to find the best match
5. Adjust stability settings based on your needs

## 🌍 Language Support

v3 supports 70+ languages including English, Spanish, French, German, Japanese, Korean, Chinese, and many more. Tags generally work across languages but test for best results.

Remember: The key to great v3 audio is experimentation. Try different combinations and have fun!"""
    
    return TextContent(
        type="text",
        text=guide
    )


def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
