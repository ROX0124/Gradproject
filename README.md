# Speech Training Web (speech.vocal-fit.com)

FastAPI 기반 음성 분석 및 훈련 시스템

## 현황

- **목적**: speech.vocal-fit.com 단일 origin FastAPI 웹 서비스
- **배포 환경**: Cloudflare Tunnel (speech-web-dev connector)
- **프론트엔드**: 순수 HTML/JavaScript
- **백엔드**: FastAPI + Whisper (음성 인식)
- **데이터베이스**: SQLite

## 설치

### 1. 저장소 클론
```bash
git clone <repo-url>
cd speech-web
```

### 2. Python 환경 설정 (Python 3.11.9 이상 필요)
```bash
# 가상환경 생성
python -m venv .venv

# 가상환경 활성화
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

> **주의**: `torch` 설치는 시스템 환경에 따라 시간이 걸릴 수 있습니다 (CPU 모드, 약 5-10분).

## 실행

### 로컬 개발 (127.0.0.1:8080)
```bash
uvicorn main:app --host 127.0.0.1 --port 8080
```

그 후 브라우저에서 `http://127.0.0.1:8080` 접속

### 외부 도메인 (speech.vocal-fit.com)
```bash
# FastAPI 서버 실행 (위 명령)
# 별도 터미널에서 Cloudflare Tunnel 시작
cloudflared tunnel run speech-web-dev
```

그 후 `https://speech.vocal-fit.com` 접속

## 프로젝트 구조

```
.
├── main.py                         # FastAPI 메인 애플리케이션
├── index.html                      # 프론트엔드 (inline script 포함)
├── requirements.txt                # Python 의존성
├── voice_analysis(mk7).db          # SQLite 데이터베이스 (생성 후 자동)
├── announcer_voice/                # 앵커 음성 데이터
├── merged_voices_final/            # 병합된 음성 파일 (정적 서빙)
├── temp_audio/                     # 사용자 업로드 임시 오디오
├── temp_drill/                     # 훈련 관련 임시 파일
└── .gitignore                      # Git 제외 목록
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 메인 HTML 페이지 |
| GET | `/api/sentence/random` | 랜덤 문장 조회 |
| POST | `/upload` | 음성 분석 (query: `sentence_id`) |
| GET | `/api/history` | 분석 히스토리 조회 |
| GET | `/api/drill/accumulated-words` | 훈련용 누적 단어 조회 |
| POST | `/api/drill/check` | 발음 검증 |

## 프론트엔드 URL 규칙

**중요**: 모든 fetch 호출은 **상대 경로**를 사용해야 합니다.

```javascript
// ✅ 올바른 예
fetch('/api/sentence/random')
fetch('/upload', { method: 'POST', ... })
fetch('/api/history')

// ❌ 절대 URL 사용 금지
fetch('http://127.0.0.1:8080/api/sentence/random')
fetch('http://localhost:8080/upload')
fetch('https://ngrok-url.io/api/history')
```

이는 Cloudflare Tunnel의 프록시 메커니즘이 상대 경로에 의존하기 때문입니다.

## 로컬 테스트

### 1. FastAPI 서버 실행 확인
```bash
curl http://127.0.0.1:8080/
# 또는
Invoke-WebRequest -Uri http://127.0.0.1:8080/ -Verbose
```

### 2. API 엔드포인트 테스트
```bash
# 랜덤 문장 조회
curl http://127.0.0.1:8080/api/sentence/random

# 히스토리 조회
curl http://127.0.0.1:8080/api/history
```

### 3. 브라우저 DevTools 확인
- F12 → Network 탭 열기
- 모든 API 호출이 `localhost:8080` 기반의 상대 경로여야 함
- 절대 URL(`http://127.0.0.1`, ngrok 등)이 보이면 안 됨

## 외부 도메인 배포 (speech.vocal-fit.com)

### Cloudflare Tunnel 설정

```bash
# 기존 tunnel 확인
cloudflared tunnel list

# 발동 (speech-web-dev 커넥터)
cloudflared tunnel run speech-web-dev
```

**라우팅**: `speech.vocal-fit.com` → `http://127.0.0.1:8080`

### 배포 검증

1. **브라우저 접속**
   ```
   https://speech.vocal-fit.com
   ```

2. **버튼 클릭 후 Network 탭 확인**
   - 상대 경로 API 호출 확인
   - 절대 URL 없음 확인
   - HTTP 200 응답 확인

3. **CloudFlare 문제 해결**
   - 페이지가 로드 안 되면, FastAPI 서버와 cloudflared 모두 실행 중인지 확인
   - `cloudflared` 프로세스 확인 (Windows: `tasklist | findstr cloudflared`)
   - FastAPI 에러 로그 확인

## 주의사항

### 개발 중 캐시 문제

`index.html` 또는 `script.js`를 수정할 때, 브라우저 캐시 때문에 변경이 반영되지 않을 수 있습니다.

**해결책**:
1. **DevTools 캐시 비활성화**
   - F12 → Network 탭 → "Disable cache" 체크

2. **버전 쿼리 추가** (프로덕션)
   ```html
   <script src="script.js?v=20260525"></script>
   ```

3. **No-Cache 헤더** (FastAPI 응답)
   ```python
   response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
   response.headers["Pragma"] = "no-cache"
   ```

### Cloudflare Tunnel 동시 실행 금지

여러 기기에서 동일한 `speech-web-dev` 커넥터를 동시에 실행하면 안 됩니다:

- ❌ 팀원 PC + 정우 Mac 동시 실행 금지
- ✅ 한 사람만 `cloudflared tunnel run speech-web-dev` 실행
- ✅ 다른 사람은 로컬(127.0.0.1:8080) 또는 별도 tunnel 사용

### Token 관리

- Cloudflare tunnel **token은 GitHub에 커밋하지 말 것**
- `.env` 파일에 저장하고 `.gitignore`에 등록
- 공유 필요 시 KakaoTalk/Slack 등 안전한 채널 사용

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| speech.vocal-fit.com 페이지 안 뜸 | FastAPI 미실행 또는 cloudflared 미실행 | `uvicorn main:app --port 8080` + `cloudflared tunnel run speech-web-dev` 확인 |
| 버튼 클릭 시 API 실패 | 절대 URL 사용 또는 캐시 | DevTools Network 탭에서 상대 경로 확인, 캐시 비활성화 |
| 음성 분석 느림 | Whisper 모델 로딩 (첫 실행 시) | 첫 요청 시 3-5분 소요 (CPU 모드) |
| "FastAPI 실행 중인지 확인하세요" 알람 | 백엔드 미응답 | FastAPI 서버 시작, 포트 8080 확인 |

## 개발자 인수인계

자세한 개발 관련 정보는 [SPEECH_DEV_HANDOVER.md](./SPEECH_DEV_HANDOVER.md) 참고

## 라이선스

내부용
