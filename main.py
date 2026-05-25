import os
import glob
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import ctypes
import re

try:
    dll_path = r"C:/Users/user/Gradproject/venv/Lib/site-packages/torch/lib/c10.dll"
    if os.path.exists(dll_path):
        ctypes.WinDLL(dll_path)
except Exception as e:
    print(f"DLL 로드 시도 중 알림: {e}")

import shutil
import sqlite3
import difflib
import json
import whisper
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="음성 분석 시스템 API")

MERGED_DIR = "merged_voices_final"
if not os.path.exists(MERGED_DIR):
    os.makedirs(MERGED_DIR)

app.mount("/announcer_audio", StaticFiles(directory="merged_voices_final"), name="announcer_audio")
# 사용자 업로드 오디오 정적 서빙
USER_AUDIO_DIR = "temp_audio"
if not os.path.exists(USER_AUDIO_DIR):
    os.makedirs(USER_AUDIO_DIR)
app.mount("/user_audio", StaticFiles(directory=USER_AUDIO_DIR), name="user_audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "voice_analysis(mk7).db"

print("오리지널 Whisper 모델 로드 중 (CPU 모드 유지)...")
model = whisper.load_model("large-v3", device="cpu")
print("오리지널 Whisper 모델 로드 완벽하게 성공!")


# --- [모듈] 텍스트 정규화 ---
def normalize_text(text):
    exceptions = {
        "19극복": "일구극복",
        "apple": "애플",
        "who": "더블유에이치오",
    }
    for k, v in exceptions.items():
        text = re.sub(k, v, text, flags=re.IGNORECASE)

    # 숫자 읽기 헬퍼들 (공유)
    digit_kor = ['영','일','이','삼','사','오','육','칠','팔','구']

    def digits_separate(s):
        return ''.join(digit_kor[int(d)] for d in s)

    def four_digit_chunk_to_sino(chunk):
        units = ['천','백','십','']
        res = ''
        chunk = chunk.zfill(4)
        for i, ch in enumerate(chunk):
            d = int(ch)
            if d == 0: continue
            u = units[i]
            if d == 1 and u != '':
                res += u
            else:
                res += digit_kor[d] + u
        return res

    def number_to_sino(n):
        if n == 0:
            return '영'
        higher = ['', '만', '억', '조', '경']
        s = str(n)
        parts = []
        while s:
            parts.append(s[-4:])
            s = s[:-4]
        res_parts = []
        for idx, part in enumerate(parts):
            part_num = int(part)
            if part_num == 0:
                res_parts.append('')
                continue
            chunk = four_digit_chunk_to_sino(part)
            if chunk:
                res_parts.append(chunk + higher[idx])
            else:
                res_parts.append('')
        return ''.join(reversed([p for p in res_parts if p]))

    def convert_measurements(match):
        num_str = match.group(1)
        unit_str = match.group(2).lower()
        unit_dict = {
            'kg': '킬로그램', 'km': '킬로미터', 'cm': '센티미터', 'mm': '밀리미터',
            'm': '미터', 'g': '그램', 'mg': '밀리그램', 'ml': '밀리리터', 'l': '리터',
            '%': '퍼센트'
        }
        try:
            n = int(num_str)
            return number_to_sino(n) + unit_dict[unit_str]
        except Exception:
            return num_str + unit_dict[unit_str]

    text = re.sub(r'(\d+)\s*(kg|km|cm|mm|m|g|mg|ml|l|%)(?![a-zA-Z])', convert_measurements, text, flags=re.IGNORECASE)

    def convert_eng_to_korean(match):
        eng_str = match.group().upper()
        eng_to_kor_dict = {
            'A': '에이', 'B': '비', 'C': '씨', 'D': '디', 'E': '이', 'F': '에프', 'G': '지',
            'H': '에이치', 'I': '아이', 'J': '제이', 'K': '케이', 'L': '엘', 'M': '엠',
            'N': '엔', 'O': '오', 'P': '피', 'Q': '큐', 'R': '알', 'S': '에스', 'T': '티',
            'U': '유', 'V': '브이', 'W': '더블유', 'X': '엑스', 'Y': '와이', 'Z': '제트'
        }
        return "".join(eng_to_kor_dict.get(char, char) for char in eng_str)

    text = re.sub(r'[A-Za-z]+', convert_eng_to_korean, text)

    def convert_smart_number(match):
        num_str = match.group(1)
        unit = match.group(2)
        num = int(num_str)
        native_units = ['명', '개', '번', '살', '마리', '시간', '달', '군데', '가지', '근', '평', '자', '척', '편']
        # reuse shared helpers defined above: digits_separate, number_to_sino

        # If unit is a native counting unit and number < 100, use native Korean counters
        if unit in native_units:
            native_ones = ["","한","두","세","네","다섯","여섯","일곱","여덟","아홉"]
            native_tens = ["","열","스물","서른","마흔","쉰","예순","일흔","여든","아흔"]
            if 1 <= num < 100:
                # handle e.g., 21 -> 스물한개
                return (native_tens[num // 10] + native_ones[num % 10]) + unit

        # If there is a measurement/unit like m, kg, cm etc, convert full sino reading
        measurement_units = {'kg':'킬로그램','km':'킬로미터','cm':'센티미터','mm':'밀리미터','m':'미터','g':'그램','mg':'밀리그램','ml':'밀리리터','l':'리터','%':'퍼센트'}
        if unit.lower() in measurement_units:
            return number_to_sino(num) + measurement_units[unit.lower()]

        # For short standalone numbers (1-2 digits) not followed by a measurement, read digits separately (identifier style)
        if len(num_str) <= 2:
            return digits_separate(num_str) + unit

        # Default: full sino reading + unit
        return number_to_sino(num) + unit

    text = re.sub(r'(\d+)([가-힣]?)', convert_smart_number, text)
    return re.sub(r'[^\w\s]', '', text).strip()


# --- [모듈] CER 계산 ---
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


# --- [모듈] 단어 단위 정밀 비교 ---
def get_detailed_comparison(reference, recognized):
    ref_words = normalize_text(reference).split()
    ref_chars = normalize_text(reference).replace(" ", "")
    rec_chars = normalize_text(recognized).replace(" ", "")
    matcher = difflib.SequenceMatcher(None, ref_chars, rec_chars)
    char_status = [{"error": False, "said": ""} for _ in range(len(ref_chars))]
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                char_status[i1 + k]["said"] = rec_chars[j1 + k]
        elif tag == 'replace':
            said_chunk = rec_chars[j1:j2]
            for k in range(i1, i2):
                char_status[k]["error"] = True
                char_status[k]["said"] = said_chunk if k == i1 else ""
        elif tag == 'delete':
            for k in range(i1, i2):
                char_status[k]["error"] = True
    comparison_map = []
    error_words = []
    current_idx = 0
    for word in ref_words:
        word_len = len(word)
        has_error = False
        said_parts = []
        for i in range(current_idx, current_idx + word_len):
            if char_status[i]["error"]:
                has_error = True
            if char_status[i]["said"]:
                said_parts.append(char_status[i]["said"])
        said_word = "".join(said_parts)
        if has_error:
            error_words.append(word)
            if not said_word:
                comparison_map.append({"word": word, "status": "missing"})
            else:
                comparison_map.append({"word": word, "status": "wrong", "said": said_word})
        else:
            comparison_map.append({"word": word, "status": "correct"})
        current_idx += word_len
    return error_words, comparison_map





# --- [API 1] 랜덤 문장 가져오기 ---
def get_random_sentence():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sentence_id, news_id, paragraph_seq, text, guided_text FROM sentence_table ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="문장이 없습니다.")
    data = dict(row)
    sentence_id = data['sentence_id']
    data['announcer_voice_url'] = None
    if os.path.exists(MERGED_DIR):
        for filename in os.listdir(MERGED_DIR):
            if filename.endswith(f"_{sentence_id}.wav") or filename.endswith(f"_{str(sentence_id).zfill(2)}.wav"):
                import time
                data['announcer_voice_url'] = f"/announcer_audio/{filename}?t={int(time.time())}"
                print(f"✅ [랜덤] 찰떡 매칭 성공!: {filename} (문장 ID: {sentence_id})")
                break
    if not data['announcer_voice_url']:
        print(f"❌ [랜덤] 문장 ID {sentence_id}번의 오디오 파일을 폴더에서 찾을 수 없습니다.")
    return data


# --- [API 2] 음성 업로드 및 분석 ---
@app.post("/upload")
async def upload_audio(
    sentence_id: int = Query(..., description="비교할 문장의 ID"),
    file: UploadFile = File(...)
):
    if not os.path.exists("temp_audio"): os.makedirs("temp_audio")
    file_path = f"temp_audio/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT text, anchor_duration, anchor_silence_timestamps
        FROM sentence_table
        WHERE sentence_id = ?
    """, (sentence_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: raise HTTPException(status_code=404, detail="문장 없음")

    reference_text = row[0]
    anchor_duration = row[1] or 0.0
    anchor_silence_data = row[2]

    result = model.transcribe(
        file_path,
        language="ko",
        word_timestamps=True,
        condition_on_previous_text=False,
        temperature=0.0
    )
    segments = result.get("segments", [])
    words_data = []
    for segment in segments:
        if "words" in segment:
            words_data.extend(segment["words"])

    user_timestamps = []
    recognized_text = ""
    if words_data:
        word_texts = []
        for w in words_data:
            txt = w.get("word") or w.get("text") or w.get("word_text")
            if txt:
                clean_word = txt.strip()
                word_texts.append(clean_word)
                user_timestamps.append({
                    "word": clean_word,
                    "start": round(w["start"], 2),
                    "end": round(w["end"], 2)
                })
        recognized_text = " ".join(word_texts).strip()
    else:
        recognized_text = result.get("text", "").strip()

    total_duration = 0.0
    total_spoken_time = 0.0
    total_silence = 0.0
    if words_data:
        total_duration = words_data[-1]["end"]
        for word in words_data:
            total_spoken_time += (word["end"] - word["start"])
        total_silence = max(0.0, total_duration - total_spoken_time)
    silence_ratio = round(total_silence / total_duration, 4) if total_duration > 0 else 0.0

    anchor_silence = 0.0
    if anchor_silence_data:
        try:
            silence_dict = json.loads(anchor_silence_data)
            anchor_silence = silence_dict.get("total_silence", 0.0)
        except Exception:
            pass

    cer_val = calculate_cer(reference_text, recognized_text)
    articulation_score = max(0, 1 - cer_val)
    syllable_count = len(recognized_text.replace(" ", "").strip())
    speech_rate = round(syllable_count / total_duration, 2) if total_duration > 0 else 0.0
    if 4 <= speech_rate <= 7:
        rate_score = 1.0
    else:
        rate_score = max(0, 1.0 - abs(speech_rate - 5.5) * 0.1)
    clarity_score = (articulation_score * 0.5) + (rate_score * 0.3) + ((1 - silence_ratio) * 0.2)

    error_words, comparison_map = get_detailed_comparison(reference_text, recognized_text)

    feedback_parts = []
    if articulation_score >= 0.95:
        feedback_parts.append("🎖️ <b>[발음 정밀 진단]</b> 아나운서 수준의 완벽한 조음 정확도입니다. 모든 자음과 모음의 종성(받침) 처리가 매우 명확하게 전달되었습니다.")
    elif articulation_score >= 0.80:
        example = f"'{error_words[0]}'" if error_words else "일부 구간"
        feedback_parts.append(f"😊 <b>[발음 정밀 진단]</b> 전반적인 흐름은 양호하나, 복합 자음이 포함된 {example} 등에서 조음이 다소 뭉개지는 경향이 있습니다. 입술 근육을 확장하여 한 글자씩 또박또박 짚어주는 연습을 권장합니다.")
    else:
        feedback_parts.append("⚠️ <b>[발음 정밀 진단]</b> 발음 뭉개짐 및 오인식 구간이 다수 발견됩니다. 낭독 속도를 늦추고, '아-에-이-오-우' 조음 기관 스트레칭 후 단어 단위로 끊어 읽는 기본기 훈련부터 다시 시작해 보세요.")

    # 🎯 [모듈 B 고도화] 아나운서 속도 연동 메트로놈 목표 BPM 산출 로직 적용
    target_bpm = 95
    if anchor_duration > 0:
        # 아나운서 속도 측정 (순수 한글 글자수 / 아나운서 발화 시간)
        pure_ref_text = re.sub(r'[^가-힣]', '', reference_text)
        ref_syllable_count = len(pure_ref_text)
        announcer_speech_rate = round(ref_syllable_count / anchor_duration, 2)
        
        # 아나운서 속도 기반 BPM 도출 (초당 음절수 * 20)
        target_bpm = int(round(announcer_speech_rate * 20))
        target_bpm = max(70, min(target_bpm, 130))  # BPM 제한 범위 (너무 빠르거나 느려짐 방지)
        
        rate_difference = round(speech_rate - announcer_speech_rate, 2)
        
        if rate_difference > 0.8:
            feedback_parts.append(f"🐇 <b>[완급 조절 진단]</b> 아나운서의 페이스(초당 {announcer_speech_rate}음절)에 비해 사용자님의 속도가 대단히 급합니다. 완벽한 전달력을 위해 아나운서의 실제 호흡 페이스를 복제한 <strong style='color:#e74c3c;'>{target_bpm} BPM 메트로놈 훈련</strong>을 추천합니다.")
        elif rate_difference < -0.8:
            feedback_parts.append(f"🐢 <b>[완급 조절 진단]</b> 아나운서의 페이스(초당 {announcer_speech_rate}음절)에 비해 낭독이 다소 무겁고 처집니다. 목소리에 탄력을 불어넣을 수 있도록 아나운서 맞춤형 속도인 <strong style='color:#2ecc71;'>{target_bpm} BPM 메트로놈 훈련</strong>을 추천합니다.")
        else:
            feedback_parts.append(f"⏱️ <b>[완급 조절 진단]</b> 훌륭합니다! 아나운서의 발화 속도(초당 {announcer_speech_rate}음절)와 거의 완벽하게 일치하는 안정적인 유창성을 보여주고 있습니다. <strong style='color:#3498db;'>{target_bpm} BPM 템포 유지 훈련</strong>을 지속해 보세요.")
    else:
        # 기준 아나운서 음성이 없거나 길이가 0일 때의 기본 진단
        if 4.5 <= speech_rate <= 6.0:
            feedback_parts.append(f"⏱️ <b>[속도 정밀 진단]</b> 현재 초당 {speech_rate}음절로 안정적인 뉴스 낭독 속도를 유지하고 있습니다. 완벽한 안정감을 위해 <strong style='color:#3498db;'>{target_bpm} BPM 템포 유지 훈련</strong>을 추천합니다.")
        elif speech_rate > 6.0:
            target_bpm = 80
            feedback_parts.append(f"🐇 <b>[속도 정밀 진단]</b> 현재 초당 {speech_rate}음절로 발화 속도가 다소 빠릅니다. 차분하게 읽기 위해 <strong style='color:#e74c3c;'>{target_bpm} BPM 메트로놈 훈련</strong>을 진행해 보세요.")
        else:
            target_bpm = 105
            feedback_parts.append(f"🐢 <b>[속도 정밀 진단]</b> 현재 초당 {speech_rate}음절로 발화 속도가 느린 편입니다. 비트에 탄력을 붙이기 위해 <strong style='color:#2ecc71;'>{target_bpm} BPM 메트로놈 훈련</strong>을 진행해 보세요.")

    if anchor_silence > 0:
        diff_silence = total_silence - anchor_silence
        if diff_silence > 1.5 or silence_ratio > 0.25:
            feedback_parts.append(f"⏸️ <b>[호흡 정밀 진단]</b> 불필요한 공백이 아나운서 대비 약 {abs(round(diff_silence, 1))}초 길게 감지되었습니다.")
        else:
            feedback_parts.append("💨 <b>[호흡 정밀 진단]</b> 의미 구절에 따른 끊어 읽기와 숨결 처리가 아나운서의 호흡 패턴과 매우 유사하여 안정적인 흐름을 만듭니다.")
    else:
        if silence_ratio > 0.25:
            feedback_parts.append("⏸️ <b>[호흡 정밀 진단]</b> 문장 사이사이 빈 공간(Silence)의 비중이 다소 높아 낭독이 자주 끊기는 느낌을 줍니다.")
        else:
            feedback_parts.append("💨 <b>[호흡 정밀 진단]</b> 적절한 구간에서 호흡을 끊어 읽어 청자에게 텍스트가 안정적으로 전달됩니다.")

    feedback_message = "<br><br>".join(feedback_parts)

    # 아나운서 URL 계산 (DB 저장 전)
    announcer_url = None
    if os.path.exists(MERGED_DIR):
        for filename in os.listdir(MERGED_DIR):
            if filename.endswith(f"_{sentence_id}.wav") or filename.endswith(f"_{str(sentence_id).zfill(2)}.wav"):
                announcer_url = f"/announcer_audio/{filename}"
                print(f"✅ [결과창] 찰떡 매칭 성공!: {filename} (문장 ID: {sentence_id})")
                break
    if not announcer_url:
        print(f"❌ [결과창] 문장 ID {sentence_id}번의 오디오 파일을 찾지 못했습니다.")

    # 포맷된 값 미리 계산
    articulation_accuracy_fmt = f"{round(articulation_score * 100, 2)}%"
    speech_rate_fmt = f"{speech_rate} 음절/초"
    silence_ratio_fmt = f"{round(silence_ratio * 100, 2)}%"
    clarity_score_fmt = f"{round(clarity_score * 100, 2)}점"
    duration_fmt = f"{round(total_duration, 2)}초"

    record_id = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1) 먼저 speech_record_table에 오디오 기록을 남기고 record_id를 확보
        try:
            cursor.execute(
                "INSERT INTO speech_record_table (user_id, sentence_id, audio_path) VALUES (?, ?, ?)",
                (None, sentence_id, file_path)
            )
            speech_record_id = cursor.lastrowid
        except Exception:
            speech_record_id = None

        # 2) analysis_result_table에 필요한 컬럼이 없으면 추가(안전성 목적)
        columns_to_add = [
            ("cer_score", "REAL"),
            ("speech_rate", "REAL"),
            ("silence_ratio", "REAL"),
            ("clarity_score", "REAL"),
            ("duration", "REAL"),
            ("comparison_map", "TEXT"),
            ("user_timestamps", "TEXT"),
            ("announcer_voice_url", "TEXT"),
            ("user_voice_url", "TEXT"),
            ("articulation_accuracy_fmt", "TEXT"),
            ("speech_rate_fmt", "TEXT"),
            ("silence_ratio_fmt", "TEXT"),
            ("clarity_score_fmt", "TEXT"),
            ("duration_fmt", "TEXT"),
            ("original_text", "TEXT"),
            ("target_bpm", "INTEGER")  # 👈 DB에 BPM 저장 컬럼 추가
        ]
        for col, ctype in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE analysis_result_table ADD COLUMN {col} {ctype}")
            except Exception:
                pass

        # 3) analysis_result_table에 삽입 (speech_record_id가 있으면 record_id로 연결)
        user_audio_url = f"/user_audio/{os.path.basename(file_path)}"
        insert_cols = [
            "record_id",
            "original_text", "recognized_text",
            "cer_score", "speech_rate", "silence_ratio", "clarity_score",
            "error_words", "feedback_message", "duration",
            "comparison_map", "user_timestamps", "announcer_voice_url",
            "user_voice_url",
            "articulation_accuracy_fmt", "speech_rate_fmt",
            "silence_ratio_fmt", "clarity_score_fmt", "duration_fmt",
            "target_bpm" # 👈 insert 컬럼 목록에 추가
        ]
        placeholders = ",".join(["?"] * len(insert_cols))
        cursor.execute(f"INSERT INTO analysis_result_table ({', '.join(insert_cols)}) VALUES ({placeholders})", (
            speech_record_id,
            reference_text, recognized_text,
            round(cer_val, 4), speech_rate, silence_ratio, round(clarity_score, 4),
            json.dumps(error_words, ensure_ascii=False),
            feedback_message,
            round(total_duration, 2),
            json.dumps(comparison_map, ensure_ascii=False),
            json.dumps(user_timestamps, ensure_ascii=False),
            announcer_url,
            user_audio_url,
            articulation_accuracy_fmt, speech_rate_fmt,
            silence_ratio_fmt, clarity_score_fmt, duration_fmt,
            target_bpm # 👈 insert 값에 추가
        ))

        conn.commit()
        record_id = speech_record_id if speech_record_id is not None else cursor.lastrowid
    finally:
        conn.close()

    if record_id is None:
        raise HTTPException(status_code=500, detail="DB 저장에 실패했습니다.")

    return {
        "record_id": record_id,
        "message": "분석 및 DB 저장 완료",
        "announcer_voice_url": announcer_url,
        "user_voice_url": user_audio_url,
        "target_bpm": target_bpm, # 👈 프론트엔드로 보내기 위해 반환값 추가
        "analysis_results": {
            "sentence_id": sentence_id,
            "reference_text": reference_text,
            "recognized_text": recognized_text,
            "error_words": error_words,
            "comparison_map": comparison_map,
            "feedback_message": feedback_message,
            "user_timestamps": user_timestamps,
            "anchor_timestamps": anchor_silence_data,
            "metrics": {
                "articulation_accuracy": articulation_accuracy_fmt,
                "speech_rate": speech_rate_fmt,
                "silence_ratio": silence_ratio_fmt,
                "clarity_score": clarity_score_fmt
            },
            "duration": duration_fmt,
            "total_silence_time": f"{round(total_silence, 2)}초"
        }
    }


# --- [API 3] 단어 집중 교정 (드릴) ---
@app.post("/api/drill/check")
async def check_drill(
    target_word: str = Query(..., description="교정 목표 단어"),
    file: UploadFile = File(...)
):
    if not os.path.exists("temp_drill"):
        os.makedirs("temp_drill")
    file_path = f"temp_drill/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    result = model.transcribe(file_path, language="ko", temperature=0.0)
    recognized_text = normalize_text(result.get("text", "").strip())
    normalized_target = normalize_text(target_word).strip()
    is_match = (recognized_text == normalized_target) or (normalized_target in recognized_text)
    return {
        "status": "success",
        "match": is_match,
        "recognized": recognized_text,
        "target": normalized_target
    }


# --- [API 4] 과거 기록 조회 ---
@app.get("/api/history")
def get_history():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            r.record_id, s.text as original_text, a.*, r.created_at
        FROM speech_record_table r
        JOIN sentence_table s ON r.sentence_id = s.sentence_id
        JOIN analysis_result_table a ON r.record_id = a.record_id
        ORDER BY r.created_at DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        row_dict = dict(row)
        for key in ['error_words', 'comparison_map', 'user_timestamps']:
            if row_dict.get(key):
                try: row_dict[key] = json.loads(row_dict[key])
                except: row_dict[key] = []

        cer = row_dict.get('cer_score', 0) or 0
        articulation_score = max(0, 1 - cer)
        speech_rate_raw = row_dict.get('speech_rate', 0) or 0
        silence_ratio_raw = row_dict.get('silence_ratio', 0) or 0
        clarity_raw = row_dict.get('clarity_score', 0) or 0
        duration_raw = row_dict.get('duration', 0) or 0

        row_dict['metrics'] = {
            "articulation_accuracy": row_dict.get('articulation_accuracy_fmt') or f"{round(articulation_score * 100, 2)}%",
            "speech_rate":           row_dict.get('speech_rate_fmt')           or f"{speech_rate_raw} 음절/초",
            "silence_ratio":         row_dict.get('silence_ratio_fmt')         or f"{round(silence_ratio_raw * 100, 2)}%",
            "clarity_score":         row_dict.get('clarity_score_fmt')         or f"{round(clarity_raw * 100, 2)}점"
        }
        row_dict['duration_formatted'] = row_dict.get('duration_fmt') or f"{duration_raw}초"

        result.append(row_dict)
    return result


# ✅ [신규 API 5] 누적 오답 단어 조회
@app.get("/api/drill/accumulated-words")
def get_accumulated_drill_words(exclude: str = Query("", description="제외할 단어들 (쉼표 구분)")):
    """
    DB에 저장된 모든 분석 기록의 error_words를 수집하여
    중복 제거 후 반환합니다. exclude 파라미터로 현재 세션 단어를 제외할 수 있습니다.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT error_words FROM analysis_result_table WHERE error_words IS NOT NULL AND error_words != '[]'")
    rows = cursor.fetchall()
    conn.close()

    # 제외 단어 목록 파싱
    exclude_set = set(w.strip() for w in exclude.split(",") if w.strip()) if exclude else set()

    # 전체 오답 단어 누적 (순서 유지 + 중복 제거)
    seen = set()
    accumulated = []
    for (error_words_json,) in rows:
        try:
            words = json.loads(error_words_json)
            for w in words:
                if w and w not in seen and w not in exclude_set:
                    seen.add(w)
                    accumulated.append(w)
        except Exception:
            continue

    return {
        "total_count": len(accumulated),
        "words": accumulated
    }


# --- [SPA Fallback] 모든 정적 리소스는 여기서 처리 (API 라우트 이후) ---
@app.get("/")
async def read_index():
    response = FileResponse("index.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# --- [SPA Fallback] 루트 경로는 모든 API 라우트 이후에 처리 ---
@app.get("/")
async def read_index():
    response = FileResponse("index.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response