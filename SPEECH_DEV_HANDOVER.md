# Speech-Web 개발자 인수인계 문서

**작성일**: 2026년 5월 25일  
**대상**: 정우 (다음 개발자)  
**상태**: speech.vocal-fit.com 배포 중, API 연결 문제 수정 필요

---

## 1. 프로젝트 개요

### 목적
- **speech.vocal-fit.com**: 단일 origin FastAPI 웹 서비스
- 음성 분석 및 발음 훈련 플랫폼
- Cloudflare Tunnel을 통해 외부 도메인 배포

### 현재 상태
✅ FastAPI 백엔드 정상 실행  
✅ 프론트엔드 UI 기본 로드 성공  
✅ 프론트엔드 API 호출은 같은 origin 상대 경로 사용
✅ SQLite 기본 테이블은 서버 시작 시 자동 생성/보강

### 배포 구조
```
사용자 브라우저
    ↓
https://speech.vocal-fit.com
    ↓
Cloudflare Tunnel (speech-web-dev)
    ↓
http://127.0.0.1:8080 (FastAPI)
```

---

## 2. 실행 환경

### Python 버전
```
3.11.9
```

### 필수 소프트웨어
- Python 3.11+
- pip
- git
- (선택) Cloudflare CLI (`cloudflared`) - 외부 테스트 시만 필요

### 로컬 실행 명령
```bash
# 1. 가상환경 활성화
.venv\Scripts\activate  # Windows
# 또는
source .venv/bin/activate  # macOS/Linux

# 2. FastAPI 서버 실행
uvicorn main:app --host 127.0.0.1 --port 8080
```

### 외부 도메인 테스트 명령
```bash
# 별도 터미널 1: FastAPI
uvicorn main:app --host 127.0.0.1 --port 8080

# 별도 터미널 2: Cloudflare Tunnel
cloudflared tunnel run speech-web-dev

# 브라우저: https://speech.vocal-fit.com
```

---

## 3. 프로젝트 구조

```
speech-web/
├── main.py                          # FastAPI 메인 (엔트리포인트)
├── index.html                       # 프론트엔드 (inline JavaScript 포함)
├── requirements.txt                 # Python 의존성
├── README.md                        # 사용자 설명서
├── SPEECH_DEV_HANDOVER.md          # 본 문서
├── .gitignore                       # Git 제외 설정
├── .git/                            # Git 저장소
│
├── voice_analysis(mk7).db           # SQLite DB (자동 생성)
├── announcer_voice/                 # 앵커 음성 데이터 (미포함)
├── merged_voices_final/             # 병합된 음성 (미포함, 무시)
├── temp_audio/                      # 사용자 업로드 (미포함, 무시)
├── temp_drill/                      # 훈련 임시 (미포함, 무시)
│
├── auto_analyze.py                  # 배치 처리 스크립트 (참고용)
├── db_utils.py                      # DB 유틸리티
├── build_*.py                       # 초기 구성 스크립트
└── ... (기타 처리 스크립트)
```

### GitHub에 포함되지 않는 항목 (.gitignore)
```
.env                    # 환경 변수, Cloudflare token
.venv/, venv/          # 가상환경
__pycache__/           # Python 캐시
*.db, *.sqlite, *.sqlite3  # 실데이터 DB
uploads/, recordings/, temp_audio/, temp_drill/  # 사용자 파일
*.log                  # 로그
cloudflared*, *.pem, *.key  # 보안 관련
```

---

## 4. 주요 API 엔드포인트

### 정의 순서 (FastAPI route 순서 중요!)

```python
# main.py에서 정의 순서:
1. GET  /api/sentence/random        # 랜덤 문장
2. POST /upload                      # 음성 분석
3. GET  /api/history                 # 분석 히스토리
4. GET  /api/drill/accumulated-words # 훈련 단어
5. POST /api/drill/check             # 발음 검증
6. GET  /                            # 메인 페이지 (반드시 마지막!)
```

