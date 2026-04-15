# 🎵 Spotify Music Promoter Ecosystem

> **인디 뮤지션 및 기획사를 위한 통합 뮤직 프로모션 대시보드 자동화 마케팅 솔루션**  
> 발매된 곡을 전 세계 음악 블로그, 플레이리스트 큐레이터, 리뷰 매체에 손쉽게(Pitch) 제안하고 홍보할 수 있는 올인원 툴입니다.

---

## 📌 프로젝트 개요

**Spotify Music Promoter**는 수작업으로 진행되던 해외 음악 프로모션을 자동화하기 위해 만들어진 하이브리드 솔루션입니다.
Spotify API와 연동하여 트랙 정보를 고속으로 가져오고, 장르별 타겟 큐레이터/블로거 이메일을 딥 서치 기반으로 수집하며, 개별 캠페인 홍보를 위한 맞춤형 Pitch(청취) 페이지를 자동 렌더링 후 생성해 줍니다. 

### 💡 탄생 배경

해외 주요 블로그와 큐레이터들에게 내 음악을 알리고 플레이리스트에 등재하기 위해서는 방대한 매체를 직접 찾아 이메일을 보내는 'Pitching' 과정이 필수적입니다. 이메일 100통을 보내기 위해 수일의 시간이 걸리던 막막한 노동을 백엔드 파이썬 엔진과 멋진 태블릿 화면(React)을 접목시켜 단 10분, 원클릭으로 해결하기 위해 탄생했습니다.

---

## 🖥️ 화면 구성 (Web Dashboard)

```text
┌─────────────────────────────────────────────────────┐
│  🎵 Spotify Music Promoter Dashboard                │
├──────────────┬──────────────────────────────────────┤
│  메뉴 네비    │  🔎 곡 검색 (Spotify API)            │
│              │  [ Search Track by Title/Artist... ] │
│  [캠페인설정] ├──────────────────────────────────────┤
│  [실행내역]   │  💿 선택된 트랙: "Flowers Facing Guns"│
│  [통계분석]   │                                      │
│  [설정]       ├──────────────────────────────────────┤
│              │  🎯 타겟 장르 선택                     │
│              │  ☑ Indie Pop   ☑ Lo-Fi   □ EDM      │
│              │  ☑ Post-Rock   □ R&B                │
│              ├──────────────────────────────────────┤
│              │  [🚀 캠페인 시작하기]                  │
│              ├──────────────────────────────────────┤
│              │  ● 진행 상태                  ████░░░ │
│              │  → "이메일 큐레이터 30명 수집 완료..."  │
└──────────────┴──────────────────────────────────────┘
```

---

## ⚙️ 핵심 기술 스택

| 분류 | 기술 | 역할 |
|------|------|------|
| **언어** | TypeScript, Python 3.10+ | 프론트엔드 대시보드 및 백엔드 스크래핑 엔진 |
| **Frontend** | React 18, Vite | 모바일/태블릿에 최적화된 반응형 웹 대시보드 |
| **Backend** | FastAPI, uvicorn | 로컬 PC 엔진 브릿지 웹서버 |
| **Data & Auth**| Google Firebase | Firestore (Task Queue 실시간 동기화), Hosting |
| **스크래핑/검색**| Spotify Web API, BeautifulSoup4 | 공식 곡 메타데이터 검색 및 큐레이터 웹사이트 파싱 |
| **템플릿/생성**| Jinja2 | 음원 재생용 커스텀 HTML Pitch 페이지 자동 렌더링 |
| **메일러** | smtplib, email.mime | 수집된 큐레이터들에게 SMTP 프로토콜 대량 이메일 발송 |

---

## 🔄 캠페인 자동화 파이프라인

