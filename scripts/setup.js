#!/usr/bin/env node

const { spawn } = require('cross-spawn');
const fs = require('fs');
const path = require('path');
const which = require('which');

console.log('Setting up ElevenLabs MCP Enhanced...');

async function findPython() {
  const pythonCommands = ['python3', 'python'];
  
  for (const cmd of pythonCommands) {
    try {
      const pythonPath = await which(cmd);
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
  
  return null;
}

async function checkPip(pythonPath) {
  const result = spawn.sync(pythonPath, ['-m', 'pip', '--version'], { encoding: 'utf8' });
  return result.status === 0;
}

async function installDependencies(pythonPath) {
  console.log('Installing Python dependencies...');
  
  // Install the package in development mode
  const installArgs = ['-m', 'pip', 'install', '-e', '.'];
  
  const child = spawn(pythonPath, installArgs, {
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit'
  });
  
  return new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`pip install failed with code ${code}`));
      }
    });
  });
}

async function main() {
  try {
    // Check for Python
    const pythonPath = await findPython();
    
    if (!pythonPath) {
      console.error('\n❌ Python 3.11+ is required but not found.');
      console.error('Please install Python 3.11 or higher from https://www.python.org/downloads/');
      process.exit(1);
    }
    
    console.log(`✓ Found Python at: ${pythonPath}`);
    
    // Check for pip
    const hasPip = await checkPip(pythonPath);
    if (!hasPip) {
      console.error('\n❌ pip is not available.');
      console.error('Please ensure pip is installed with your Python installation.');
      process.exit(1);
    }
    
    console.log('✓ pip is available');
    
    // Install Python dependencies
    await installDependencies(pythonPath);
    
    console.log('\n✅ Setup complete!');
    console.log('\nTo use the server:');
    console.log('  npx @199-biotechnologies/elevenlabs-mcp-enhanced --api-key YOUR_API_KEY');
    console.log('\nOr set the ELEVENLABS_API_KEY environment variable and run:');
    console.log('  npx @199-biotechnologies/elevenlabs-mcp-enhanced');
    
  } catch (error) {
    console.error('\n❌ Setup failed:', error.message);
    process.exit(1);
  }
}

main();