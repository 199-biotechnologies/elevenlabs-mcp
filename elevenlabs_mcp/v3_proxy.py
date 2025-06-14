"""
ElevenLabs v3 Proxy Server

This proxy handles Firebase authentication and forwards v3 requests with proper JWT tokens.
It automatically refreshes tokens before they expire.
"""

import os
import json
import time
import asyncio
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
from typing import Optional
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class FirebaseAuth:
    def __init__(self):
        self.email = os.getenv("ELEVENLABS_EMAIL")
        self.password = os.getenv("ELEVENLABS_PASSWORD")
        self.api_key = "AIzaSyBSsRE_1Os04-bxpd5JTLIniy3UK4OqKys"
        self.id_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.client = httpx.AsyncClient(timeout=120.0)
        
    async def login(self):
        """Login to Firebase and get tokens"""
        if not self.email or not self.password:
            raise ValueError("ELEVENLABS_EMAIL and ELEVENLABS_PASSWORD must be set")
            
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.api_key}"
        
        payload = {
            "returnSecureToken": True,
            "email": self.email,
            "password": self.password,
            "clientType": "CLIENT_TYPE_WEB"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://elevenlabs.io",
            "X-Client-Version": "Chrome/JsCore/11.2.0/FirebaseCore-web"
        }
        
        response = await self.client.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Login failed: {response.text}")
            raise HTTPException(status_code=401, detail="Login failed")
            
        data = response.json()
        self.id_token = data["idToken"]
        self.refresh_token = data["refreshToken"]
        expires_in = int(data["expiresIn"])
        # Refresh 5 minutes before expiry
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
        logger.info("Successfully logged in to Firebase")
        
    async def refresh_id_token(self):
        """Refresh the ID token using refresh token"""
        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        response = await self.client.post(url, data=payload)
        
        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.text}")
            # Try full login again
            await self.login()
            return
            
        data = response.json()
        self.id_token = data["id_token"]
        self.refresh_token = data["refresh_token"]
        expires_in = int(data["expires_in"])
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
        logger.info("Successfully refreshed token")
        
    async def get_valid_token(self) -> str:
        """Get a valid ID token, refreshing if necessary"""
        if not self.id_token or not self.token_expires_at:
            await self.login()
        elif datetime.now() >= self.token_expires_at:
            await self.refresh_id_token()
            
        return self.id_token

# Global auth instance
auth = FirebaseAuth()

@app.on_event("startup")
async def startup_event():
    """Login on startup"""
    try:
        await auth.login()
    except Exception as e:
        logger.error(f"Failed to login on startup: {e}")

@app.post("/v1/text-to-dialogue/stream")
async def proxy_v3_dialogue(request: Request):
    """Proxy v3 text-to-dialogue requests"""
    try:
        # Get valid token
        token = await auth.get_valid_token()
        
        # Get request body
        body = await request.body()
        
        # Forward request to ElevenLabs
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "Origin": "https://elevenlabs.io",
            "Referer": "https://elevenlabs.io/"
        }
        
        response = await auth.client.post(
            "https://api.us.elevenlabs.io/v1/text-to-dialogue/stream",
            content=body,
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"v3 request failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        # Return audio stream
        return Response(
            content=response.content,
            media_type="audio/mpeg",
            headers={
                "Content-Type": "audio/mpeg",
                "Content-Length": str(len(response.content))
            }
        )
        
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "authenticated": auth.id_token is not None,
        "token_expires_at": auth.token_expires_at.isoformat() if auth.token_expires_at else None
    }

def run_proxy():
    """Run the proxy server"""
    port = int(os.getenv("V3_PROXY_PORT", "8123"))
    logger.info(f"Starting v3 proxy server on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)

if __name__ == "__main__":
    run_proxy()