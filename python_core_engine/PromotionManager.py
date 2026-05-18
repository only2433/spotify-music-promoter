import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import os
import shutil
import json
from pydub import AudioSegment
from jinja2 import Template
import urllib3
import webbrowser
from EmailScraper import SpotifyEmailScraper

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [경로 설정] ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = "assets"
TEMPLATE_FILE = "pitch_template.html"
CONFIG_FILE = os.path.join(BASE_DIR, "spotify_config.json")

# --- [FFmpeg 경로] ---
ffmpeg_path = os.path.join(BASE_DIR, "ffmpeg.exe")
ffprobe_path = os.path.join(BASE_DIR, "ffprobe.exe")

if os.path.exists(ffmpeg_path):
    print(f"🔧 FFmpeg 경로 설정: {ffmpeg_path}")
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffmpeg = ffmpeg_path
    AudioSegment.ffprobe = ffprobe_path
    os.environ["PATH"] += os.pathsep + BASE_DIR
else:
    print("⚠️ FFmpeg가 발견되지 않았습니다. install_ffmpeg.py를 먼저 실행해주세요.")

# --- [유틸리티] ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Config saving error: {e}")

def get_spotify_cover_image(spotify_url):
    if not spotify_url.startswith("http"):
        spotify_url = "https://" + spotify_url
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(spotify_url, headers=headers, verify=False)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        og_image = soup.find("meta", property="og:image")
        return og_image["content"] if og_image else None
    except Exception as e:
        print(f"이미지 추출 실패: {e}")
        return None

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
    except Exception as e:
        raise Exception(f"오디오 처리 중 오류 발생: {e}")

