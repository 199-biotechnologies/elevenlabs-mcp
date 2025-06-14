import os
os.environ["ELEVENLABS_EMAIL"] = "boris@199.bio" 
os.environ["ELEVENLABS_PASSWORD"] = "vasnig-mygneG-tefzo8"

# Import and run the proxy
import sys
sys.path.insert(0, ".")
from elevenlabs_mcp.v3_proxy import run_proxy
run_proxy()
