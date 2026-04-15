import os
import sys
import io

if sys.platform == "win32":
    try:
        sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='utf-8', errors='ignore')
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='ignore')
        sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='ignore')
    except:
        pass

import re
import time
import random
import requests
import urllib3
import base64
import json
from bs4 import BeautifulSoup

import dns.resolver

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [강화된 블랙리스트] ---
# 이메일 앞부분(Local part)이 다음과 같으면 대부분 관리/시스템용입니다.
INVALID_PREFIXES = [
    "no-reply", "donotreply", "donot_reply", "admin", "administrator", "support", 
    "webmaster", "privacy", "hr", "jobs", "billing", "notification", "alert", 
    "mailer-daemon", "postmaster", "root", "sysadmin", "legal", "compliance",
    "accounts", "sales", "marketing", "office", "help", "contact-us", "info" 
    # note: 'info'는 가끔 실제 사람이 쓰기도 하지만 신뢰도는 낮음
]

# 플랫폼이나 서비스 자동 생성 메일의 도메인들
INVALID_DOMAINS = [
    "wix.com", "squarespace.com", "shopify.com", "wordpress.com", "weebly.com", 
    "jimdo.com", "bitly.com", "sentry.io", "github.com", "gitlab.com", "atlassian.net",
    "facebook.com", "fb.com", "twitter.com", "instagram.com", "google.com", 
    "apple.com", "microsoft.com", "localhost", "node.js", "react.js", "sentry.io",
    "domain.com", "email.com", "example.com", "test.com", "zohocorp.com", 
    "amazon.com", "aws.com"
]

def safe_print(msg):
    try:
        print(str(msg).encode('utf-8', 'ignore').decode('utf-8'))
    except:
        pass

# ─────────────────────────────────────────────
# 실제 활동 중인 큐레이터/플랫폼 실명 DB
# (수동 검증된 실제 제출 이메일 모음)
# ─────────────────────────────────────────────
try:
    from private_core import CURATOR_DB, SCRAPE_TARGETS
except ImportError:
    CURATOR_DB = {"Default": []}
    SCRAPE_TARGETS = {}

# DuckDuckGo 및 Bing 검색 URL 템플릿
SEARCH_ENGINES = [
    "https://html.duckduckgo.com/html/?q={query}",
    "https://www.bing.com/search?q={query}",
]

# 랜덤 User-Agent 풀
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]