# --- [GUI 클래스] ---
class EmailPreviewWindow:
    def __init__(self, parent, collected_data, html_path, artist, title, cover_url, genre):
        self.window = tk.Toplevel(parent)
        self.window.title("📧 Campaign Preview")
        self.window.geometry("900x600")
        self.window.configure(bg="#f5f5f5")
        self.html_path = html_path
        self.artist = artist
        self.title = title
        self.cover_url = cover_url
        self.genre = genre
        self.public_url = None
        
        tk.Label(self.window, text=f"Collected {len(collected_data)} Curators", font=("Arial", 16, "bold"), bg="#f5f5f5").pack(pady=15)
        
        main_frame = tk.Frame(self.window, bg="#f5f5f5")
        main_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        left_frame = tk.LabelFrame(main_frame, text="Curator List", bg="#f5f5f5")
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        columns = ("status", "email", "source")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings")
        self.tree.heading("status", text="St.")
        self.tree.heading("email", text="Email")
        self.tree.heading("source", text="Playlist Source")
        self.tree.column("status", width=35, anchor="center")
        self.tree.column("email", width=200)
        self.tree.column("source", width=150)
        
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        for item in collected_data:
            status = "✅" if item.get('verified') else "⚠️"
            self.tree.insert("", "end", values=(status, item['email'], item['source']))
            
        right_frame = tk.LabelFrame(main_frame, text="Email Draft", bg="#f5f5f5")
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        
        tk.Label(right_frame, text="Subject:", bg="#f5f5f5").pack(anchor="w", padx=10, pady=(10, 0))
        self.entry_subject = tk.Entry(right_frame, width=40)
        self.entry_subject.insert(0, f"Submission: Fresh sounds from {self.artist} - \"{self.title}\"")
        self.entry_subject.pack(fill="x", padx=10, pady=5)
        
        tk.Label(right_frame, text="Message:", bg="#f5f5f5").pack(anchor="w", padx=10)
        self.text_msg = tk.Text(right_frame, height=10, width=40, font=("Arial", 10))
        email_body = (
            "Hi there,\n\n"
            f"I love your playlist curations and wanted to submit my track \"{self.title}\" for your consideration.\n\n"
            "This song has a really unique vibe that I think your listeners will absolutely love. It brings fresh energy and I'd be honored to have it on your radar."
            "\n\n▶ Please check the ATTACHED HTML file to listen to the preview.\n"
            "(Simply download and open it in your browser - no internet needed!)\n\n"
            f"Best,\n{self.artist}"
        )
        self.text_msg.insert("1.0", email_body)
        self.text_msg.pack(fill="both", expand=True, padx=10, pady=5)
        
        btn_frame = tk.Frame(self.window, bg="#f5f5f5")
        btn_frame.pack(fill="x", pady=20)
        
        tk.Button(btn_frame, text="👁️ View Pitch Page", command=self.open_html, bg="#333", fg="white").pack(side="left", padx=20)
        
        right_btn_frame = tk.Frame(btn_frame, bg="#f5f5f5")
        right_btn_frame.pack(side="right", padx=20)
        
        tk.Button(right_btn_frame, text="📋 Copy Emails", command=self.copy_emails, bg="#008080", fg="white").pack(side="left", padx=5)
        tk.Button(right_btn_frame, text="📝 Copy Message", command=self.copy_message, bg="#008080", fg="white").pack(side="left", padx=5)
        self.btn_surge = tk.Button(right_btn_frame, text="🌍 Get Web Link", command=self.deploy_to_surge, bg="#4169E1", fg="white")
        self.btn_surge.pack(side="left", padx=5)
        
        self.btn_html_email = tk.Button(right_btn_frame, text="🎨 Create HTML Email", command=self.generate_html_email, bg="#FF5722", fg="white", state="disabled")
        self.btn_html_email.pack(side="left", padx=5)

        tk.Button(right_btn_frame, text="🚀 Send Auto Emails", command=self.send_emails, bg="#1DB954", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=5)

        self.progress = ttk.Progressbar(self.window, mode='indeterminate')
        self.lbl_deploy_status = tk.Label(self.window, text="", bg="#f5f5f5", fg="#4169E1")

    def deploy_to_surge(self):
        import random, string
        self.btn_surge.config(state="disabled", text="Deploying...")
        self.progress.pack(fill="x", padx=20, pady=(0, 10))
        self.progress.start(10)
        self.lbl_deploy_status.pack(pady=(0, 5))
        self.lbl_deploy_status.config(text="무료 웹사이트 생성 중... (최대 30초 소요)")
        
    def deploy_to_surge(self):
        import random, string
        
        # We will use firebase instead of surge to guarantee mobile support.
        # Load saved domain if exists to maintain consistency
        config = load_config()
        saved_domain = config.get("surge_domain")
        
        if saved_domain:
            domain = saved_domain
            print(f"Reuse domain: {domain}")
        else:
            rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            domain = f"pitch_{rand_str}.html"

        self.btn_surge.config(state="disabled", text="Deploying...")
        self.progress.pack(fill="x", padx=20, pady=(0, 10))
        self.progress.start(10)
        self.lbl_deploy_status.pack(pady=(0, 5))
        self.lbl_deploy_status.config(text="구글 서버에 웹페이지 생성 중... (최대 60초)")
        
        threading.Thread(target=self._deploy_thread, args=(domain,), daemon=True).start()

    def _deploy_thread(self, html_filename):
        try:
            import subprocess
            import time
            import json
            
            # Setup Firebase Directory
            firebase_dir = os.path.join(BASE_DIR, "firebase_deploy")
            public_dir = os.path.join(firebase_dir, "public")
            os.makedirs(public_dir, exist_ok=True)
            
            fb_json_path = os.path.join(firebase_dir, "firebase.json")
            if not os.path.exists(fb_json_path):
                with open(fb_json_path, "w", encoding="utf-8") as f:
                    json.dump({"hosting": {"public": "public", "ignore": ["firebase.json", "**/.*", "**/node_modules/**"]}}, f)
            
            fb_rc_path = os.path.join(firebase_dir, ".firebaserc")
            if not os.path.exists(fb_rc_path):
                with open(fb_rc_path, "w", encoding="utf-8") as f:
                    json.dump({"projects": {"default": "pitch-promo-xyz-1234"}}, f)

            # Clean and Copy
            for f in os.listdir(public_dir):
                if f.endswith('.html'):
                    try: os.remove(os.path.join(public_dir, f))
                    except: pass

            shutil.copy(self.html_path, os.path.join(public_dir, html_filename))
            shutil.copy(self.html_path, os.path.join(public_dir, "index.html"))

            cmd = ["firebase.cmd", "deploy", "--only", "hosting"]
            
            # 1. Attempt Deployment
            process = subprocess.run(cmd, cwd=firebase_dir, capture_output=True, text=True, encoding='utf-8')
            combined_log = (process.stdout or "") + (process.stderr or "")
            with open("deploy_debug.log", "w", encoding="utf-8") as _f:
                _f.write(combined_log)
            
            if "completed" in combined_log or "complete!" in combined_log:
                public_url = f"https://pitch-promo-xyz-1234.web.app/{html_filename}"
                
                # 2. Verify Deployment (Health Check)
                success_check = False
                for i in range(10):
                    try:
                        time.sleep(3) # Wait for propagation
                        check = requests.get(public_url, timeout=5, verify=False)
                        if check.status_code == 200:
                            success_check = True
                            break
                    except:
                        pass
                
                # Save successful domain since deploy confirmed success
                config = load_config()
                config["surge_domain"] = html_filename
                save_config(config)
                
                self.public_url = public_url
                
                if success_check:
                    self.window.after(0, lambda: self._deploy_finished(True, public_url, None))
                else:
                    self.window.after(0, lambda: self._deploy_finished(True, public_url, "Deployment success, but site verification is taking longer than usual. The link might take a minute to work!"))
            else:
                self.window.after(0, lambda: self._deploy_finished(False, None, combined_log))
                
        except subprocess.TimeoutExpired:
             self.window.after(0, lambda: self._deploy_finished(False, None, "Timeout"))
        except Exception as e:
            self.window.after(0, lambda: self._deploy_finished(False, None, str(e)))

    def _deploy_finished(self, success, public_url, error_msg):
        self.progress.stop()
        self.progress.pack_forget()
        self.lbl_deploy_status.pack_forget()
        self.btn_surge.config(state="normal", text="🌍 Get Web Link")
        
        if success:
            current_body = self.text_msg.get("1.0", tk.END).strip()
            self.text_msg.delete("1.0", tk.END)
            self.text_msg.insert("1.0", f"{current_body}\n\n[Live Link]: {public_url}")
            
            msg_title = "Success"
            msg_body = f"Deployed: {public_url}"
            if error_msg:
                msg_body += f"\n\nNote: {error_msg}"
                
            messagebox.showinfo(msg_title, msg_body)
            self.window.clipboard_clear()
            self.window.clipboard_append(public_url)
            self.btn_html_email.config(state="normal")
        else:
            messagebox.showerror("Failed", f"Deployment failed: {error_msg}")

    def open_html(self):
        webbrowser.open(f"file://{os.path.abspath(self.html_path)}")

    def copy_emails(self):
        emails = [self.tree.item(child)['values'][1] for child in self.tree.get_children()]
        if emails:
            self.window.clipboard_clear()
            self.window.clipboard_append(", ".join(emails))
            messagebox.showinfo("Copied", f"Copied {len(emails)} emails!")

    def copy_message(self):
        subject = self.entry_subject.get()
        body = self.text_msg.get("1.0", tk.END)
        self.window.clipboard_clear()
        self.window.clipboard_append(f"Subject: {subject}\n\n{body}")
        messagebox.showinfo("Copied", "Subject and body copied.")

    def send_emails(self):
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import time

        # 1. Get SMTP Configuration
        config = load_config()
        smtp_host = config.get("smtp_host", "smtp.gmail.com")
        smtp_port = config.get("smtp_port", "587")
        sender_email = config.get("sender_email")
        app_password = config.get("app_password")

        print(f"\n--- [Email Sending Debug] ---")
        print(f"Host: {smtp_host}, Port: {smtp_port}")
        print(f"Sender: {sender_email}")

        if not (sender_email and app_password):
            messagebox.showerror("SMTP Error", "메인 화면에서 이메일 발신 설정을 먼저 완료해주세요.\n(SMTP Host, Port, Email, App Password)")
            return

        emails = [self.tree.item(child)['values'][1] for child in self.tree.get_children()]
        if not emails:
            messagebox.showwarning("No Emails", "전송할 이메일 리스트가 비어있습니다.")
            return

        # 2. Ask for Email Type
        choice = messagebox.askyesnocancel("Choose Email Type", 
                                          "어떤 형식으로 전송하시겠습니까?\n\n"
                                          "Yes: '텍스트 전송' (Draft 창 내용)\n"
                                          "No: 'HTML 디자인 전송' (템플릿 적용)\n"
                                          "Cancel: 취소")
        
        if choice is None: return # Cancelled
        
        subject = self.entry_subject.get()
        text_body = self.text_msg.get("1.0", tk.END).strip()
        
        # HTML Content if needed
        html_body = None
        if choice is False: # HTML Design
            if not self.public_url:
                messagebox.showwarning("Link Required", "HTML 전송을 위해서는 반드시 'Get Web Link'를 먼저 실행해야 합니다.")
                return
            try:
                template_path = os.path.join(TEMPLATE_DIR, "email_template.html")
                with open(template_path, "r", encoding="utf-8") as f:
                    template_str = f.read()
                template = Template(template_str)
                html_body = template.render(
                    artist_name=self.artist,
                    track_title=self.title,
                    cover_image=self.cover_url,
                    genre=self.genre,
                    pitch_url=self.public_url
                )
            except Exception as e:
                messagebox.showerror("Template Error", f"HTML 템플릿 처리 중 오류: {e}")
                return

        # 3. Start Sending Thread
        self.window.attributes('-disabled', True) 
        self.progress.pack(fill="x", padx=20, pady=10)
        self.progress.start(10)
        
        def _send_thread():
            import ssl
            success_count = 0
            fail_count = 0
            log_messages = []
            context = ssl.create_default_context()
            
            try:
                print(f"Step 1: Connecting to server {smtp_host} (Port: {smtp_port})...")
                self.window.after(0, lambda: self.lbl_deploy_status.config(text=f"Connecting to {smtp_host}..."))
                self.window.after(0, lambda: self.lbl_deploy_status.pack())

                # Use explicit SSL context for modern security
                if smtp_port == "465":
                    server = smtplib.SMTP_SSL(smtp_host, int(smtp_port), timeout=20, context=context)
                else:
                    server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=20)
                    print(f"Step 2: Starting TLS...")
                    server.starttls(context=context)
                
                print(f"Step 3: Attempting Login as {sender_email}...")
                self.window.after(0, lambda: self.lbl_deploy_status.config(text="Logging in..."))
                server.login(sender_email, app_password)
                print(f"Login Success!")
                
                for i, target_email in enumerate(emails):
                    try:
                        print(f"[{i+1}/{len(emails)}] Sending to: {target_email}...")
                        self.window.after(0, lambda m=f"Sending to ({i+1}/{len(emails)}): {target_email}": self.lbl_deploy_status.config(text=m))
                        
                        msg = MIMEMultipart("alternative")
                        msg["From"] = sender_email
                        msg["To"] = target_email
                        msg["Subject"] = subject
                        
                        msg.attach(MIMEText(text_body, "plain"))
                        if html_body:
                            msg.attach(MIMEText(html_body, "html"))
                        
                        server.send_message(msg)
                        success_count += 1
                        time.sleep(1.5)
                    except Exception as e:
                        print(f"Error sending to {target_email}: {e}")
                        fail_count += 1
                        log_messages.append(f"Failed {target_email}: {e}")
                
                server.quit()
                print(f"Done! Success: {success_count}, Fail: {fail_count}")
                
                summary = f"전송 완료!\n\n성공: {success_count}\n실패: {fail_count}"
                if log_messages:
                    summary += "\n\n오류 내역:\n" + "\n".join(log_messages[:5])
                
                self.window.after(0, lambda: self._send_finished(summary))
                
            except Exception as e:
                err_msg = str(e)
                print(f"CRITICAL SMTP ERROR: {err_msg}")
                friendly_msg = f"SMTP Server Connection Failed:\n{err_msg}\n\n"
                if "10061" in err_msg:
                    friendly_msg += "💡 해결 팁:\n1. 백신(V3, 알약 등)의 '메일 감시' 기능을 끄고 시도해 보세요.\n2. 회사/카페 와이파이 대신 '선없는 테더링(핫스팟)'을 써보세요.\n3. 포트를 465와 587 중 다른 것으로 바꿔보세요."
                
                self.window.after(0, lambda: self._send_finished(friendly_msg))

        threading.Thread(target=_send_thread, daemon=True).start()

    def _send_finished(self, message):
        self.window.attributes('-disabled', False)
        self.progress.stop()
        self.progress.pack_forget()
        self.lbl_deploy_status.pack_forget()
        messagebox.showinfo("Email Result", message)

    def generate_html_email(self):
        if not self.public_url:
            messagebox.showwarning("Link Required", "Please deploy to Surge first to get a public link.")
            return

        try:
            template_path = os.path.join(TEMPLATE_DIR, "email_template.html")
            if not os.path.exists(template_path):
                # Fallback simple template creation if missing
                 with open(template_path, "w", encoding="utf-8") as f:
                     f.write("<html><body><h1>{{ track_title }}</h1><a href='{{ pitch_url }}'>Listen</a></body></html>")

            with open(template_path, "r", encoding="utf-8") as f:
                template = Template(f.read())
            
            html_content = template.render(
                artist_name=self.artist,
                track_title=self.title,
                cover_image=self.cover_url,
                genre=self.genre,
                pitch_url=self.public_url
            )
            
            preview_file = os.path.join(OUTPUT_DIR, "email_preview.html")
            with open(preview_file, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            webbrowser.open(f"file://{os.path.abspath(preview_file)}")
            
            messagebox.showinfo("Email HTML Generated", 
                                "The HTML email design has been opened in your browser.\n\n"
                                "1. Click inside the browser window.\n"
                                "2. Press Ctrl+A (Select All).\n"
                                "3. Press Ctrl+C (Copy).\n"
                                "4. Paste (Ctrl+V) into your Gmail/Outlook body.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate email HTML: {str(e)}")

class PromotionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity Music Promoter 🎸 (Spotify API Mode)")
        self.root.geometry("600x750") # 높이 증가
        self.root.configure(bg="#f0f0f0")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        tk.Label(root, text="Music Pitch Page Generator", font=("Arial", 18, "bold"), bg="#f0f0f0", fg="#1DB954").pack(pady=15)
        
        form_frame = tk.Frame(root, bg="#f0f0f0")
        form_frame.pack(pady=5, padx=30, fill="x")
        
        # 1. Artist
        tk.Label(form_frame, text="Artist Name:", bg="#f0f0f0").grid(row=0, column=0, sticky="w", pady=5)
        self.entry_artist = ttk.Entry(form_frame, width=40)
        self.entry_artist.grid(row=0, column=1, pady=5)
        
        # 2. Song
        tk.Label(form_frame, text="Song Title:", bg="#f0f0f0").grid(row=1, column=0, sticky="w", pady=5)
        self.entry_song = ttk.Entry(form_frame, width=40)
        self.entry_song.grid(row=1, column=1, pady=5)
        
        # 3. Spotify Link
        tk.Label(form_frame, text="Spotify Link:", bg="#f0f0f0").grid(row=2, column=0, sticky="w", pady=5)
        self.entry_spotify = ttk.Entry(form_frame, width=30)
        self.entry_spotify.grid(row=2, column=1, sticky="w", pady=5)
        ttk.Button(form_frame, text="🔍 Check", command=self.manual_check_spotify, width=8).grid(row=2, column=1, sticky="e")
        
        # 4. MP3
        tk.Label(form_frame, text="MP3 File:", bg="#f0f0f0").grid(row=3, column=0, sticky="w", pady=5)
        self.entry_mp3 = ttk.Entry(form_frame, width=30)
        self.entry_mp3.grid(row=3, column=1, sticky="w", pady=5)
        ttk.Button(form_frame, text="📂 Find", command=self.browse_mp3, width=8).grid(row=3, column=1, sticky="e")
        
        # 5. Genres
        tk.Label(form_frame, text="Genres (Max 3):", bg="#f0f0f0").grid(row=4, column=0, sticky="nw", pady=5)
        
        genre_outer_frame = tk.Frame(form_frame, bg="#f0f0f0")
        genre_outer_frame.grid(row=4, column=1, sticky="w", pady=5)
        
        # Search Bar
        self.entry_genre_search = ttk.Entry(genre_outer_frame, width=35)
        self.entry_genre_search.pack(fill="x", pady=(0, 5))
        self.entry_genre_search.insert(0, "Search genres...")
        self.entry_genre_search.bind("<FocusIn>", lambda e: self.clear_genre_search())
        self.entry_genre_search.bind("<FocusOut>", self.restore_genre_search)
        self.entry_genre_search.bind("<KeyRelease>", self.filter_genres)

        genre_container = tk.Frame(genre_outer_frame, bg="#ffffff", bd=1, relief="solid")
        genre_container.pack(fill="both")
        
        self.genre_canvas = tk.Canvas(genre_container, bg="#ffffff", height=150, width=350)
        genre_scrollbar = ttk.Scrollbar(genre_container, orient="vertical", command=self.genre_canvas.yview)
        self.genre_inner_frame = tk.Frame(self.genre_canvas, bg="#ffffff")
        self.genre_inner_frame.bind("<Configure>", lambda e: self.genre_canvas.configure(scrollregion=self.genre_canvas.bbox("all")))
        self.genre_canvas.create_window((0, 0), window=self.genre_inner_frame, anchor="nw")
        self.genre_canvas.configure(yscrollcommand=genre_scrollbar.set)
        self.genre_canvas.pack(side="left", fill="both")
        genre_scrollbar.pack(side="right", fill="y")
        
        self.genre_vars = {}
        self.genre_widgets = []
        self.genres_list = [
            "Pop", "K-Pop", "Hip-Hop", "R&B", "Rock", "Indie", "Electronic", "House", "Lo-Fi", "Chill", 
            "Jazz", "Synth-Pop", "Trap", "Acoustic", "Afrobeat", "Alternative", "Ambient", "Anime", "Blues", 
            "Classical", "Country", "Dance", "Dancehall", "Deep House", "Disco", "Dubstep", "EDM", "Folk", 
            "Funk", "Gospel", "Grime", "Heavy Metal", "J-Pop", "Latin", "Lofi Hip Hop", "Metal", "Neo Soul", 
            "New Age", "Phonk", "Piano", "Punk", "Rap", "Reggae", "Reggaeton", "Salsa", "Ska", "Soul", "Techno", 
            "Trance", "Acapella", "Alternative Rock", "Bass", "Beats", "Bossa Nova", "Chillout", "Cinematic", 
            "Classical Crossover", "Contemporary", "Cyberpunk", "Darkwave", "Dream Pop", "Drum and Bass", 
            "Electro", "Emo", "Flamenco", "Future Bass", "Garage", "Hardstyle", "Indie Pop", "Indie Rock", 
            "Industrial", "Instrumental", "K-Indie", "K-R&B", "K-Rock", "K-Hip-Hop", "Latin Pop", "Mariachi", 
            "Melodic Techno", "Nu Disco", "Opera", "Orchestral", "Pop Punk", "Pop Rock", "Progressive House", 
            "Psytrance", "R&B/Soul", "Shoegaze", "Singer-Songwriter", "Smooth Jazz", "Symphonic", "Tech House", 
            "Tropical House", "Vaporwave", "Vocal", "World Music", "Afropop", "Bhangra", "Cumbia", "Merengue",
            "Bachata", "Tango", "Bossa", "City Pop", "Hyperpop", "Drill", "Boom Bap", "Alternative R&B",
            "Death Metal", "Black Metal", "Folk Rock", "Psychedelic Rock", "K-pop Girl Group", "K-pop Boy Group",
            "J-Rock", "Jazz Fusion", "Latin Jazz", "Bebop", "Lo-Fi Beats", "Breakcore", "Post-Punk",
            "Post-Rock", "Math Rock", "Screamo", "Britpop", "Chiptune", "Vocaloid", "J-Core", "Eurobeat"
        ]
        
        for genre in self.genres_list:
            self.genre_vars[genre] = tk.BooleanVar()
            
        self.populate_genres(self.genres_list)

        # --- Spotify API Credentials ---
        api_frame = tk.LabelFrame(root, text="Spotify API Keys (Required for Email Scraping)", bg="#f0f0f0", font=("Arial", 10, "bold"))
        api_frame.pack(pady=10, padx=30, fill="x")
        
        tk.Label(api_frame, text="Client ID:", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_client_id = ttk.Entry(api_frame, width=30, show="*")
        self.entry_client_id.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(api_frame, text="Client Secret:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_client_secret = ttk.Entry(api_frame, width=30, show="*")
        self.entry_client_secret.grid(row=0, column=3, padx=5, pady=5)

        # --- SMTP Settings (for automatic sending) ---
        smtp_frame = tk.LabelFrame(root, text="Email Sending (SMTP) Settings - Default: Gmail", bg="#f0f0f0", font=("Arial", 10, "bold"))
        smtp_frame.pack(pady=10, padx=30, fill="x")
        
        tk.Label(smtp_frame, text="SMTP Host:", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_smtp_host = ttk.Entry(smtp_frame, width=20)
        self.entry_smtp_host.grid(row=0, column=1, padx=5, pady=5)
        self.entry_smtp_host.insert(0, "smtp.gmail.com")

        tk.Label(smtp_frame, text="Port:", bg="#f0f0f0").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_smtp_port = ttk.Entry(smtp_frame, width=5)
        self.entry_smtp_port.grid(row=0, column=3, padx=5, pady=5)
        self.entry_smtp_port.insert(0, "587")

        tk.Label(smtp_frame, text="Your Email:", bg="#f0f0f0").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_sender_email = ttk.Entry(smtp_frame, width=25)
        self.entry_sender_email.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(smtp_frame, text="App Password:", bg="#f0f0f0").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entry_app_password = ttk.Entry(smtp_frame, width=20, show="*")
        self.entry_app_password.grid(row=1, column=3, padx=5, pady=5)

        tk.Button(smtp_frame, text="Save All Settings", command=self.save_all_settings, bg="#1DB954", fg="white", font=("Arial", 8, "bold")).grid(row=1, column=4, padx=5)

        # 5. Image Preview
        self.img_label = tk.Label(root, text="[Album Artwork]", bg="#e0e0e0", width=30, height=8)
        self.img_label.pack(pady=10)
        
        # 6. Run Button
        self.btn_generate = tk.Button(root, text="🚀 CREATE PITCH PAGE", command=self.run_process, 
                                      bg="#1DB954", fg="white", font=("Arial", 14, "bold"), padx=20, pady=10)
        self.btn_generate.pack(pady=10)
        
        self.status_lbl = tk.Label(root, text="Ready", bg="#f0f0f0", fg="#666")
        self.status_lbl.pack(pady=5)

        # Initialize Defaults
        self.load_defaults()

    def restore_genre_search(self, event):
        if not self.entry_genre_search.get():
            self.entry_genre_search.insert(0, "Search genres...")
            self.populate_genres(self.genres_list)

    def clear_genre_search(self):
        if self.entry_genre_search.get() == "Search genres...":
            self.entry_genre_search.delete(0, tk.END)

    def filter_genres(self, event):
        query = self.entry_genre_search.get().lower()
        if not query or query == "search genres...":
            filtered = self.genres_list
        else:
            filtered = [g for g in self.genres_list if query in g.lower() or self.genre_vars[g].get()]
        self.populate_genres(filtered)

    def populate_genres(self, genres_to_show):
        for w in self.genre_widgets:
            w.destroy()
        self.genre_widgets.clear()
        
        genres_to_show = list(dict.fromkeys(genres_to_show))
        
        for i, genre in enumerate(sorted(genres_to_show)):
            chk = tk.Checkbutton(self.genre_inner_frame, text=genre, variable=self.genre_vars[genre], bg="#ffffff", command=lambda g=genre: self.check_genre_limit(g))
            chk.grid(row=i//3, column=i%3, sticky="w")
            self.genre_widgets.append(chk)
            
        self.genre_canvas.yview_moveto(0)

    def save_all_settings(self):
        config = load_config()
        
        # Spotify
        config["client_id"] = self.entry_client_id.get().strip()
        config["client_secret"] = self.entry_client_secret.get().strip()
        
        # SMTP
        config["smtp_host"] = self.entry_smtp_host.get().strip()
        config["smtp_port"] = self.entry_smtp_port.get().strip()
        config["sender_email"] = self.entry_sender_email.get().strip()
        config["app_password"] = self.entry_app_password.get().strip()
        
        save_config(config)
        messagebox.showinfo("Saved", "모든 설정(API & SMTP)이 저장되었습니다!")

    def load_defaults(self):
        # Basic defaults
        self.entry_artist.insert(0, "ChickenBoomZup")
        self.entry_song.insert(0, "Wish I Was With U")
        self.entry_spotify.insert(0, "https://open.spotify.com/track/0TzZkiRcKe9rnFPha8Iqjt")
        
        default_mp3 = os.path.join(BASE_DIR, "Wish I Was With U.mp3")
        if not os.path.exists(default_mp3):
             fallback = os.path.expanduser("~/Downloads/Wish I Was With U.mp3")
             if os.path.exists(fallback): default_mp3 = fallback

        self.entry_mp3.insert(0, default_mp3)

        # Load Config
        config = load_config()
        if "client_id" in config: self.entry_client_id.insert(0, config["client_id"])
        if "client_secret" in config: self.entry_client_secret.insert(0, config["client_secret"])
        
        if "smtp_host" in config: 
            self.entry_smtp_host.delete(0, tk.END)
            self.entry_smtp_host.insert(0, config["smtp_host"])
        if "smtp_port" in config:
            self.entry_smtp_port.delete(0, tk.END)
            self.entry_smtp_port.insert(0, config["smtp_port"])
        if "sender_email" in config: self.entry_sender_email.insert(0, config["sender_email"])
        if "app_password" in config: self.entry_app_password.insert(0, config["app_password"])

    def browse_mp3(self):
        f = filedialog.askopenfilename(filetypes=[("MP3", "*.mp3")])
        if f: 
            self.entry_mp3.delete(0, tk.END)
            self.entry_mp3.insert(0, f)

    def manual_check_spotify(self):
        threading.Thread(target=self.fetch_cover, args=(self.entry_spotify.get().strip(),)).start()

    def check_genre_limit(self, changed_genre):
        if sum([v.get() for v in self.genre_vars.values()]) > 3:
            self.genre_vars[changed_genre].set(False)
            messagebox.showwarning("Limit", "Max 3 genres allowed.")

    def fetch_cover(self, url):
        self.status_lbl.config(text="Fetching artwork...")
        cover = get_spotify_cover_image(url)
        if cover:
            self.cover_url = cover
            try:
                res = requests.get(cover, verify=False)
                img = Image.open(BytesIO(res.content)).resize((200, 200), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.img_label.config(image=photo, width=200, height=200, text="")
                self.img_label.image = photo
                self.status_lbl.config(text="Artwork loaded! (Ready to create)")
            except: self.status_lbl.config(text="Image Error")
        else: self.status_lbl.config(text="No Artwork Found")

    def run_process(self):
        artist = self.entry_artist.get().strip()
        title = self.entry_song.get().strip()
        spotify_link = self.entry_spotify.get().strip()
        mp3_path = self.entry_mp3.get().strip()
        cid = self.entry_client_id.get().strip()
        secret = self.entry_client_secret.get().strip()

        selected_genres = [g for g, v in self.genre_vars.items() if v.get()]
        genre_input = ", ".join(selected_genres) if selected_genres else "Pop"

        if not (artist and title and spotify_link and mp3_path):
            messagebox.showwarning("Error", "Please fill in all fields.")
            return

        if not (cid and secret):
             if not messagebox.askyesno("No API Keys", "Spotify API Key가 없으면 이메일 수집을 할 수 없습니다.\n\n계속 진행하여 'HTML 페이지만' 생성하시겠습니까?"):
                 return

        # Save keys implicitly if provided
        if cid and secret:
            save_config({"client_id": cid, "client_secret": secret})

        self.btn_generate.config(state="disabled", text="Processing...")
        
        cover = getattr(self, 'cover_url', None) or get_spotify_cover_image(spotify_link)
        
        threading.Thread(target=self.process_thread, args=(artist, title, spotify_link, mp3_path, cover, genre_input, cid, secret)).start()

    def process_thread(self, artist, title, spotify_link, mp3_path, cover_url, genre, cid, secret):
        try:
            filename_safe = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(" ", "_")
            
            self.status_lbl.config(text="Processing Audio...")
            song_id = f"{artist}_{title}".replace(" ", "_")
            preview_filename = process_audio(mp3_path, song_id)
            
            self.status_lbl.config(text="Generating HTML...")
            html_filename = f"pitch_{filename_safe}.html"
            final_html_path = self.generate_pitch_compiled(artist, title, spotify_link, cover_url, preview_filename, html_filename, genre)
            
            if cid and secret:
                self.run_scraper(genre, final_html_path, cid, secret, artist, title, cover_url)
            else:
                 self.root.after(0, lambda: messagebox.showinfo("Done", f"HTML Generated: {final_html_path}\n(Skipped scraping due to missing keys)"))
                 self.root.after(0, lambda: self.btn_generate.config(state="normal", text="🚀 CREATE PITCH PAGE"))

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.root.after(0, lambda: self.btn_generate.config(state="normal", text="🚀 CREATE PITCH PAGE"))

    def run_scraper(self, genre_input, html_path, cid, secret, artist, title, cover_url):
        try:
            self.status_lbl.config(text=f"🔍 Searching curators for {genre_input} (Spotify API)...")
            
            scraper = SpotifyEmailScraper(client_id=cid, client_secret=secret)
            
            def update_status(msg):
                self.root.after(0, lambda: self.status_lbl.config(text=msg))
                
            collected_emails = scraper.scrape_emails(genre_input, max_count=30, progress_callback=update_status)
            
            self.root.after(0, lambda: self.open_preview(collected_emails, html_path, artist, title, cover_url, genre_input))
            
        except Exception as e:
            msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Scraping Error", msg))
        finally:
             self.root.after(0, lambda: self.btn_generate.config(state="normal", text="🚀 CREATE PITCH PAGE"))
             self.root.after(0, lambda: self.status_lbl.config(text="Ready"))

    def open_preview(self, emails, html_path, artist, title, cover_url, genre):
        if not emails:
            messagebox.showwarning("No Emails", "No emails found via Spotify API.\nTry different genres or check if keys are valid.")
        else:
            EmailPreviewWindow(self.root, emails, html_path, artist, title, cover_url, genre)

    def generate_pitch_compiled(self, artist, title, spotify_url, cover_url, audio_path, output_filename, genre):
        template_path = os.path.join(TEMPLATE_DIR, TEMPLATE_FILE)
        if not os.path.exists(template_path): return # Should create default
        
        with open(template_path, "r", encoding="utf-8") as f:
            template = Template(f.read())
            
        full_audio_path = os.path.join(OUTPUT_DIR, audio_path)
        audio_src = audio_path
        
        if os.path.exists(full_audio_path):
            import base64
            with open(full_audio_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                audio_src = f"data:audio/mp3;base64,{b64}"

        html_content = template.render(
            artist_name=artist, track_title=title, spotify_link=spotify_url,
            cover_image=cover_url or "https://via.placeholder.com/300",
            preview_audio_file=audio_src, genre=genre
        )
        
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return output_path

if __name__ == "__main__":
    root = tk.Tk()
    app = PromotionApp(root)
    root.mainloop()
