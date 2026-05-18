import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import os
import shutil
import json
import base64
from pydub import AudioSegment
from jinja2 import Template
import urllib3
import webbrowser
import ssl

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# --- [경로 설정] ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = "assets"
CONFIG_FILE = os.path.join(BASE_DIR, "spotify_config.json")
FIREBASE_DIR = os.path.join(BASE_DIR, "firebase_deploy")

# --- [유틸리티] ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f: return json.load(f)
        except: pass
    return {}

def save_config(data):
    try:
        with open(CONFIG_FILE, "w") as f: json.dump(data, f)
    except Exception as e: print(f"Config saving error: {e}")

def get_spotify_token(client_id, client_secret):
    auth_string = f"{client_id}:{client_secret}"
    auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
    url = "https://accounts.spotify.com/api/token"
    headers = {"Authorization": "Basic " + auth_base64, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}
    res = requests.post(url, headers=headers, data=data, verify=False)
    return res.json().get("access_token")

def search_spotify_track(query, token):
    query_encoded = requests.utils.quote(query)
    url = f"https://api.spotify.com/v1/search?q={query_encoded}&type=track&limit=1"
    headers = {"Authorization": "Bearer " + token}
    res = requests.get(url, headers=headers, verify=False)
    items = res.json().get("tracks", {}).get("items", [])
    return items[0] if items else None

def process_audio(input_mp3_path, song_id):
    try:
        assets_path = os.path.join(OUTPUT_DIR, ASSETS_DIR)
        os.makedirs(assets_path, exist_ok=True)
        audio = AudioSegment.from_mp3(input_mp3_path)
        extract = audio[:30000].fade_in(2000).fade_out(2000)
        output_filename = f"preview_{song_id}.mp3"
        output_full_path = os.path.join(assets_path, output_filename)
        extract.export(output_full_path, format="mp3")
        return f"{ASSETS_DIR}/{output_filename}"
    except Exception as e: raise Exception(f"Audio error: {e}")