class SpotifyEmailScraper:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.session = requests.Session()
        self.session.verify = False
        self.session.trust_env = False

    def _random_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def verify_domain_mx(self, email):
        """DNS 조회를 통해 도메인의 MX(Mail Exchange) 레코드가 있는지 확인 (유효성 검증)"""
        if not email or "@" not in email:
            return False
            
        domain = email.split("@")[-1].lower()
        
        # 캐시 처리 (동일 도메인 반복 조회 방지)
        if not hasattr(self, '_domain_cache'):
            self._domain_cache = {}
        
        if domain in self._domain_cache:
            return self._domain_cache[domain]
            
        try:
            # MX 레코드가 있는지 확인 (타임아웃은 짧게)
            answers = dns.resolver.resolve(domain, 'MX', timeout=3)
            is_valid = len(answers) > 0
            self._domain_cache[domain] = is_valid
            return is_valid
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
            self._domain_cache[domain] = False
            return False
        except Exception:
            # 기타 오류 발생 시 안전하게 True로 넘김 (차단 방지)
            return True

    def authenticate(self):
        """Spotify API 토큰 획득"""
        if not self.client_id or not self.client_secret:
            safe_print("[WARN] Spotify Client ID/Secret이 없습니다. Spotify 수집 단계를 건너뜁니다.")
            return False

        auth_str = f"{self.client_id}:{self.client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode('ascii')).decode('ascii')

        try:
            safe_print("[INFO] Spotify 인증 시도 중...")
            res = self.session.post(
                'https://accounts.spotify.com/api/token',
                headers={
                    'Authorization': f'Basic {auth_b64}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data={'grant_type': 'client_credentials'},
                timeout=10
            )
            if res.status_code == 200:
                self.access_token = res.json().get('access_token')
                safe_print("[OK] Spotify 토큰 획득 성공!")
                return True
            else:
                safe_print(f"[FAIL] 인증 실패: {res.status_code}")
                return False
        except Exception as e:
            safe_print(f"[ERROR] 인증 오류: {e}")
            return False

    # ─────────────────────────────────────────────
    # 메인 진입점
    # ─────────────────────────────────────────────
    def scrape_emails(self, genre_input, max_count=30, progress_callback=None):
        collected = {}  # email → dict (중복 방지를 위해 dict 사용)

        def cb(msg):
            safe_print(msg)
            if progress_callback:
                progress_callback(msg)

        # 장르 리스트 파싱
        if isinstance(genre_input, str):
            genres = [g.strip() for g in genre_input.split(",") if g.strip()]
        else:
            genres = list(genre_input)

        cb(f"[START] 장르: {genres}, 목표: {max_count}개")

        # ① DB 시드 데이터 (즉시, 검증된 큐레이터)
        cb("📋 [STEP 1/4] 검증된 큐레이터 DB 로딩...")
        self._load_from_db(genres, collected, max_count, cb)
        cb(f"  → 현재 수집: {len(collected)}개")

        # ② Spotify API 스크래핑
        if len(collected) < max_count:
            cb("🎵 [STEP 2/4] Spotify playlist 이메일 스캔...")
            if not self.access_token:
                self.authenticate()
            if self.access_token:
                self._scrape_spotify(genres, collected, max_count, cb)
            cb(f"  → 현재 수집: {len(collected)}개")

        # ③ 큐레이터 제출 사이트 직접 스크래핑
        if len(collected) < max_count:
            cb("🌐 [STEP 3/4] 큐레이터 사이트 스크래핑...")
            self._scrape_curator_sites(genres, collected, max_count, cb)
            cb(f"  → 현재 수집: {len(collected)}개")

        # ④ 검색 엔진 폴백
        if len(collected) < max_count:
            cb("🔍 [STEP 4/4] 검색 엔진 스캔...")
            self._scrape_search_engines(genres, collected, max_count, cb)
            cb(f"  → 현재 수집: {len(collected)}개")

        results = list(collected.values())
        cb(f"✅ 최종 수집 완료: {len(results)}개")
        return results

    # ─────────────────────────────────────────────
    # STEP 1: 검증 DB에서 로드
    # ─────────────────────────────────────────────
    def _load_from_db(self, genres, collected, max_count, cb):
        for genre in genres:
            # 정확한 장르 or 유사 장르 매칭
            seed_list = self._find_best_seeds(genre)
            for email in seed_list:
                if len(collected) >= max_count:
                    return
                if email not in collected and self._is_valid_email(email):
                    collected[email] = {
                        "email": email,
                        "source": f"Verified DB ({genre})",
                        "url": "https://submithub.com",
                        "genre": genre
                    }
                    cb(f"  ✓ [DB] {email}")

    def _find_best_seeds(self, genre):
        """입력 장르와 가장 비슷한 DB 키를 찾아 반환"""
        genre_lower = genre.lower()
        # 완전 일치 우선
        for key in CURATOR_DB:
            if key.lower() == genre_lower:
                return CURATOR_DB[key]
        # 부분 일치
        for key in CURATOR_DB:
            if genre_lower in key.lower() or key.lower() in genre_lower:
                return CURATOR_DB[key]
        # 키워드 매핑
        keyword_map = {
            "hip": "Hip-Hop", "rap": "Hip-Hop", "trap": "Hip-Hop", "drill": "Hip-Hop",
            "soul": "R&B", "urban": "R&B", "neo": "R&B",
            "synth": "Synth-Pop", "wave": "Synth-Pop", "vaporwave": "Synth-Pop",
            "edm": "Electronic", "house": "Electronic", "techno": "Electronic", "trance": "Electronic",
            "lofi": "Lo-Fi", "chill": "Lo-Fi", "ambient": "Lo-Fi",
            "kpop": "K-Pop", "k-pop": "K-Pop", "korean": "K-Pop",
            "metal": "Rock", "punk": "Rock", "grunge": "Rock", "alternative": "Rock",
        }
        for kw, mapped in keyword_map.items():
            if kw in genre_lower:
                return CURATOR_DB.get(mapped, CURATOR_DB["Default"])
        return CURATOR_DB["Default"]

    # ─────────────────────────────────────────────
    # STEP 2: Spotify API 스크래핑 (강화판)
    # ─────────────────────────────────────────────
    def _scrape_spotify(self, genres, collected, max_count, cb):
        headers = {'Authorization': f'Bearer {self.access_token}'}

        for genre in genres:
            if len(collected) >= max_count:
                break

            # 더 다양하고 많은 쿼리 (이메일 노출 가능성 높은 것들)
            # 불필요한 플랫폼 메일 배제를 위해 마이너스 키워드 활용
            queries = [
                f'"{genre}" submit music email -support -wix -squarespace',
                f'"{genre}" playlist curator email -no-reply',
                f'{genre} music blog contact email -marketing',
                f'{genre} playlist submission gmail.com',
                f'submit {genre} music "reach me" -info',
                f'{genre} curator contact "{genre} playlist"',
                f'{genre} demo submission email',
                f'playlist {genre} email contact curator',
                f'"{genre}" independent music curator email',
            ]

            for query in queries:
                if len(collected) >= max_count:
                    break
                try:
                    res = self.session.get(
                        "https://api.spotify.com/v1/search",
                        headers=headers,
                        params={'q': query, 'type': 'playlist', 'limit': 50},
                        timeout=10
                    )

                    if res.status_code == 401:
                        cb("  [WARN] 토큰 만료, 재인증...")
                        self.authenticate()
                        headers = {'Authorization': f'Bearer {self.access_token}'}
                        continue

                    if res.status_code != 200:
                        continue

                    playlists = res.json().get('playlists', {}).get('items', [])
                    found_in_query = 0

                    for pl in playlists:
                        if not pl:
                            continue
                        # 설명 + 이름 + 소유자 모두 탐색
                        desc = pl.get('description', '') or ''
                        name = pl.get('name', '') or ''
                        owner = pl.get('owner', {}) or {}
                        owner_name = owner.get('display_name', '') or ''

                        # HTML 엔티티 복원
                        combined = f"{desc} {name} {owner_name}"
                        combined = (combined
                                    .replace("&lt;", "<").replace("&gt;", ">")
                                    .replace("&amp;", "&").replace("&#x27;", "'")
                                    .replace("&quot;", '"').replace("&#39;", "'"))

                        if self._is_paid_promo(combined):
                            continue

                        emails_found = re.findall(
                            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                            combined
                        )
                        for email in emails_found:
                            email = email.lower().strip('.')
                            if self._is_valid_email(email) and email not in collected:
                                # 추가 검증: MX 레코드 체크
                                if self.verify_domain_mx(email):
                                    collected[email] = {
                                        "email": email,
                                        "source": f"Spotify: {name[:25]}",
                                        "url": pl.get('external_urls', {}).get('spotify', ''),
                                        "genre": genre,
                                        "verified": True
                                    }
                                    cb(f"  🎵 [Spotify] {email} (Verified)")
                                    found_in_query += 1
                                else:
                                    cb(f"  ⚠️ [Skip] {email} (No MX Record)")

                        if len(collected) >= max_count:
                            break

                    time.sleep(0.3)

                except Exception as e:
                    safe_print(f"  [API Error] {e}")
                    time.sleep(1)

    # ─────────────────────────────────────────────
    # STEP 3: 실제 큐레이터 사이트 스크래핑
    # ─────────────────────────────────────────────
    def _scrape_curator_sites(self, genres, collected, max_count, cb):
        # 스크래핑 대상 URL 목록 (이메일이 노출될 수 있는 페이지)
        target_pages = [
            "https://www.submithub.com/blog/music-blogs-that-accept-submissions",
            "https://musosoup.com/how-it-works",
            "https://www.indiemono.com/submit/",
            "https://www.earmilk.com/submit-music/",
            "https://highclouds.org/page/submit-music/",
            "https://www.thelineofbestfit.com/contact",
            "https://clashmusic.com/contact-us",
            "https://soundplate.com/submit-music/",
            "https://www.aupium.com/",
            "https://www.mariskalrock.com/",
            "https://indieshuffle.com/submission",
        ]

        for url in target_pages:
            if len(collected) >= max_count:
                break
            try:
                cb(f"  🌐 스크래핑: {url[:50]}...")
                res = self.session.get(url, headers=self._random_headers(), timeout=8)
                if res.status_code == 200:
                    emails = re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        res.text
                    )
                    for email in emails:
                        email = email.lower().strip('.')
                        genre = genres[0] if genres else "General"
                        if self._is_valid_email(email) and email not in collected:
                            if self.verify_domain_mx(email):
                                collected[email] = {
                                    "email": email,
                                    "source": f"Site: {url.split('/')[2][:20]}",
                                    "url": url,
                                    "genre": genre,
                                    "verified": True
                                }
                                cb(f"  🌐 [Site] {email} (Verified)")
                            else:
                                cb(f"  ⚠️ [Skip] {email} (No MX Record)")
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                safe_print(f"  [Site Error] {url[:40]}: {e}")

    # ─────────────────────────────────────────────
    # STEP 4: 검색 엔진 스크래핑 (Bing + DuckDuckGo)
    # ─────────────────────────────────────────────
    def _scrape_search_engines(self, genres, collected, max_count, cb):
        for genre in genres:
            if len(collected) >= max_count:
                break

            search_queries = [
                f'"{genre}" music blog "submit" "email" contact',
                f'"{genre}" curator playlist email "@gmail.com" OR "@outlook.com"',
                f'"{genre}" music submission "contact us" email',
                f'site:submithub.com "{genre}"',
                f'"{genre}" playlist curator "send your music"',
            ]

            for q in search_queries:
                if len(collected) >= max_count:
                    break

                # DuckDuckGo 먼저 (덜 공격적)
                for engine_url in SEARCH_ENGINES:
                    if len(collected) >= max_count:
                        break
                    try:
                        url = engine_url.format(
                            query=requests.utils.quote(q)
                        )
                        cb(f"  🔍 검색: {q[:45]}...")
                        res = self.session.get(
                            url,
                            headers=self._random_headers(),
                            timeout=10
                        )
                        if res.status_code == 200:
                            emails = re.findall(
                                r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                                res.text
                            )
                            # 검색 결과 내 링크에서도 URL 추출하여 추가 스크래핑
                            soup = BeautifulSoup(res.text, 'html.parser')
                            result_links = []
                            for a in soup.find_all('a', href=True):
                                href = a['href']
                                if 'http' in href and 'google' not in href and 'bing' not in href and 'duck' not in href:
                                    result_links.append(href)

                            for email in emails:
                                email = email.lower().strip('.')
                                if self._is_valid_email(email) and email not in collected:
                                    if self.verify_domain_mx(email):
                                        collected[email] = {
                                            "email": email,
                                            "source": f"Search: {genre}",
                                            "url": url,
                                            "genre": genre,
                                            "verified": True
                                        }
                                        cb(f"  🔍 [Search] {email} (Verified)")
                                    else:
                                        cb(f"  ⚠️ [Skip] {email} (No MX Record)")

                            # 검색 결과 첫 3개 페이지 딥 스캔
                            for link in result_links[:3]:
                                if len(collected) >= max_count:
                                    break
                                try:
                                    sub_res = self.session.get(
                                        link, headers=self._random_headers(), timeout=6
                                    )
                                    if sub_res.status_code == 200:
                                        sub_emails = re.findall(
                                            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                                            sub_res.text
                                        )
                                        for email in sub_emails:
                                            email = email.lower().strip('.')
                                            if self._is_valid_email(email) and email not in collected:
                                                if self.verify_domain_mx(email):
                                                    collected[email] = {
                                                        "email": email,
                                                        "source": f"DeepScan: {link.split('/')[2][:20] if '//' in link else link[:20]}",
                                                        "url": link,
                                                        "genre": genre,
                                                        "verified": True
                                                    }
                                                    cb(f"  🔬 [Deep] {email} (Verified)")
                                                else:
                                                    cb(f"  ⚠️ [Skip] {email} (No MX Record)")
                                    time.sleep(random.uniform(0.3, 0.8))
                                except:
                                    pass

                        time.sleep(random.uniform(1.0, 2.0))

                    except Exception as e:
                        safe_print(f"  [Search Error] {e}")
                        time.sleep(2)

    # ─────────────────────────────────────────────
    # 유틸리티
    # ─────────────────────────────────────────────
    def _is_paid_promo(self, text):
        """유료 프로모션 필터"""
        text_lower = text.lower()
        bad = [
            "paid placement", "placement fee", "submission fee",
            "buy followers", "sell streams", "guaranteed streams",
            "promotion agency", "increase streams guaranteed",
            "pricing plan", "buy now", "purchase placement"
        ]
        return any(k in text_lower for k in bad)

    def _is_valid_email(self, email):
        if not email or len(email) < 6:
            return False
        
        email = email.lower().strip('.')
        if "@" not in email:
            return False
            
        local_part, domain = email.split("@", 1)
        
        # 1. Local Part (앞부분) 체크 - 관리용 계정 제외
        if any(local_part == p or local_part.startswith(p + ".") or local_part.startswith(p + "-") for p in INVALID_PREFIXES):
            return False
            
        # 2. 이미지/파일 확장자 필터 (실수로 텍스트에서 섞여 나온 것들)
        invalid_ext = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".php", ".aspx", ".webp", ".mp3", ".wav"]
        if any(email.endswith(x) for x in invalid_ext):
            return False
            
        # 3. 스팸성/시스템 도메인 필터
        if any(d in domain for d in INVALID_DOMAINS):
            return False
        
        # 4. 숫자만 가득한 스팸성 메일 (예: 123847293847@qq.com 등)
        if local_part.isdigit() and len(local_part) > 8:
            return False
            
        # 5. 이메일 형식 정규식 검사
        pattern = r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$'
        if not re.match(pattern, email):
            return False
            
        return True


if __name__ == "__main__":
    cid = os.environ.get('SPOTIPY_CLIENT_ID')
    secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
    if cid and secret:
        s = SpotifyEmailScraper(cid, secret)
        results = s.scrape_emails("Pop, R&B", max_count=30)
        for r in results:
            print(f"  {r['email']} ({r['source']})")