**중요**: `GET /`은 반드시 **마지막**에 정의해야 합니다. 그렇지 않으면 `/api/*` 라우트가 매칭되지 않습니다.

---

## 5. 프론트엔드 (index.html) - Fetch URL 규칙

### ✅ 올바른 상대 경로 사용
```javascript
// 랜덤 문장 조회
fetch('/api/sentence/random')
  .then(r => r.json())

// 음성 분석 (FormData)
const formData = new FormData();
formData.append('audio', audioBlob, 'audio.webm');
fetch(`/upload?sentence_id=${sentenceId}`, {
  method: 'POST',
  body: formData
})

// 히스토리
fetch('/api/history')

// 발음 검증
fetch('/api/drill/check', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ word: '단어' })
})
```

### ❌ 절대로 금지할 것
```javascript
// 금지: localhost/127.0.0.1
fetch('http://127.0.0.1:8080/api/sentence/random')
fetch('http://localhost:8080/upload')

// 금지: ngrok
fetch('https://abc123.ngrok-free.app/api/history')

// 금지: http 프로토콜 명시
fetch('http://speech.vocal-fit.com/api/sentence/random')
```

### 캐시 버스팅
현재 프론트 로직은 `index.html` inline script에 있으므로 루트 응답에 `Cache-Control: no-store`와 `app-version` 메타를 적용합니다. 나중에 `script.js`나 `style.css`로 분리하면 버전 쿼리를 같이 올리세요.
```html
<script src="script.js?v=20260525-1"></script>
<link rel="stylesheet" href="style.css?v=20260525-1">
```

---

## 6. API/DB 체크리스트

### 정상 조건
- `GET /api/sentence/random` route가 등록되어 있어야 함
- `GET /api/history`는 테이블이 비어 있거나 새 DB여도 500이 아니라 JSON 배열을 반환해야 함
- `POST /upload`와 `GET /api/history`는 같은 `speech_record_table`/`analysis_result_table` schema를 바라봐야 함
- DB 보강은 `CREATE TABLE IF NOT EXISTS`와 누락 컬럼 `ALTER TABLE ADD COLUMN`만 사용하고 기존 데이터를 삭제하지 않음

### 원인 분석 체크리스트

**Step 1: 프론트 코드 검사**
```bash
# index.html에서 절대 URL 검색
grep -i "http://" index.html
grep -i "127.0.0.1" index.html
grep -i "localhost" index.html
grep -i "ngrok" index.html
```
→ 결과가 없어야 함 (모두 상대 경로 `/api/*`, `/upload` 등)

**Step 2: 브라우저 DevTools 확인**
1. DevTools 열기 (F12)
2. Network 탭 → 버튼 클릭
3. 모든 요청이 상대 경로인지 확인
4. 절대 URL 발견 시 → Step 1로 돌아가 fix

**Step 3: 캐시 문제 확인**
- DevTools → Network 탭 → "Disable cache" 체크
- Ctrl+Shift+R (강력한 새로고침)
- 다시 버튼 클릭

**Step 4: FastAPI 서버 상태 확인**
```bash
# 로컬에서
curl http://127.0.0.1:8080/
# 또는
curl http://127.0.0.1:8080/api/sentence/random

# 외부 도메인 (cloudflared 실행 중)
curl https://speech.vocal-fit.com/api/sentence/random
```

**Step 5: Cloudflare Tunnel 상태 확인**
```bash
# 터미널 확인
# "Connected" 메시지 보임?
# 에러 없음?
```

---

## 7. Cloudflare Tunnel 관리

### Token 위치
- ❌ GitHub에 없음 (보안)
- 📁 팀원 PC의 개인 폴더에 저장됨
- 공유 필요 시: Slack/KakaoTalk 등 안전한 채널

