import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import ctypes

# WinError 1114 강제 해결을 위한 코드 (파일 최상단에 추가)
try:
    # 가상환경 내 torch lib 폴더 경로를 직접 지정
    dll_path = r"C:/Users/user/Gradproject/.venv/Lib/site-packages/torch/lib/c10.dll"
    if os.path.exists(dll_path):
        # 시스템에 해당 DLL을 미리 로드하도록 명령
        ctypes.WinDLL(dll_path)
except Exception as e:
    print(f"DLL 로드 시도 중 알림: {e}")

import shutil
import sqlite3
import whisper  # faster_whisper 대신 오리지널 라이브러리 사용
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="음성 분석 시스템 API")

# 합쳐진 파일들이 저장된 실제 폴더 이름
MERGED_DIR = "merged_voices_final"
if not os.path.exists(MERGED_DIR):
    os.makedirs(MERGED_DIR)

# 웹에서 /announcer_audio 라는 주소로 접속하면 MERGED_DIR 안의 파일을 보여줌
app.mount("/announcer_audio", StaticFiles(directory=MERGED_DIR), name="announcer_audio")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 말씀하신 최신 DB 파일 이름
DB_PATH = "voice_analysis(mk7).db"

# 오리지널 Whisper 모델 로드 (가장 안전한 base 모델 + CPU 환경 강제 지정)
print("오리지널 Whisper 모델 로드 중...")
model = whisper.load_model("base", device="cpu")
# model = whisper.load_model("medium", device="cpu")
# model = whisper.load_model("large-v3", device="cpu")
print("오리지널 Whisper 모델 로드 완벽하게 성공!")