# --- [GUI] ---
class SpotifyPromoterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Spotify Music Promoter 🟢")
        self.root.geometry("600x700")
        self.root.configure(bg="#121212")

        tk.Label(root, text="Spotify Pitch Generator", font=("Arial", 22, "bold"), bg="#121212", fg="#1DB954").pack(pady=20)
        
        form = tk.Frame(root, bg="#121212")
        form.pack(pady=10, padx=40, fill="x")

        # Inputs
        self.add_field(form, "Search Song:", "entry_search")
        tk.Button(form, text="🔍 Search Spotify", command=self.search_track, bg="#1DB954", fg="white", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=5)
        
        self.add_field(form, "Artist:", "entry_artist", row=1)
        self.add_field(form, "Title:", "entry_title", row=2)
        self.add_field(form, "Genre:", "entry_genre", row=3)
        self.entry_genre.insert(0, "Pop, Indie")
        
        self.add_field(form, "MP3 File:", "entry_mp3", row=4)
        tk.Button(form, text="📂", command=self.browse_mp3).grid(row=4, column=2)

        self.img_label = tk.Label(root, bg="#181818", width=20, height=10)
        self.img_label.pack(pady=10)
        
        self.btn_create = tk.Button(root, text="🚀 DEPLOY PITCH PAGE", command=self.deploy, bg="#1DB954", fg="white", font=("Arial", 14, "bold"), padx=30, pady=10)
        self.btn_create.pack(pady=20)
        
        self.status = tk.Label(root, text="Ready", bg="#121212", fg="#888")
        self.status.pack()

        self.track_data = None
        self.load_settings()

    def add_field(self, parent, label, var_name, row=0):
        tk.Label(parent, text=label, bg="#121212", fg="white").grid(row=row, column=0, sticky="w", pady=5)
        ent = ttk.Entry(parent, width=40)
        ent.grid(row=row, column=1, pady=5, padx=5)
        setattr(self, var_name, ent)

    def load_settings(self):
        config = load_config()
        try:
            from private_keys import SpotifyKeys
            default_id = SpotifyKeys.CLIENT_ID
            default_secret = SpotifyKeys.CLIENT_SECRET
        except ImportError:
            default_id = ""
            default_secret = ""
            
        self.client_id = config.get("client_id", default_id)
        self.client_secret = config.get("client_secret", default_secret)

    def browse_mp3(self):
        f = filedialog.askopenfilename(filetypes=[("MP3", "*.mp3")])
        if f: self.entry_mp3.delete(0, tk.END); self.entry_mp3.insert(0, f)

    def search_track(self):
        q = self.entry_search.get()
        if not q: return
        self.status.config(text="Searching...")
        threading.Thread(target=self._search_thread, args=(q,)).start()

    def _search_thread(self, q):
        try:
            token = get_spotify_token(self.client_id, self.client_secret)
            track = search_spotify_track(q, token)
            if track:
                self.track_data = track
                self.root.after(0, self.update_ui_with_track)
            else: self.root.after(0, lambda: messagebox.showwarning("Not Found", "곡을 찾을 수 없습니다."))
        except Exception as e: self.root.after(0, lambda: messagebox.showerror("API Error", str(e)))

    def update_ui_with_track(self):
        self.entry_artist.delete(0, tk.END); self.entry_artist.insert(0, self.track_data["artists"][0]["name"])
        self.entry_title.delete(0, tk.END); self.entry_title.insert(0, self.track_data["name"])
        cover_url = self.track_data["album"]["images"][0]["url"]
        res = requests.get(cover_url, verify=False)
        img = Image.open(BytesIO(res.content)).resize((150, 150))
        photo = ImageTk.PhotoImage(img)
        self.img_label.config(image=photo); self.img_label.image = photo
        self.status.config(text="Track loaded!")

    def deploy(self):
        if not self.track_data: messagebox.showwarning("Error", "먼저 노래를 검색해주세요."); return
        self.btn_create.config(state="disabled", text="Deploying...")
        threading.Thread(target=self._deploy_thread).start()

    def _deploy_thread(self):
        try:
            # Generate HTML
            artist = self.entry_artist.get()
            title = self.entry_title.get()
            track_id = self.track_data["id"]
            cover_url = self.track_data["album"]["images"][0]["url"]
            spotify_link = self.track_data["external_urls"]["spotify"]
            
            with open(os.path.join(TEMPLATE_DIR, "pitch_template.html"), "r", encoding="utf-8") as f:
                template = Template(f.read())
            
            html_content = template.render(
                artist_name=artist, track_title=title, cover_image=cover_url,
                genre=self.entry_genre.get(), spotify_track_id=track_id, spotify_link=spotify_link
            )
            
            public_dir = os.path.join(FIREBASE_DIR, "public")
            os.makedirs(public_dir, exist_ok=True)
            html_file = f"pitch_{track_id}.html"
            with open(os.path.join(public_dir, html_file), "w", encoding="utf-8") as f: f.write(html_content)
            with open(os.path.join(public_dir, "index.html"), "w", encoding="utf-8") as f: f.write(html_content)

            # Firebase Config
            with open(os.path.join(FIREBASE_DIR, "firebase.json"), "w") as f:
                json.dump({"hosting": {"public": "public"}}, f)
            with open(os.path.join(FIREBASE_DIR, ".firebaserc"), "w") as f:
                json.dump({"projects": {"default": "pitch-promo-xyz-0727"}}, f)

            import subprocess
            subprocess.run(["firebase.cmd", "deploy", "--only", "hosting"], cwd=FIREBASE_DIR, shell=True)
            
            url = f"https://pitch-promo-xyz-0727.web.app/{html_file}"
            self.root.after(0, lambda: self.finish_deploy(url))
        except Exception as e: self.root.after(0, lambda: self.error_deploy(str(e)))

    def finish_deploy(self, url):
        self.btn_create.config(state="normal", text="🚀 DEPLOY PITCH PAGE")
        messagebox.showinfo("Success", f"Deployed to:\n{url}")
        webbrowser.open(url)

    def error_deploy(self, err):
        self.btn_create.config(state="normal", text="🚀 DEPLOY PITCH PAGE")
        messagebox.showerror("Deploy Error", err)

if __name__ == "__main__":
    root = tk.Tk()
    app = SpotifyPromoterApp(root)
    root.mainloop()