### Tunnel 설정
```bash
# 기존 tunnel 확인
cloudflared tunnel list

# speech-web-dev tunnel 발동
cloudflared tunnel run speech-web-dev

# 라우팅 설정 (이미 구성됨)
# speech.vocal-fit.com → http://127.0.0.1:8080
```

### 중요 규칙
⚠️ **동시 실행 금지**
- 팀원 PC와 정우 Mac에서 동시에 `cloudflared tunnel run speech-web-dev` 실행 금지
- 여러 기기에서 동시 연결 시 트래픽 섞임 위험

✅ **올바른 워크플로우**
1. 정우가 수정 시: 정우 Mac에서만 `cloudflared tunnel run speech-web-dev` 실행
2. 정우 수정 완료 후: `cloudflared` 종료
3. 팀원이 다시 개발 시: 팀원 PC에서 `cloudflared tunnel run speech-web-dev` 실행

---

## 8. 의존성 설치

### requirements.txt
```
fastapi==0.136.1
uvicorn==0.46.0
openai-whisper==20250625
torch==2.7.1
torchaudio==2.7.1
requests==2.33.1
python-multipart==0.0.26
pandas==3.0.2
```

### 설치 명령
```bash
pip install -r requirements.txt
```

⏱️ **시간 소요**: 약 5-10분 (torch 설치)

---

## 9. 개발 시 주의사항

### Fetch URL 변경 금지 사항
❌ **절대 하지 말 것**
```javascript
// 1. localhost로 변경 금지
const API_BASE = "http://127.0.0.1:8080"  // 금지!

// 2. ngrok 사용 금지
fetch("https://abc123.ngrok-free.app/...")  // 금지!

// 3. 절대 경로 사용 금지
fetch("http://speech.vocal-fit.com/...")  // 금지!
```

✅ **반드시 사용할 것**
```javascript
// 상대 경로만
fetch('/api/sentence/random')
fetch('/upload', { method: 'POST', ... })
fetch('/api/history')
```

### FastAPI 포트 변경 금지
❌ 8080 이외의 포트 사용 금지

### Cloudflare 설정 변경 금지
❌ speech.vocal-fit.com 라우팅 재설정 금지

---

## 10. 팀원이 다시 개발할 때 (인수인계 후)

### 준비 체크리스트
- [ ] 정우의 수정사항 pull 받음
- [ ] `pip install -r requirements.txt` 실행 (변경 있는 경우)
- [ ] FastAPI 재시작: `uvicorn main:app --host 127.0.0.1 --port 8080`
- [ ] Cloudflare 재시작: `cloudflared tunnel run speech-web-dev`
- [ ] https://speech.vocal-fit.com 접속 확인

### 트러블슈팅
| 문제 | 확인사항 |
|------|---------|
| 페이지 안 뜸 | FastAPI/cloudflared 실행 확인 |
| API 호출 실패 | fetch URL이 상대 경로인지 확인 |
| 음성 인식 안 됨 | Whisper 모델 로딩 완료 확인 (첫 요청 3-5분) |
| DB 오류 | voice_analysis(mk7).db 파일 확인 |

---

## 11. 파일별 담당자 정보

| 파일 | 목적 | 마지막 수정 |
|------|------|-----------|
| `main.py` | FastAPI 백엔드 | 2026-05-25 |
| `index.html` | 프론트엔드 UI + JavaScript | 2026-05-25 |
| `requirements.txt` | 의존성 (새로 생성) | 2026-05-25 |
| `.gitignore` | Git 제외 (업데이트) | 2026-05-25 |
| `README.md` | 사용자 문서 (새로 생성) | 2026-05-25 |

---

## 12. 연락처 & 질문

- **기술 질문**: 팀원에게 Slack/KakaoTalk 연락
- **Cloudflare Token 필요**: 팀원에게 요청 (GitHub 아님!)
- **급한 문제**: DevTools Network 탭 스크린샷과 함께 보고

---

**문서 버전**: v1.0  
**최종 검토**: 2026-05-25
