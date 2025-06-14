#!/usr/bin/env python3
"""Test the v3 proxy functionality"""

import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_proxy():
    # Test direct proxy endpoint
    url = "http://localhost:8123/v1/text-to-dialogue/stream"
    
    payload = {
        "inputs": [{
            "text": "[thoughtful] Testing v3 proxy... [laughs] This should work with audio tags!",
            "voice_id": "21m00Tcm4TlvDq8ikWAM"
        }],
        "model_id": "eleven_v3",
        "settings": {
            "quality": None,
            "similarity_boost": 0.75,
            "stability": 0.5
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # First check health
            health = await client.get("http://localhost:8123/health")
            print(f"Proxy health: {health.json()}")
            
            # Make v3 request
            response = await client.post(url, json=payload, timeout=30.0)
            
            if response.status_code == 200:
                print(f"Success! Audio size: {len(response.content)} bytes")
                # Save audio
                with open("test_v3_proxy_output.mp3", "wb") as f:
                    f.write(response.content)
                print("Audio saved to test_v3_proxy_output.mp3")
            else:
                print(f"Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_proxy())