# --- [모듈] CER(조음 정확도) 계산 함수 ---
def calculate_cer(reference, hypothesis):
    ref = reference.replace(" ", "").strip()
    hyp = hypothesis.replace(" ", "").strip()
    
    n = len(ref)
    if n == 0: return 0.0
    
    rows = n + 1
    cols = len(hyp) + 1
    distance = [[0] * cols for _ in range(rows)]
    for i in range(1, rows): distance[i][0] = i
    for j in range(1, cols): distance[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            if ref[i-1] == hyp[j-1]:
                distance[i][j] = distance[i-1][j-1]
            else:
                distance[i][j] = min(distance[i-1][j], distance[i][j-1], distance[i-1][j-1]) + 1
    
    cer = distance[n][len(hyp)] / n
    return cer

@app.get("/")
async def read_index():
    # 같은 폴더에 있는 index.html 파일을 읽어서 보여줍니다.
    return FileResponse("index.html")

# --- [API 1] 랜덤 문장 가져오기 ---
@app.get("/api/sentence/random")
def get_random_sentence():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sentence_id, news_id, paragraph_seq, text FROM sentence_table ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row: return dict(row)
    raise HTTPException(status_code=404, detail="문장이 없습니다.")

# --- [API 2] 음성 업로드 및 분석 ---
@app.post("/upload")
async def upload_audio(
    sentence_id: int = Query(..., description="비교할 문장의 ID"), 
    file: UploadFile = File(...)
):
    # 파일 저장 로직
    if not os.path.exists("temp_audio"): os.makedirs("temp_audio")
    file_path = f"temp_audio/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 1. 오리지널 Whisper 음성 인식 (파라미터 호환성 수정)
    result = model.transcribe(
        file_path, 
        language="ko", 
        word_timestamps=True,
        temperature=0.0,
        no_speech_threshold=0.0, 
        logprob_threshold=-1.0,  
        compression_ratio_threshold=2.4, 
        condition_on_previous_text=False 
    )
    
    segments = result.get("segments", [])
    recognized_text = result.get("text", "").strip()
    
    # 2. 정밀 침묵 분석 (오리지널 버전에 맞춰 Dictionary 접근 방식으로 변경)
    total_duration = 0.0
    total_spoken_time = 0.0 
    total_silence = 0.0 
    words_data = []

    for segment in segments:
        if "words" in segment:
            words_data.extend(segment["words"])

    if words_data:
        total_duration = words_data[-1]["end"]
        
        for word in words_data:
            total_spoken_time += (word["end"] - word["start"])
        
        total_silence = total_duration - total_spoken_time
        total_silence = max(0.0, total_silence)
                
    silence_ratio = round(total_silence / total_duration, 4) if total_duration > 0 else 0.0

    # 3. DB에서 기준 문장 가져오기
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM sentence_table WHERE sentence_id = ?", (sentence_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: raise HTTPException(status_code=404, detail="문장 없음")
    reference_text = row[0]

    # 4. 종합 지표 계산
    cer_val = calculate_cer(reference_text, recognized_text)
    articulation_score = max(0, 1 - cer_val)

    syllable_count = len(recognized_text.replace(" ", "").strip())
    speech_rate = round(syllable_count / total_duration, 2) if total_duration > 0 else 0.0
    
    if 4 <= speech_rate <= 7:
        rate_score = 1.0
    else:
        rate_score = max(0, 1.0 - abs(speech_rate - 5.5) * 0.1)

    clarity_score = (articulation_score * 0.5) + (rate_score * 0.3) + ((1 - silence_ratio) * 0.2)

    # 5. DB에 녹음 기록과 분석 결과 저장하기
    record_id = None

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM user_table WHERE user_id = 1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO user_table (user_id, total_score) VALUES (1, 0.0)")

        test_user_id = 1 
        
        cursor.execute("""
            INSERT INTO speech_record_table (user_id, sentence_id, audio_path)
            VALUES (?, ?, ?)
        """, (test_user_id, sentence_id, file_path))
        
        record_id = cursor.lastrowid 

        cursor.execute("""
                INSERT INTO analysis_result_table 
                (record_id, original_text, recognized_text, cer_score, speech_rate, silence_ratio, clarity_score) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (record_id, reference_text, recognized_text, round(cer_val, 4), speech_rate, silence_ratio, round(clarity_score, 2)))
        
        conn.commit()
        
    except Exception as e:
        print(f"🔥 DB 저장 중 에러 발생: {e}")
    finally:
        conn.close()

    if record_id is None:
        raise HTTPException(status_code=500, detail="DB 저장에 실패했습니다.")


# --- [수정된 부분] 6. 아나운서 음성 파일 경로 자동 찾기 ---
    paragraph = str(sentence_id)
    announcer_url = None
    
    # 폴더 안에 있는 모든 파일을 뒤져서, 이름이 '_{sentence_id}.wav'로 끝나는 파일을 찾습니다.
    target_suffix = f"_{paragraph}.wav"
    
    if os.path.exists(MERGED_DIR):
        for filename in os.listdir(MERGED_DIR):
            if filename.endswith(target_suffix):
                announcer_url = f"/announcer_audio/{filename}"
                print(f"✅ 아나운서 파일 자동 매칭 성공!: {filename}")
                break
                
    if not announcer_url:
        print(f"❌ 아나운서 파일을 찾지 못했습니다. (찾으려는 단락 번호: {paragraph})")
    
    # 7. 결과 반환 (announcer_voice_url 추가됨!)
    return {
        "record_id": record_id,
        "message": "분석 및 DB 저장 완료",
        "announcer_voice_url": announcer_url, # 👈 프론트엔드가 사용할 URL
        "analysis_results": {
            "sentence_id": sentence_id,
            "reference_text": reference_text,
            "recognized_text": recognized_text,
            "metrics": {
                "articulation_accuracy": f"{round(articulation_score * 100, 2)}%",
                "speech_rate": f"{speech_rate} 음절/초",
                "silence_ratio": f"{round(silence_ratio * 100, 2)}%",
                "clarity_score": f"{round(clarity_score * 100, 2)}점"
            },
            "duration": f"{round(total_duration, 2)}초",
            "total_silence_time": f"{round(total_silence, 2)}초"
        }
    }

# --- [API 3] 과거 기록 리스트 가져오기 ---
@app.get("/api/history")
def get_history():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.record_id, s.text as original_text, a.clarity_score, a.recognized_text, r.created_at
        FROM speech_record_table r
        JOIN sentence_table s ON r.sentence_id = s.sentence_id
        JOIN analysis_result_table a ON r.record_id = a.record_id
        ORDER BY r.created_at DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
