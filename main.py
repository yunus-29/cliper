from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import tempfile
import base64
from google import genai
from google.genai import types

app = FastAPI(title="YClip Backend API")

# CORS for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDAVtl798KG0KrRBts1-MQludiXB9zmiqU")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

class AnalyzeRequest(BaseModel):
    video_url: Optional[str] = None
    video_base64: Optional[str] = None

class ClipResponse(BaseModel):
    start: str
    end: str
    description: str

class AnalyzeResponse(BaseModel):
    clips: List[ClipResponse]

PROMPT = """
You are a ruthless TikTok-first short-form clip editor.
Your sole objective is to maximize STOP-SCROLL impact, retention, and rewatch potential,
while maintaining clean editorial cuts.

You think in SECONDS, not minutes.
You prioritize the FIRST 1–3 SECONDS above everything else.

Analyze the entire long-form video and extract ONLY moments that can be transformed
into high-performing TikTok clips.

========================
PRIMARY SELECTION CRITERIA (NON-NEGOTIABLE)
========================
Select ONLY moments that contain at least ONE of the following:

1. Bold, polarizing, or uncomfortable opinions
2. Statements that directly contradict common beliefs
3. Emotional spikes (anger, frustration, passion, shock, vulnerability)
4. Clear conflict (speaker vs belief, system, audience, or social norm)
5. Insights that make the listener rethink something familiar

If a moment is "interesting" but not disruptive, DO NOT select it.

========================
STOP-SCROLL OPENING REQUIREMENT (MANDATORY)
========================
Each selected clip MUST include a sentence that can function as a
STRONG OPENING HOOK within the first 1–3 seconds.

A valid hook MUST:
- Be understandable instantly without context
- Sound like a conclusion, not an introduction
- Trigger curiosity, tension, or emotional reaction immediately
- Make the viewer feel slightly attacked, challenged, or exposed

If a moment lacks a hook that can stop scrolling,
DO NOT select it — even if the insight is good.

========================
DISQUALIFY IMMEDIATELY
========================
Reject any moment that includes:
- Explanations, definitions, or teaching-style delivery
- Safe, polite, or neutral language
- Long setup before the point
- Rambling or filler speech
- Content that requires background knowledge

========================
CRITICAL EDITING CONSTRAINTS (ABSOLUTE RULES)
========================
- NEVER cut mid-sentence, mid-thought, or mid-word
- End timestamps MUST fall on a natural pause or completed sentence
- If the emotional peak happens mid-sentence, EXTEND the clip until the thought ends
- Prefer ending 1–3 seconds AFTER the punchline
- If unsure, OVER-EXTEND rather than under-cut
- Assume clips may be used WITHOUT captions — audio clarity is mandatory

========================
CLIP RULES
========================
- Select 3–7 clips ONLY (quality over quantity)
- Each clip must stand alone with zero external context
- Duration per clip: 15–45 seconds (ideal for TikTok retention)
- Timestamps must be precise (HH:MM:SS)

========================
OUTPUT FORMAT (STRICT)
========================
Return ONLY valid JSON.
No explanations, no markdown, no extra text.

Use this structure EXACTLY:

{
  "clips": [
    {
      "start": "HH:MM:SS",
      "end": "HH:MM:SS",
      "description": "Why this moment stops scrolling and which psychological trigger it hits"
    }
  ]
}
"""

@app.get("/")
def read_root():
    return {"status": "YClip Backend API is running", "version": "1.0"}

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_video(request: AnalyzeRequest):
    """Analyze video using Gemini SDK"""
    try:
        content_part = None
        
        # Use YouTube URL if provided (faster, no upload)
        if request.video_url:
            print(f"Using YouTube URL: {request.video_url}")
            content_part = types.Part.from_uri(
                file_uri=request.video_url, 
                mime_type="video/mp4"
            )
        
        # Upload video file if provided
        elif request.video_base64:
            print("Uploading video file...")
            # Decode base64
            video_bytes = base64.b64decode(request.video_base64)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name
            
            try:
                # Upload using SDK
                video_file = gemini_client.files.upload(path=tmp_path)
                
                # Wait for processing
                while video_file.state.name == "PROCESSING":
                    print("Processing video...")
                    import time
                    time.sleep(2)
                    video_file = gemini_client.files.get(name=video_file.name)
                
                if video_file.state.name == "FAILED":
                    raise HTTPException(status_code=500, detail="Video processing failed")
                
                content_part = types.Part.from_uri(
                    file_uri=video_file.uri,
                    mime_type=video_file.mime_type
                )
                
                # Cleanup temp file
                os.unlink(tmp_path)
                
                # Delete uploaded file after analysis
                try:
                    gemini_client.files.delete(name=video_file.name)
                except:
                    pass
                    
            except Exception as e:
                # Cleanup temp file on error
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise e
        
        else:
            raise HTTPException(status_code=400, detail="Either video_url or video_base64 required")
        
        # Generate analysis
        print("Generating AI analysis...")
        response = gemini_client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=[content_part, PROMPT],
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json",
                system_instruction="You are a professional video editor agent. Your job is to analyze video content and identify viral-worthy moments."
            )
        )
        
        # Parse response
        import json
        text = response.text
        # Clean JSON
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        if isinstance(data, dict) and "clips" in data:
            return AnalyzeResponse(clips=data["clips"])
        elif isinstance(data, list):
            return AnalyzeResponse(clips=data)
        else:
            return AnalyzeResponse(clips=[])
            
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
