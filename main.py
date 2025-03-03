import json
import os
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import urlopen
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    raise ImportError(
        "`youtube_transcript_api` not installed. Please install using `pip install youtube_transcript_api`"
    )

app = FastAPI(title="YouTube Tools API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class YouTubeTools:
    @staticmethod
    def get_youtube_video_id(url: str) -> Optional[str]:
        """Function to get the video ID from a YouTube URL."""
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        if hostname == "youtu.be":
            return parsed_url.path[1:]
        if hostname in ("www.youtube.com", "youtube.com"):
            if parsed_url.path == "/watch":
                query_params = parse_qs(parsed_url.query)
                return query_params.get("v", [None])[0]
            if parsed_url.path.startswith("/embed/"):
                return parsed_url.path.split("/")[2]
            if parsed_url.path.startswith("/v/"):
                return parsed_url.path.split("/")[2]
        return None

    @staticmethod
    def get_video_data(url: str) -> dict:
        """Function to get video data from a YouTube URL."""
        if not url:
            raise HTTPException(status_code=400, detail="No URL provided")

        try:
            video_id = YouTubeTools.get_youtube_video_id(url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        except Exception:
            raise HTTPException(status_code=400, detail="Error getting video ID from URL")

        try:
            params = {"format": "json", "url": f"https://www.youtube.com/watch?v={video_id}"}
            oembed_url = "https://www.youtube.com/oembed"
            query_string = urlencode(params)
            full_url = oembed_url + "?" + query_string

            with urlopen(full_url) as response:
                response_text = response.read()
                video_data = json.loads(response_text.decode())
                clean_data = {
                    "title": video_data.get("title"),
                    "author_name": video_data.get("author_name"),
                    "author_url": video_data.get("author_url"),
                    "type": video_data.get("type"),
                    "height": video_data.get("height"),
                    "width": video_data.get("width"),
                    "version": video_data.get("version"),
                    "provider_name": video_data.get("provider_name"),
                    "provider_url": video_data.get("provider_url"),
                    "thumbnail_url": video_data.get("thumbnail_url"),
                }
                return clean_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting video data: {str(e)}")

    @staticmethod
    def get_video_captions(url: str, languages: Optional[List[str]] = None) -> str:
        """Get captions from a YouTube video."""
        if not url:
            raise HTTPException(status_code=400, detail="No URL provided")

        try:
            video_id = YouTubeTools.get_youtube_video_id(url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        except Exception:
            raise HTTPException(status_code=400, detail="Error getting video ID from URL")

        try:
            captions = None
            if languages:
                captions = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            else:
                captions = YouTubeTranscriptApi.get_transcript(video_id)
            
            if captions:
                return " ".join(line["text"] for line in captions)
            return "No captions found for video"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting captions for video: {str(e)}")

    @staticmethod
    def get_video_timestamps(url: str, languages: Optional[List[str]] = None) -> List[str]:
        """Generate timestamps for a YouTube video based on captions."""
        if not url:
            raise HTTPException(status_code=400, detail="No URL provided")

        try:
            video_id = YouTubeTools.get_youtube_video_id(url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        except Exception:
            raise HTTPException(status_code=400, detail="Error getting video ID from URL")

        try:
            captions = YouTubeTranscriptApi.get_transcript(video_id, languages=languages or ["en"])
            timestamps = []
            for line in captions:
                start = int(line["start"])
                minutes, seconds = divmod(start, 60)
                timestamps.append(f"{minutes}:{seconds:02d} - {line['text']}")
            return timestamps
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating timestamps: {str(e)}")

    @staticmethod
    def get_video_captions_markdown(video_id: str, languages: Optional[List[str]] = None) -> str:
        """Get captions from a YouTube video and format as markdown."""
        if not video_id:
            raise HTTPException(status_code=400, detail="No video ID provided")

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            video_data = YouTubeTools.get_video_data(url)
            
            captions = None
            try:
                if languages:
                    captions = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
                else:
                    captions = YouTubeTranscriptApi.get_transcript(video_id)
            except Exception as e:
                return f"# {video_data.get('title', 'YouTube Video')}\n\nNo captions available for this video.\n\n🔗 [Watch on YouTube]({url})"
            
            if not captions:
                return f"# {video_data.get('title', 'YouTube Video')}\n\nNo captions found for this video.\n\n🔗 [Watch on YouTube]({url})"
            
            # Create markdown output
            markdown = f"# {video_data.get('title', 'YouTube Video')}\n\n"
            markdown += f"By: {video_data.get('author_name', 'Unknown')}\n\n"
            markdown += f"🔗 [Watch on YouTube]({url})\n\n"
            markdown += "## Transcript\n\n"
            
            # Merge all captions into a single text block instead of timestamp sections
            full_text = " ".join([line['text'] for line in captions])
            markdown += full_text
            
            return markdown
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting captions for video: {str(e)}")

class YouTubeRequest(BaseModel):
    url: str
    languages: Optional[List[str]] = None

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/video-data")
async def get_video_data(request: YouTubeRequest):
    """Endpoint to get video metadata"""
    return YouTubeTools.get_video_data(request.url)

@app.post("/video-captions")
async def get_video_captions(request: YouTubeRequest):
    """Endpoint to get video captions"""
    return YouTubeTools.get_video_captions(request.url, request.languages)

@app.post("/video-timestamps")
async def get_video_timestamps(request: YouTubeRequest):
    """Endpoint to get video timestamps"""
    return YouTubeTools.get_video_timestamps(request.url, request.languages)

@app.get("/widgets.json")
async def get_widgets():
    """Endpoint to get available widgets for OpenBB integration"""
    widgets = {
        "youtube_captions": {
            "name": "YouTube Captions",
            "description": "Get timestamped transcript from a YouTube video",
            "type": "markdown",
            "endpoint": "/youtube/captions",
            "params": [
                {
                    "paramName": "videoId",
                    "description": "YouTube video ID to get captions from",
                    "value": "",
                    "label": "Video ID",
                    "type": "text",
                },
            ],
        }
    }
    return JSONResponse(content=widgets)

@app.get("/youtube/captions")
async def get_youtube_captions(videoId: str):
    """Endpoint to get YouTube captions in markdown format for OpenBB integration"""
    try:
        markdown_content = YouTubeTools.get_video_captions_markdown(videoId)
        return PlainTextResponse(content=markdown_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

if __name__ == "__main__":
    # Use environment variable for port, default to 8000 if not set
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)