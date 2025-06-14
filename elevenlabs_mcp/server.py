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
    description="""Convert text to speech with a given voice. 🆕 Now supports ElevenLabs v3 model!
    
    🚀 To use v3: Set model="v3" for enhanced expressiveness and audio tags support
    
    Directory is optional, if not provided, the output file will be saved to $HOME/Desktop.
    Only one of voice_id or voice_name can be provided. If none are provided, the default voice will be used.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    
    🎭 AUDIO TAGS (v3 only): When using model='v3', you can include tags like [thoughtful], [crying], [laugh], [piano], etc.

     Args:
        text (str): The text to convert to speech. Can include audio tags when using v3 model.
        voice_name (str, optional): The name of the voice to use.
        stability (float, optional): Stability of the generated audio. Determines how stable the voice is and the randomness between each generation. Lower values introduce broader emotional range for the voice. Higher values can result in a monotonous voice with limited emotion. Range is 0 to 1.
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
        voice = client.voices.get(voice_id=voice_id)
    elif voice_name is not None:
        voices = client.voices.search(search=voice_name)
        if len(voices.voices) == 0:
            make_error("No voices found with that name.")
        voice = next((v for v in voices.voices if v.name == voice_name), None)
        if voice is None:
            make_error(f"Voice with name: {voice_name} does not exist.")

    voice_id = voice.voice_id if voice else DEFAULT_VOICE_ID

    output_path = make_output_path(output_directory, base_path)
    output_file_name = make_output_file("tts", text, output_path, "mp3")

    # Select model based on user preference
    if model == "v3":
        model_id = "eleven_v3"
    elif model == "flash":
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
        make_error("Duration must be between 0.5 and 5 seconds")
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
    Search for existing voices, a voice that has already been added to the user's ElevenLabs voice library.
    Searches in name, description, labels and category.

    Args:
        search: Search term to filter voices by. Searches in name, description, labels and category.
        sort: Which field to sort by. `created_at_unix` might not be available for older voices.
        sort_direction: Sort order, either ascending or descending.

    Returns:
        List of voices that match the search criteria.
    """
)
def search_voices(
    search: str | None = None,
    sort: Literal["created_at_unix", "name"] = "name",
    sort_direction: Literal["asc", "desc"] = "desc",
) -> list[McpVoice]:
    response = client.voices.search(
        search=search, sort=sort, sort_direction=sort_direction
    )
    return [
        McpVoice(id=voice.voice_id, name=voice.name, category=voice.category)
        for voice in response.voices
    ]


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
    
    Args:
        conversation_id: The ID of the conversation
        format: Format for the transcript ('plain', 'timestamps', 'json')
    
    Returns:
        The conversation transcript in the requested format
    """
)
async def get_conversation_transcript(
    conversation_id: str,
    format: Literal["plain", "timestamps", "json"] = "plain"
) -> TextContent:
    """Get just the transcript from a conversation."""
    try:
        response = custom_client.get(
            f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
            headers={"xi-api-key": api_key}
        )
        
        if response.status_code == 404:
            make_error(f"Conversation with ID {conversation_id} not found")
        elif response.status_code != 200:
            make_error(f"API error: {response.status_code} - {response.text}")
        
        data = response.json()
        transcript_data = data.get("transcript", [])
        
        if not transcript_data:
            return TextContent(type="text", text="No transcript available for this conversation.")
        
        if format == "json":
            # Return raw JSON transcript
            import json
            return TextContent(type="text", text=json.dumps(transcript_data, indent=2))
        elif format == "timestamps":
            # Include timestamps
            lines = []
            for entry in transcript_data:
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
            lines = []
            for entry in transcript_data:
                speaker = entry.get("speaker", "Unknown")
                text = entry.get("text", "")
                lines.append(f"{speaker}: {text}")
            return TextContent(type="text", text="\n".join(lines))
            
    except Exception as e:
        make_error(f"Failed to fetch transcript: {str(e)}")


@mcp.tool(
    description="""🆕 NEW v3 FEATURE: Generate natural dialogue between multiple speakers with enhanced expressiveness!
    
    This uses the new ElevenLabs v3 model for multi-speaker dialogue generation.
    
    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    
    🎭 AUDIO TAGS: You can include tags like [thoughtful], [crying], [laughing], [piano], [footsteps], etc.
    
    Args:
        inputs: List of dialogue turns, each with text and voice_id/voice_name
        output_directory: Directory where the audio file should be saved (defaults to $HOME/Desktop)
        stability: Stability of the generated audio (0-1, default 0.5)
        similarity_boost: Similarity boost of the generated audio (0-1, default 0.75)
        
    Returns:
        Path to the generated audio file
    """
)
def text_to_dialogue(
    inputs: list[dict],
    output_directory: str | None = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> TextContent:
    try:
        # Process inputs to get voice IDs
        processed_inputs = []
        for input_item in inputs:
            if "voice_name" in input_item and "voice_id" not in input_item:
                # Look up voice by name
                voices = client.voices.get_all()
                voice = next((v for v in voices.voices if v.name == input_item["voice_name"]), None)
                if not voice:
                    make_error(f"Voice with name '{input_item['voice_name']}' not found")
                voice_id = voice.voice_id
            else:
                voice_id = input_item.get("voice_id")
                if not voice_id:
                    make_error("Each input must have either voice_id or voice_name")
            
            processed_inputs.append({
                "text": input_item["text"],
                "voice_id": voice_id
            })
        
        # Make API call to text-to-dialogue endpoint
        response = httpx.post(
            "https://api.elevenlabs.io/v1/text-to-dialogue/stream",
            json={
                "inputs": processed_inputs,
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
            },
            timeout=120.0
        )
        
        if response.status_code != 200:
            make_error(f"API error: {response.status_code} - {response.text}")
        
        # Save audio file
        output_path = make_output_path(output_directory, base_path)
        output_file_name = make_output_file("dialogue", "v3_dialogue", output_path, "mp3")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path / output_file_name, "wb") as f:
            f.write(response.content)
        
        return TextContent(
            type="text",
            text=f"Success. Dialogue saved as: {output_path / output_file_name}"
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


def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
