import React, { useState, useRef, useEffect } from 'react';
import { Rocket, Globe, Music, Loader2, X } from 'lucide-react';
import { db, collection, addDoc, onSnapshot, doc, query, where, limit } from './firebase';
import { Buffer } from 'buffer';

const API_BASE = 'http://127.0.0.1:8000';

const ALL_GENRES = [
    'Acoustic', 'Afrobeats', 'Alternative', 'Ambient', 'Americana',
    'Art Pop', 'Bedroom Pop', 'Bluegrass', 'Blues', 'Bossa Nova',
    'Chillout', 'Christian', 'Classical', 'Country', 'Dance',
    'Dark Pop', 'Deep House', 'Dream Pop', 'Drum & Bass', 'Dubstep',
    'EDM', 'Electronic', 'Emo', 'Experimental', 'Folk',
    'Funk', 'Future Bass', 'Gospel', 'Grunge', 'Hard Rock',
    'Heavy Metal', 'Hip-Hop', 'House', 'IDM', 'Indie',
    'Indie Folk', 'Indie Pop', 'Indie Rock', 'Jazz', 'K-Pop',
    'Latin', 'Lo-Fi', 'Lounge', 'Math Rock', 'Metalcore',
    'Minimal', 'Neo Soul', 'New Wave', 'Noise Rock', 'Nu-Metal',
    'Orchestral', 'Pop', 'Post-Rock', 'Progressive Rock', 'Punk',
    'R&B', 'Rap', 'Reggae', 'Reggaeton', 'Shoegaze',
    'Singer-Songwriter', 'Ska', 'Smooth Jazz', 'Soul', 'Synth-Pop',
    'Tech House', 'Techno', 'Trap', 'Trance', 'Trip-Hop',
    'UK Garage', 'Vaporwave', 'World Music',
];

