"""Entry point to launch the EchoScribe background server."""
import sys
import uvicorn
from src.config import HOST, PORT

if __name__ == "__main__":
    print("=" * 60)
    print(f"  EchoScribe Speech-to-Text & Dictionary Service")
    print(f"  Listening on: http://{HOST}:{PORT}")
    print(f"  Swagger Docs: http://localhost:{PORT}/docs")
    print("=" * 60)
    uvicorn.run("src.server:app", host=HOST, port=PORT, reload=False, log_level="info")
