# ElevenLabs MCP Enhanced

<div class="title-block" style="text-align: center;" align="center">

  [![Discord Community](https://img.shields.io/badge/discord-@elevenlabs-000000.svg?style=for-the-badge&logo=discord&labelColor=000)](https://discord.gg/elevenlabs)
  [![Twitter](https://img.shields.io/badge/Twitter-@elevenlabsio-000000.svg?style=for-the-badge&logo=twitter&labelColor=000)](https://x.com/ElevenLabsDevs)
  [![PyPI](https://img.shields.io/badge/PyPI-elevenlabs--mcp-000000.svg?style=for-the-badge&logo=pypi&labelColor=000)](https://pypi.org/project/elevenlabs-mcp)
  [![Tests](https://img.shields.io/badge/tests-passing-000000.svg?style=for-the-badge&logo=github&labelColor=000)](https://github.com/elevenlabs/elevenlabs-mcp-server/actions/workflows/test.yml)

</div>

<p align="center">
  <strong>Enhanced fork of the official ElevenLabs MCP server</strong> with additional conversational AI features including conversation history and transcript retrieval.
</p>

<p align="center">
  This enhanced version is developed and maintained by <strong>Boris Djordjevic</strong> and the <strong>199 Longevity</strong> team.
</p>

## 🚀 What's New in This Fork

This enhanced version adds critical conversational AI features missing from the original:

- **🎙️ Conversation History**: Retrieve full conversation details including transcripts
- **📝 Transcript Access**: Get conversation transcripts in multiple formats (plain, timestamps, JSON)
- **⏳ Real-time Monitoring**: Wait for ongoing conversations to complete and retrieve results
- **🔍 Conversation Search**: List and filter conversations by agent, status, and more
- **🎨 Improved Formatting**: Consistent formatting across all list operations

## About

This is an enhanced fork of the official ElevenLabs <a href="https://github.com/modelcontextprotocol">Model Context Protocol (MCP)</a> server that enables interaction with powerful Text to Speech and audio processing APIs. This server allows MCP clients like <a href="https://www.anthropic.com/claude">Claude Desktop</a>, <a href="https://www.cursor.so">Cursor</a>, <a href="https://codeium.com/windsurf">Windsurf</a>, <a href="https://github.com/openai/openai-agents-python">OpenAI Agents</a> and others to generate speech, clone voices, transcribe audio, manage conversational AI agents, and now retrieve conversation history.

## Quickstart with Claude Desktop

### Option 1: Using npm/npx (Recommended - No installation required!)

1. Get your API key from [ElevenLabs](https://elevenlabs.io/app/settings/api-keys). There is a free tier with 10k credits per month.
2. Go to Claude > Settings > Developer > Edit Config > claude_desktop_config.json to include the following:

```json
{
  "mcpServers": {
    "ElevenLabs": {
      "command": "npx",
      "args": ["elevenlabs-mcp-enhanced"],
      "env": {
        "ELEVENLABS_API_KEY": "<insert-your-api-key-here>"
      }
    }
  }
}
```

That's it! No installation needed - npx will automatically download and run the server.

### Option 2: Using Python and uv

1. Get your API key from [ElevenLabs](https://elevenlabs.io/app/settings/api-keys).
2. Install `uv` (Python package manager), install with `curl -LsSf https://astral.sh/uv/install.sh | sh` or see the `uv` [repo](https://github.com/astral-sh/uv) for additional install methods.
3. Go to Claude > Settings > Developer > Edit Config > claude_desktop_config.json to include the following:

```json
{
  "mcpServers": {
    "ElevenLabs": {
      "command": "uvx",
      "args": ["elevenlabs-mcp"],
      "env": {
        "ELEVENLABS_API_KEY": "<insert-your-api-key-here>"
      }
    }
  }
}
```

If you're using Windows, you will have to enable "Developer Mode" in Claude Desktop to use the MCP server. Click "Help" in the hamburger menu at the top left and select "Enable Developer Mode".

## Other MCP clients

### Using npm/npx:
For other clients like Cursor and Windsurf, you can run the server directly:
```bash
npx elevenlabs-mcp-enhanced --api-key YOUR_API_KEY
```

### Using Python:
1. `pip install elevenlabs-mcp`
2. `python -m elevenlabs_mcp --api-key={{PUT_YOUR_API_KEY_HERE}} --print` to get the configuration. Paste it into appropriate configuration directory specified by your MCP client.

That's it. Your MCP client can now interact with ElevenLabs through these tools:

## Example usage

⚠️ Warning: ElevenLabs credits are needed to use these tools.

Try asking Claude:

- "Create an AI agent that speaks like a film noir detective and can answer questions about classic movies"
- "Generate three voice variations for a wise, ancient dragon character, then I will choose my favorite voice to add to my voice library"
- "Convert this recording of my voice to sound like a medieval knight"
- "Create a soundscape of a thunderstorm in a dense jungle with animals reacting to the weather"
- "Turn this speech into text, identify different speakers, then convert it back using unique voices for each person"

### 🆕 New Conversation Features

With the enhanced conversation tools, you can now:

- "Get the conversation transcript from conversation ID abc123" (automatically waits for completion)
- "List all conversations from my agent and show me the completed ones"
- "Get conversation xyz789 immediately without waiting" (set wait_for_completion=false)
- "Show me all conversations in JSON format with timestamps"
- "Get the conversation history including analysis data"

**Note:** The `get_conversation` tool now waits for conversations to complete by default (up to 5 minutes), ensuring you always get the full transcript.

## Optional features

You can add the `ELEVENLABS_MCP_BASE_PATH` environment variable to the `claude_desktop_config.json` to specify the base path MCP server should look for and output files specified with relative paths.

## Contributing

If you want to contribute or run from source:

1. Clone the repository:

```bash
git clone https://github.com/elevenlabs/elevenlabs-mcp
cd elevenlabs-mcp
```

2. Create a virtual environment and install dependencies [using uv](https://github.com/astral-sh/uv):

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

3. Copy `.env.example` to `.env` and add your ElevenLabs API key:

```bash
cp .env.example .env
# Edit .env and add your API key
```

4. Run the tests to make sure everything is working:

```bash
./scripts/test.sh
# Or with options
./scripts/test.sh --verbose --fail-fast
```

5. Install the server in Claude Desktop: `mcp install elevenlabs_mcp/server.py`

6. Debug and test locally with MCP Inspector: `mcp dev elevenlabs_mcp/server.py`

## Troubleshooting

Logs when running with Claude Desktop can be found at:

- **Windows**: `%APPDATA%\Claude\logs\mcp-server-elevenlabs.log`
- **macOS**: `~/Library/Logs/Claude/mcp-server-elevenlabs.log`

### Timeouts when using certain tools

Certain ElevenLabs API operations, like voice design and audio isolation, can take a long time to resolve. When using the MCP inspector in dev mode, you might get timeout errors despite the tool completing its intended task.

This shouldn't occur when using a client like Claude.

### MCP ElevenLabs: spawn uvx ENOENT

If you encounter the error "MCP ElevenLabs: spawn uvx ENOENT", confirm its absolute path by running this command in your terminal:

```bash
which uvx
```

Once you obtain the absolute path (e.g., `/usr/local/bin/uvx`), update your configuration to use that path (e.g., `"command": "/usr/local/bin/uvx"`). This ensures that the correct executable is referenced.

## Credits

### Enhanced Fork
- **Boris Djordjevic** - Lead Developer
- **199 Longevity Team** - Development and Testing

### Original ElevenLabs MCP Server
- **Jacek Duszenko** - jacek@elevenlabs.io
- **Paul Asjes** - paul.asjes@elevenlabs.io
- **Louis Jordan** - louis@elevenlabs.io
- **Luke Harries** - luke@elevenlabs.io

This enhanced fork builds upon the excellent foundation created by the ElevenLabs team, adding critical conversational AI features for improved agent interaction and monitoring.

## License

This project maintains the same MIT license as the original ElevenLabs MCP server. See [LICENSE](LICENSE) for details.