export default function App() {
    // Track State
    const [artist, setArtist] = useState('');
    const [track, setTrack] = useState('');
    const [spotifyUrl, setSpotifyUrl] = useState('');
    const [albumArt, setAlbumArt] = useState<string | null>(null);

    // Genre State
    const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
    const [genreSearch, setGenreSearch] = useState('');
    const [maxCurators, setMaxCurators] = useState(30);

    // Search State
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [showDropdown, setShowDropdown] = useState(false);
    const [showGenreModal, setShowGenreModal] = useState(false);

    // Campaign State
    const [isProcessing, setIsProcessing] = useState(false);
    const [statusMsg, setStatusMsg] = useState('시스템 준비 완료.');
    const [taskId, setTaskId] = useState<string | null>(null);
    const [pitchPageUrl, setPitchPageUrl] = useState<string | null>(null);
    const [clientLogs, setClientLogs] = useState<string[]>([]);
    const [curators, setCurators] = useState<any[]>([]);

    // Watch taskId for realtime progress updates from Firestore
    useEffect(() => {
        if (!taskId) return;
        const unsub = onSnapshot(doc(db, 'promo_tasks_spotify', taskId), (snap) => {
            const data = snap.data();
            if (data?.status === 'processing') {
                setStatusMsg('⏳ ' + (data.log || '캠페인 실행 중...'));
            } else if (data?.status === 'completed') {
                const rawCurators = data.results || [];
                const parsedCurators = rawCurators.map((item: any) => {
                    if (typeof item === 'string') {
                        try { return JSON.parse(item); } catch { return item; }
                    }
                    return item;
                });
                
                setCurators(parsedCurators);
                setPitchPageUrl(data.pitch_page_url || '');
                setStatusMsg(`✅ 큐레이터 ${parsedCurators.length}명 발굴! 피치 페이지 생성 완료.`);
                addLog('✅ 캠페인 준비 완료!');
                setIsProcessing(false);
                unsub();
            } else if (data?.status === 'error') {
                setStatusMsg('❌ 오류: ' + (data.log || '캠페인 시작 실패'));
                addLog('❌ 실패: ' + (data.log || '알 수 없는 오류'));
                setIsProcessing(false);
                unsub();
            }
        });
        return () => unsub();
    }, [taskId]);

    const searchRef = useRef<HTMLDivElement>(null);

    const addLog = (msg: string) => setClientLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 50));

    // ─── Search Logic (태블릿 직접 검색 모드) ─────────────────────────
    const handleSearch = async () => {
        const q = searchQuery.trim();
        if (!q) return;
        setIsSearching(true);
        setShowDropdown(true);
        setSearchResults([]);
        addLog(`🔍 직접 검색 시작: "${q}"`);

        try {
            const payload = {
                type: 'search-spotify',
                query: q,
                status: 'pending',
                created_at: new Date().toISOString()
            };
            const taskRef = await addDoc(collection(db, 'promo_tasks_spotify'), payload);
            addLog(`📡 API 요청 전송됨.`);

            const searchPromise = new Promise((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error('네트워크 지연')), 15000);
                const unsub = onSnapshot(doc(db, 'promo_tasks_spotify', taskRef.id), (snap) => {
                    const data = snap.data();
                    if (data?.status === 'completed') {
                        clearTimeout(timeout);
                        unsub();
                        resolve(data.results || []);
                    } else if (data?.status === 'error') {
                        clearTimeout(timeout);
                        unsub();
                        reject(new Error(data.log || '검색 실패'));
                    }
                });
            });

            const rawResults: any = await searchPromise;
            const parsedResults = rawResults.map((item: any) => {
                if (typeof item === 'string') {
                    try { return JSON.parse(item); } catch { return item; }
                }
                return item;
            });
            setSearchResults(parsedResults);
            addLog(`✅ ${parsedResults.length}개의 결과를 찾았습니다.`);

        } catch (err: any) {
            addLog(`❌ 오류: ${err.message}`);
        } finally {
            setIsSearching(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSearch();
    };

    const selectTrack = (r: any) => {
        if (r.error) return;
        setSpotifyUrl(r.url || '');
        setTrack(r.name || '');
        setArtist(r.artist || '');
        setAlbumArt(r.image || null);
        setShowDropdown(false);
        setSearchQuery(`${r.name} — ${r.artist}`);
        addLog(`🎵 선택됨: ${r.name} by ${r.artist}`);
    };

    const clearTrack = () => {
        setSpotifyUrl('');
        setTrack('');
        setArtist('');
        setAlbumArt(null);
        setSearchQuery('');
        setShowDropdown(false);
        setSearchResults([]);
    };

    // ─── Genre Logic ─────────────────────────────────────────────────
    const toggleGenre = (g: string) => {
        setSelectedGenres(prev =>
            prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]
        );
    };

    const filteredGenres = ALL_GENRES.filter(g =>
        g.toLowerCase().includes(genreSearch.toLowerCase())
    );

    // ─── Campaign Launch ─────────────────────────────────────────────
    const handleLaunch = async () => {
        if (!spotifyUrl) { setStatusMsg('❌ 곡을 먼저 선택하세요.'); return; }
        if (selectedGenres.length === 0) { setStatusMsg('❌ 장르를 1개 이상 선택하세요.'); return; }

        setIsProcessing(true);
        setStatusMsg('🚀 캠페인 시작 중...');
        addLog('캠페인 태스크 생성 시도...');

        const payload = {
            type: 'start-campaign-spotify',
            artist_name: artist,
            track_title: track,
            spotify_url: spotifyUrl,
            genres: selectedGenres,
            max_curators: maxCurators,
            album_art: albumArt,
            status: 'pending',
            created_at: new Date().toISOString(),
        };

        try {
            const docRef = await addDoc(collection(db, 'promo_tasks_spotify'), payload);
            setTaskId(docRef.id);
            setStatusMsg('✅ 클라우드 태스크 전송됨. PC 브리지 대기 중...');
            addLog(`✅ 태스크 생성: ${docRef.id}`);
        } catch (err: any) {
            setStatusMsg('❌ 오류: ' + (err.message || '태스크 생성 실패'));
            addLog(`❌ 실패: ${err.message}`);
        } finally {
            setIsProcessing(false);
        }
    };

    // ─── Styles ──────────────────────────────────────────────────────
    const inputStyle: React.CSSProperties = {
        background: '#111',
        border: '1px solid #333',
        borderRadius: '12px',
        padding: '12px 16px',
        color: '#fff',
        fontSize: '14px',
        outline: 'none',
        width: '100%',
        boxSizing: 'border-box',
        fontFamily: 'Outfit, sans-serif',
    };

    const cardStyle: React.CSSProperties = {
        background: 'rgba(25,25,30,0.7)',
        borderRadius: '24px',
        border: '1px solid rgba(255,255,255,0.08)',
        padding: '28px',
        backdropFilter: 'blur(20px)',
    };

    const genreBtnStyle = (selected: boolean): React.CSSProperties => ({
        padding: '5px 14px',
        borderRadius: '20px',
        border: `1px solid ${selected ? '#1DB954' : 'rgba(255,255,255,0.12)'}`,
        background: selected ? '#1DB954' : 'rgba(255,255,255,0.04)',
        color: selected ? '#000' : '#ccc',
        fontSize: '12px',
        cursor: 'pointer',
        fontWeight: selected ? 700 : 400,
        transition: 'all 0.15s ease',
        whiteSpace: 'nowrap' as const,
        fontFamily: 'Outfit, sans-serif',
    });

    // ─── Clipboard & Gmail ───────────────────────────────────────────
    const copyPitchAndOpenGmail = async (isTest: boolean) => {
        try {
            const htmlBody = `
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #000000; padding: 60px 0; width: 100%;">
                    <div style="max-width: 520px; margin: 0 auto; background-color: #121212; border-radius: 12px; overflow: hidden; border: 1px solid #282828;">
                        <!-- Header -->
                        <div style="text-align: center; padding: 40px 0 20px 0;">
                            ${albumArt ? `<img src="${albumArt}" alt="Artwork" style="width: 200px; height: 200px; object-fit: cover; border-radius: 8px; box-shadow: 0 10px 25px rgba(29, 185, 84, 0.2);" />` : ''}
                        </div>
                        
                        <!-- Track Content -->
                        <div style="padding: 10px 40px 40px 40px; text-align: center;">
                            <p style="margin: 0; color: #1DB954; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;">New Release</p>
                            <h1 style="margin: 10px 0 5px 0; color: #FFFFFF; font-size: 28px; font-weight: 800; letter-spacing: -0.5px;">${track || 'Untitled'}</h1>
                            <p style="margin: 0 0 30px 0; color: #A7A7A7; font-size: 15px; font-weight: 500;">by ${artist || 'Unknown Artist'}</p>
                            
                            <p style="color: #FFFFFF; font-size: 15px; line-height: 1.6; text-align: left; margin-bottom: 15px;">
                                Hi there,
                            </p>
                            <p style="color: #B3B3B3; font-size: 15px; line-height: 1.6; text-align: left; margin-bottom: 35px;">
                                I hope you're having a great week. I'm excited to share my latest release. I believe this track would be a perfect fit for your highly curated playlists.
                            </p>
                            
                            <!-- Primary Action -->
                            <a href="${spotifyUrl}" style="display: inline-block; background-color: #1DB954; color: #000000; padding: 14px 40px; border-radius: 30px; text-decoration: none; font-weight: 800; font-size: 14px; letter-spacing: 1px; text-transform: uppercase;">
                                Listen on Spotify
                            </a>
                            
                            <div style="width: 100%; height: 1px; border-top: 1px solid #282828; margin: 40px 0;"></div>
                            
                            <!-- Secondary Action (Artist Profile) -->
                            <p style="color: #A7A7A7; font-size: 13px; margin-bottom: 12px; font-weight: 500;">Discover more of our music:</p>
                            <a href="https://open.spotify.com/artist/4UjwDdQtgC8ywXTXLzmQEI" style="display: inline-block; border: 1px solid #A7A7A7; color: #FFFFFF; padding: 10px 24px; border-radius: 20px; text-decoration: none; font-weight: 600; font-size: 12px; letter-spacing: 1px; text-transform: uppercase;">
                                ChickenBoomZup Profile
                            </a>
                        </div>
                        
                        <!-- Footer -->
                        <div style="background-color: #0A0A0A; padding: 20px; text-align: center;">
                            <p style="color: #666666; font-size: 11px; margin: 0;">
                                &copy; ${new Date().getFullYear()} ${artist}. All rights reserved.
                            </p>
                        </div>
                    </div>
                </div>
            `;

            const plainBody = `Hi there,\n\nI hope you're doing well. I wanted to share my new track ${track} with you.\n\nListen on Spotify:\n${spotifyUrl}\n\nCheck out our Artist Profile (ChickenBoomZup):\nhttps://open.spotify.com/artist/4UjwDdQtgC8ywXTXLzmQEI\n\nBest regards,\n${artist}`;

            const blobHtml = new Blob([htmlBody], { type: 'text/html' });
            const blobText = new Blob([plainBody], { type: 'text/plain' });
            const clipboardItem = new window.ClipboardItem({
                'text/html': blobHtml,
                'text/plain': blobText
            });
            await navigator.clipboard.write([clipboardItem]);
            
            const subject = encodeURIComponent(`${isTest ? '[Test] ' : ''}Music Submission: ${track} by ${artist}`);
            const bccList = isTest ? '' : curators.map((c: any) => c.email).filter(Boolean).join(',');
            const toArg = isTest ? 'to=' : `bcc=${bccList}`;
            
            window.open(`https://mail.google.com/mail/?view=cm&fs=1&${toArg}&su=${subject}&body=${encodeURIComponent('(여기에 Ctrl+V를 눌러서 메일 양식을 붙여넣으세요!)')}`, '_blank');
            
            setStatusMsg('✅ 클립보드 복사 완료!');
            addLog('✅ 이메일양식 클립보드 저장완료');
        } catch (e) {
            console.error(e);
            alert("복사 실패. HTTPS 환경인지 확인하세요.");
        }
    };

    return (
        <div style={{ background: '#050505', color: '#fff', minHeight: '100vh', padding: '24px 28px', fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box' }}>
            {/* ── Header ── */}
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ background: '#1DB954', padding: '10px', borderRadius: '14px', display: 'flex' }}>
                        <Music size={22} color="#000" />
                    </div>
                    <div>
                        <h1 style={{ margin: 0, fontSize: '22px', fontWeight: 800, letterSpacing: '-0.5px' }}>Spotify Music Promoter</h1>
                        <div style={{ fontSize: '12px', color: '#555', marginTop: '2px' }}>캠페인 대시보드</div>
                    </div>
                </div>
                <div style={{ background: 'rgba(29,185,84,0.08)', border: '1px solid rgba(29,185,84,0.2)', padding: '8px 18px', borderRadius: '30px', fontSize: '13px', color: '#1DB954', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {statusMsg}
                </div>
            </header>

            {/* ── Main Grid ── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: '24px', alignItems: 'start' }}>

                {/* ── LEFT PANEL ── */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                    {/* Search Card */}
                    <div style={{ ...cardStyle, position: 'relative', zIndex: 10 }}>
                        <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', color: '#555', marginBottom: '12px' }}>🔍 SPOTIFY TRACK 검색</div>

                        <div ref={searchRef} style={{ position: 'relative' }}>
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <input
                                    style={{ ...inputStyle, flex: 1 }}
                                    placeholder="곡 제목 또는 아티스트명 입력..."
                                    value={searchQuery}
                                    onChange={e => setSearchQuery(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
                                />
                                <button
                                    onClick={handleSearch}
                                    disabled={isSearching}
                                    style={{ background: '#1DB954', color: '#000', border: 'none', padding: '0 20px', borderRadius: '12px', fontWeight: 800, cursor: 'pointer', fontSize: '14px', whiteSpace: 'nowrap' }}
                                >
                                    {isSearching ? '검색 중...' : '검색'}
                                </button>
                            </div>

                            {showDropdown && (
                                <div style={{
                                    position: 'absolute', top: 'calc(100% + 8px)', left: 0, right: 0,
                                    background: '#161616', borderRadius: '16px',
                                    border: '1px solid rgba(29,185,84,0.25)', zIndex: 200,
                                    boxShadow: '0 25px 60px rgba(0,0,0,0.85)',
                                    maxHeight: '360px', overflowY: 'auto',
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px 6px', borderBottom: '1px solid #222' }}>
                                        <span style={{ fontSize: '11px', color: '#555' }}>{isSearching ? '검색 중...' : `${searchResults.length}개 결과`}</span>
                                        <button onClick={() => setShowDropdown(false)} style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer' }}><X size={14} /></button>
                                    </div>

                                    {isSearching && (
                                        <div style={{ padding: '30px', textAlign: 'center', color: '#555', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
                                            <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> 검색 중...
                                        </div>
                                    )}

                                    {!isSearching && searchResults.length === 0 && (
                                        <div style={{ padding: '30px', textAlign: 'center', color: '#444', fontSize: '13px' }}>
                                            검색 결과가 없습니다.
                                        </div>
                                    )}

                                    {!isSearching && searchResults.map((r: any, idx: number) => (
                                        <div
                                            key={idx}
                                            onClick={() => selectTrack(r)}
                                            style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 14px', borderBottom: '1px solid #1a1a1a', cursor: 'pointer' }}
                                            onMouseEnter={e => (e.currentTarget.style.background = '#1f1f1f')}
                                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                        >
                                            {r.image ? (
                                                <img src={r.image} alt="" style={{ width: 44, height: 44, borderRadius: '8px', objectFit: 'cover' }} />
                                            ) : (
                                                <div style={{ width: 44, height: 44, borderRadius: '8px', background: '#222', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                    <Music size={18} color="#444" />
                                                </div>
                                            )}
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <div style={{ fontWeight: 700, fontSize: '14px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</div>
                                                <div style={{ fontSize: '12px', color: '#1DB954', marginTop: '2px' }}>{r.artist}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {spotifyUrl && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', background: 'rgba(29,185,84,0.06)', padding: '14px', borderRadius: '14px', border: '1px solid rgba(29,185,84,0.2)', marginTop: '16px' }}>
                                {albumArt && <img src={albumArt} alt="" style={{ width: 52, height: 52, borderRadius: '10px', objectFit: 'cover' }} />}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontWeight: 800, fontSize: '16px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{track}</div>
                                    <div style={{ color: '#1DB954', fontSize: '13px', marginTop: '2px' }}>{artist}</div>
                                </div>
                                <button onClick={clearTrack} style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer' }}><X size={16} /></button>
                            </div>
                        )}
                    </div>

                    {/* Genre Card */}
                    <div style={cardStyle}>
                        <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', color: '#555', marginBottom: '12px' }}>🎯 TARGET GENRES</div>
                        <button
                            onClick={() => setShowGenreModal(true)}
                            style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px dashed rgba(29,185,84,0.3)', borderRadius: '12px', padding: '12px 16px', color: '#ccc', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                        >
                            <span>{selectedGenres.length > 0 ? selectedGenres.slice(0, 3).join(', ') + (selectedGenres.length > 3 ? ` 외 ${selectedGenres.length - 3}개` : '') : '장르를 선택하세요...'}</span>
                            <span style={{ background: '#1DB954', color: '#000', padding: '2px 10px', borderRadius: '10px', fontSize: '11px', fontWeight: 800 }}>{selectedGenres.length}개</span>
                        </button>
                    </div>

                    {/* Launch Button */}
                    <button
                        onClick={handleLaunch}
                        disabled={isProcessing || !spotifyUrl}
                        style={{
                            width: '100%', padding: '20px',
                            background: (isProcessing || !spotifyUrl) ? '#333' : 'linear-gradient(135deg, #1DB954, #19a34a)',
                            color: '#000', border: 'none', borderRadius: '18px',
                            fontWeight: 900, fontSize: '18px', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px'
                        }}
                    >
                        {isProcessing ? <Loader2 size={22} style={{ animation: 'spin 1s linear infinite' }} /> : <Rocket size={22} />}
                        {isProcessing ? '진행 중...' : '🚀 LAUNCH SPOTIFY PROMO'}
                    </button>
                </div>

                {/* ── RIGHT PANEL ── */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div style={{ ...cardStyle, minHeight: '400px', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', color: '#555', marginBottom: '16px' }}>피치 페이지 PREVIEW</div>
                        {pitchPageUrl ? (
                            <iframe src={pitchPageUrl} style={{ flex: 1, border: 'none', borderRadius: '12px', background: '#fff' }} title="pitch" />
                        ) : (
                            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#333' }}>
                                캠페인 시작 후 미리보기가 가능합니다.
                            </div>
                        )}
                    </div>
                    <div style={{ background: '#000', borderRadius: '16px', border: '1px solid rgba(29,185,84,0.2)', padding: '16px', maxHeight: '180px', overflowY: 'auto' }}>
                        <div style={{ fontSize: '10px', fontWeight: 800, color: '#1DB954', marginBottom: '8px' }}>CONSOLE</div>
                        {clientLogs.map((l, i) => <div key={i} style={{ fontSize: '11px', color: '#666', fontFamily: 'monospace' }}>{l}</div>)}
                    </div>
                </div>
            </div>

            {/* Modal & Styles same as before with colors adjusted */}
            {showGenreModal && (
                <div onClick={() => setShowGenreModal(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div onClick={e => e.stopPropagation()} style={{ background: '#161616', borderRadius: '24px', padding: '28px', width: '90%', maxWidth: '600px', maxHeight: '80vh', overflowY: 'auto' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                            <h2 style={{ margin: 0 }}>장르 선택</h2>
                            <button onClick={() => setShowGenreModal(false)} style={{ background: '#1DB954', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontWeight: 800 }}>완료</button>
                        </div>
                        <input style={inputStyle} placeholder="장르 검색..." onChange={e => setGenreSearch(e.target.value)} />
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '20px' }}>
                            {filteredGenres.map(g => <button key={g} onClick={() => toggleGenre(g)} style={genreBtnStyle(selectedGenres.includes(g))}>{g}</button>)}
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                @font-face { font-family: 'Outfit'; src: url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;900&display=swap'); }
            `}</style>

            {curators.length > 0 && (
                <div style={{ position: 'fixed', bottom: '40px', right: '40px', zIndex: 1000 }}>
                    <button onClick={() => copyPitchAndOpenGmail(false)} style={{ background: '#1DB954', color: '#000', padding: '16px 32px', borderRadius: '40px', fontWeight: 900, border: 'none', cursor: 'pointer', boxShadow: '0 10px 40px rgba(29,185,84,0.4)' }}>
                        Gmail 발송 ({curators.length}명)
                    </button>
                </div>
            )}
        </div>
    );
}
