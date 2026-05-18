import os
import sys
import io
import json
import asyncio
import time
import re
import requests
import shutil
import threading
import socket
import ssl
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from fastapi.staticfiles import StaticFiles
import firebase_admin
from firebase_admin import credentials, firestore

if sys.platform == "win32":
    try:
        sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='utf-8', errors='ignore', line_buffering=True)
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='ignore', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='ignore', line_buffering=True)
    except:
        pass

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_CORE_DIR = os.path.join(BASE_DIR, "python_core_engine")
sys.path.append(PYTHON_CORE_DIR)

from EmailScraper import SpotifyEmailScraper

app = FastAPI(title="Spotify Promoter Bridge API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase Init
# Ensure you have the service account key or use default credentials if on local with firebase login
# For this environment, we'll try to find any existing service account or use the project ID directly
db = None
try:
    if not firebase_admin._apps:
        cred_path = os.path.join(BASE_DIR, "backend", "serviceAccountKey.json")
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            print("Found serviceAccountKey.json! Authenticating...")
        else:
            cred = credentials.ApplicationDefault()
            print("Trying Application Default Credentials...")
        
        firebase_admin.initialize_app(cred, {
            'projectId': 'pitch-promo-xyz-0727',
        })
    db = firestore.client()
    print("Firebase Admin Initialized for pitch-promo-xyz-0727")
except Exception as e:
    print(f"Firebase Init Error: {e}. Please place 'serviceAccountKey.json' in backend folder.")

CONFIG_PATH = os.path.join(PYTHON_CORE_DIR, "spotify_config.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PITCH_DIR = os.path.join(BASE_DIR, "pitch_pages")
FIREBASE_PUBLIC_DIR = os.path.join(BASE_DIR, "public")
FIREBASE_PUBLIC_HOST = "https://pitch-promo-xyz-0727.web.app"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PITCH_DIR, exist_ok=True)
os.makedirs(FIREBASE_PUBLIC_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/pitch_pages", StaticFiles(directory=PITCH_DIR), name="pitch_pages")

TEMPLATE_DIR = os.path.join(PYTHON_CORE_DIR, "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

API_BASE_URL = "http://127.0.0.1:8000"

class SpotifyCampaignConfig(BaseModel):
    artist_name: str
    track_title: str
    spotify_url: str
    genres: List[str]
    max_curators: int = 30
    album_art: Optional[str] = None

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/api/search-spotify")
async def search_spotify(query: str):
    config = load_config()
    cid = config.get("client_id")
    secret = config.get("client_secret")
    
    if not cid or not secret:
        raise HTTPException(status_code=400, detail="Spotify API keys missing")
        
    scraper = SpotifyEmailScraper(client_id=cid, client_secret=secret)
    if not scraper.authenticate():
        raise HTTPException(status_code=401, detail="Spotify Auth Failed")
        
    headers = {'Authorization': f'Bearer {scraper.access_token}'}
    # Bypass SSL for restricted environment
    res = requests.get(
        f"https://api.spotify.com/v1/search?q={requests.utils.quote(query)}&type=track&limit=10",
        headers=headers,
        verify=False
    )
    
    if res.status_code == 200:
        data = res.json()
        tracks = []
        for t in data.get("tracks", {}).get("items", []):
            tracks.append({
                "id": t.get("id"),
                "name": t.get("name"),
                "artist": ", ".join([a.get("name") for a in t.get("artists", [])]),
                "image": t.get("album", {}).get("images", [{}])[0].get("url"),
                "url": t.get("external_urls", {}).get("spotify")
            })
        return tracks
    raise HTTPException(status_code=res.status_code, detail="Search failed")

def run_spotify_task(doc_id: str, data: dict):
    try:
        db.collection('promo_tasks_spotify').document(doc_id).update({"status": "processing", "log": "세션 인증 중..."})
        
        config_data = load_config()
        scraper = SpotifyEmailScraper(
            client_id=config_data.get("client_id"),
            client_secret=config_data.get("client_secret")
        )
        
        def update_log(msg):
            print(f"[{doc_id}] {msg}")
            db.collection('promo_tasks_spotify').document(doc_id).update({
                "log": msg,
                "logs": firestore.ArrayUnion([f"[{time.strftime('%H:%M:%S')}] {msg}"])
            })

        update_log(f"큐레이터 검색 시작: {', '.join(data.get('genres', []))}")
        results = scraper.scrape_emails(", ".join(data.get("genres", [])), max_count=data.get("max_curators", 30), progress_callback=update_log)
        
        # Pitch Page Generation
        update_log("피치 페이지 생성 중...")
        pitch_data = generate_pitch_logic(data)
        
        db.collection('promo_tasks_spotify').document(doc_id).update({
            "status": "completed",
            "results": results,
            "pitch_page_url": pitch_data["public_url"],
            "log": "캠페인 준비 완료!"
        })
        
    except Exception as e:
        print(f"Task Error: {e}")
        db.collection('promo_tasks_spotify').document(doc_id).update({"status": "error", "log": str(e)})

def generate_pitch_logic(data: dict):
    # This is a simplified version of the logic in the original main.py adapted for Spotify
    try:
        template_path = os.path.join(TEMPLATE_DIR, "pitch_template.html")
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found at {template_path}")
            
        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()
            
        from jinja2 import Template
        template = Template(template_str)
        
        render_data = {
            "track_title": data.get("track_title"),
            "artist_name": data.get("artist_name"),
            "cover_image": data.get("album_art") or "https://via.placeholder.com/500",
            "spotify_url": data.get("spotify_url"),
            "genre": ", ".join(data.get("genres", [])),
        }
        
        html_content = template.render(**render_data)
        filename = f"pitch_spotify_{int(time.time())}.html"
        
        # Save for Firebase Hosting
        firebase_file_path = os.path.join(FIREBASE_PUBLIC_DIR, filename)
        with open(firebase_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # Trigger Firebase Deploy (simplified: just assume it will be deployed next time or use firebase-tools)
        # In a real scenario, we might run 'firebase deploy --only hosting' here
        
        return {
            "public_url": f"{FIREBASE_PUBLIC_HOST}/{filename}",
            "filename": filename
        }
    except Exception as e:
        print(f"Pitch Logic Error: {e}")
        raise e

async def firestore_listener():
    """Listen for new tasks in Firestore"""
    print("Firestore Listener Started...")
    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                doc = change.document
                data = doc.to_dict()
                if data.get('status') == 'pending':
                    task_type = data.get('type')
                    if task_type == 'search-spotify':
                        # Handle search task
                        print(f"Search task received: {data.get('query')}")
                        threading.Thread(target=lambda id=doc.id, d=data: asyncio.run(handle_search_task(id, d)), daemon=True).start()
                    elif task_type == 'start-campaign-spotify':
                        # Handle campaign task
                        print(f"Campaign task received: {data.get('track_title')}")
                        threading.Thread(target=run_spotify_task, args=(doc.id, data), daemon=True).start()

    if db:
        col_query = db.collection('promo_tasks_spotify').where('status', '==', 'pending')
        col_query.on_snapshot(on_snapshot)
        
        # Keep listener alive
        while True:
            await asyncio.sleep(1)
    else:
        print("Firebase is not initialized. Firestore listener cannot start.")

async def handle_search_task(doc_id: str, data: dict):
    try:
        query_str = data.get('query')
        results = await search_spotify(query_str)
        db.collection('promo_tasks_spotify').document(doc_id).update({
            "status": "completed",
            "results": results
        })
    except Exception as e:
        db.collection('promo_tasks_spotify').document(doc_id).update({
            "status": "error",
            "log": str(e)
        })

if __name__ == "__main__":
    import uvicorn
    # Start Firestore listener in background
    threading.Thread(target=lambda: asyncio.run(firestore_listener()), daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