```text
Web Dashboard에서 곡 제목 + 장르 입력 및 '캠페인 시작'
    │
    ▼
[1] 큐(Task Queue) 할당 (Firestore)
    - Firestore 'promo_tasks_spotify' 컬렉션에 pending 상태 등록
    - 로컬 PC 엔진(Python FastAPI)이 이벤트를 실시간 감지
    │
    ▼
[2] Spotify 곡 정보 메타데이터 추출 (Spotify API)
    - 트랙 ID 확보 및 고해상도 앨범 커버 수집
    - 곡 외부 링크(Spotify URL) 등 파싱
    │
    ▼
[3] 맞춤형 Pitch(프로모션) 페이지 자동 렌더링
    - Jinja2를 사용해 HTML 렌더링 (곡 제목, 커버, 아티스트명 주입)
    - 생성된 HTML 파일을 Firebase Hosting 으로 공용 URL(배포)
    │
    ▼
[4] 딥 서치 이메일 스크래핑 (BeautifulSoup)
    - 지정된 장르에 매칭되는 DB 우선 탐색 
    - Google Search 및 음악 블로그 크롤링을 통한 이메일 확보 및 검증
    │
    ▼
[5] 프로모션 이메일 일괄 송신 (SMTP)
    - 추출된 최종 큐레이터 메일 주소로 맞춤형 문구와 Pitch 페이지 URL 발송
    - Firestore를 통해 React Dashboard에 'completed' 상태 전송
```

---

## 📁 프로젝트 구조

```text
spotify-music-promoter/
├── backend/                   # Python FastAPI 브릿지 클라이언트 서버
│   ├── main.py                # Firestore Listener 및 API 서빙
│   └── serviceAccountKey.json # (Git 제외됨) Firebase 인증키
├── src/                       # React 프론트엔드 대시보드 코어
│   ├── components/            
│   ├── pages/
│   ├── App.tsx
│   └── firebase.ts            # 프론트엔드용 Firebase DB 접속
├── python_core_engine/        # (Python) 실제 스크래핑 및 API 코어 엔진로직
│   ├── SpotifyPromoter.py     # Spotify 검색 클래스 
│   ├── EmailScraper.py        # 큐레이터 이메일 웹 크롤링 분석 클래스
│   └── templates/             # Jinja2 Pitch 파일 템플릿
├── public/                    # React 정적 에셋
├── START_SPOTIFY_ENGINE.bat   # 백엔드 엔진 자동 실행 배치스크립트
└── package.json               # Frontend 의존성 라이브러리
```

---

## 🚀 설치 및 실행

### 프론트엔드 (React Dashboard)

```bash
# 1. 저장소 클론
git clone https://github.com/only2433/spotify-music-promoter.git
cd spotify-music-promoter

# 2. 패키지 설치
npm install

# 3. 개발 서버 실행
npm run dev
```

### 백엔드 파이썬 엔진 (Bridge & Crawler)

```bash
# 1. Python 라이브러리 설치
pip install fastapi uvicorn requests beautifulsoup4 jinja2 firebase-admin

# 2. Firebase 서비스 계정 인증
# backend/ 폴더 안에 `serviceAccountKey.json` 파일을 배치해야 합니다.

# 3. 로컬 엔진 서버 실행
# 루트 폴더 속 배치 파일 실행:
./START_SPOTIFY_ENGINE.bat

# 또는 수동 실행:
python backend/main.py
```

> ⚠️ **보안 관련(중요)**  
> Spotify Client Secret Key와 이메일 큐레이터 코어 DB가 포함된 
> `private_keys.py`, `private_core.py` 파일들은 저장소에 배포되지 않습니다. 해당 기능은 각 사용자가 직접 API 키를 발급받아 환경 변수를 통해 입력하도록 커스터마이징이 필요합니다.

---

## 🎯 대상 사용자

- 🎸 **인디 뮤지션 / 밴드** — 최소한의 비용으로 신곡을 글로벌 큐레이터들에게 세일즈하고 싶은 분
- 🏢 **음원 기획사 / 레이블 매니저** — 반복적인 홍보 메일 발송 및 컨택 포인트 관리를 완전 자동화하고 싶은 분
- 🎧 **음반 프로모터** — 여러 아티스트의 릴리즈 정보를 효과적으로 템플릿화하여 배포하고 모니터링해야 하는 분

---

## 📜 라이선스

This project is for personal use.  
Spotify API usage is subject to [Spotify's Developer Terms of Service](https://developer.spotify.com/terms).  
Commercial scraping of third-party emails should comply with respective local laws.
