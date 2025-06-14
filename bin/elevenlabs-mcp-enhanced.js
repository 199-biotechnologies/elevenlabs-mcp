#!/usr/bin/env node

const { spawn } = require('cross-spawn');
const path = require('path');
const fs = require('fs');
const which = require('which');

// Load environment variables
require('dotenv').config();

async function findPython() {
  const pythonCommands = ['python3', 'python'];
  
  for (const cmd of pythonCommands) {
    try {
      const pythonPath = await which(cmd);
      // Check if it's Python 3.11+
      const result = spawn.sync(cmd, ['--version'], { encoding: 'utf8' });
      if (result.stdout) {
        const version = result.stdout.match(/Python (\d+)\.(\d+)/);
        if (version && (parseInt(version[1]) > 3 || (parseInt(version[1]) === 3 && parseInt(version[2]) >= 11))) {
          return pythonPath;
        }
      }
    } catch (error) {
      // Continue to next python command
    }
  }
  
  throw new Error('Python 3.11+ is required but not found. Please install Python 3.11 or higher.');
}

async function main() {
  try {
    // Get the API key from environment or command line
    let apiKey = process.env.ELEVENLABS_API_KEY;
    
    // Parse command line arguments
    const args = process.argv.slice(2);
    const apiKeyIndex = args.indexOf('--api-key');
    
    if (apiKeyIndex !== -1 && args[apiKeyIndex + 1]) {
      apiKey = args[apiKeyIndex + 1];
      // Remove api-key from args to pass to Python
      args.splice(apiKeyIndex, 2);
    }
    
    if (!apiKey && !args.includes('--help') && !args.includes('-h')) {
      console.error('Error: ELEVENLABS_API_KEY environment variable or --api-key argument is required');
      console.error('Usage: npx @199-biotechnologies/elevenlabs-mcp-enhanced --api-key YOUR_API_KEY');
      console.error('Or set ELEVENLABS_API_KEY environment variable');
      process.exit(1);
    }
    
    // Find Python executable
    const pythonPath = await findPython();
    
    // Get the path to the Python module
    const modulePath = path.join(__dirname, '..', 'elevenlabs_mcp');
    
    // Prepare environment variables
    const env = { ...process.env };
    if (apiKey) {
      env.ELEVENLABS_API_KEY = apiKey;
    }
    
    // Check if we need to install dependencies first
    const checkResult = spawn.sync(pythonPath, ['-c', 'import elevenlabs_mcp'], {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8'
    });
    
    if (checkResult.status !== 0) {
      console.log('Python dependencies not found. Installing...');
      const setupPath = path.join(__dirname, '..', 'scripts', 'setup.js');
      const setupResult = spawn.sync('node', [setupPath], {
        stdio: 'inherit',
        cwd: path.join(__dirname, '..')
      });
      
      if (setupResult.status !== 0) {
        console.error('Failed to install dependencies. Please run: pip install elevenlabs mcp');
        process.exit(1);
      }
    }
    
    // Launch the Python MCP server
    const pythonArgs = ['-m', 'elevenlabs_mcp', ...args];
    
    console.log('Starting ElevenLabs MCP Enhanced server...');
    
    const child = spawn(pythonPath, pythonArgs, {
      cwd: path.join(__dirname, '..'),
      env: env,
      stdio: 'inherit'
    });
    
    child.on('error', (error) => {
      console.error('Failed to start server:', error.message);
      process.exit(1);
    });
    
    child.on('exit', (code) => {
      process.exit(code || 0);
    });
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

// Handle process termination
process.on('SIGINT', () => {
  process.exit(0);
});

process.on('SIGTERM', () => {
  process.exit(0);
});

main();