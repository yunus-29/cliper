# YClip Backend API

FastAPI backend for YClip mobile app using Python Gemini SDK.

## Features
- Video upload and analysis using Gemini SDK
- Same quota management as desktop app
- Railway deployment ready

## Endpoints

### POST /api/analyze
Analyze video and return viral clips.

**Request:**
```json
{
  "video_url": "https://youtube.com/watch?v=...",  // Optional
  "video_file": "base64_encoded_video"  // Optional
}
```

**Response:**
```json
{
  "clips": [
    {
      "start": "00:01:23",
      "end": "00:01:45",
      "description": "Why this moment stops scrolling..."
    }
  ]
}
```

## Deployment

### Railway
1. Connect GitHub repo
2. Set environment variable: `GEMINI_API_KEY`
3. Deploy automatically

### Local Development
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
