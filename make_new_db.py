import os
import json
import re
import difflib
import sqlite3 

folder_path = r"D:/Sample/Sample/02.라벨링데이터"
final_output_file = "merged_paragraphs.json"

unique_sentences = [] 

print("[알림] 라벨링데이터 폴더와 모든 하위 폴더를 탐색합니다...")

for root, dirs, files in os.walk(folder_path):
    for filename in files:
        if filename.endswith(".json"):
            file_path = os.path.join(root, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    script_info = data.get("script", {})
                    n_id = script_info.get("id", "알수없는뉴스") 
                    seq = script_info.get("index", 0)           
                    txt = script_info.get("text", "").strip()           
                    
                    if txt:
                        txt = re.sub(r'\s+', ' ', txt)
                        pure_txt = re.sub(r'[^\w\s]', '', txt).replace(" ", "")
                        
                        is_duplicate = False
                        
                        for saved in unique_sentences:
                            if difflib.SequenceMatcher(None, pure_txt, saved["pure"]).ratio() >= 0.90:
                                is_duplicate = True
                                if len(txt) > len(saved["data"]["text"]):
                                    saved["data"]["text"] = txt
                                break
                        
                        if not is_duplicate:
                            unique_sentences.append({
                                "pure": pure_txt,
                                "data": {
                                    "news_id": n_id,
                                    "sequence": seq,
                                    "text": txt
                                }
                            })
                            
            except Exception as e:
                print(f"[경고] {filename} 파일을 읽는 중 오류 발생: {e}")

raw_data = [item["data"] for item in unique_sentences]

print(f"[성공] 띄어쓰기가 잘 된 문장만 골라낸 데이터 {len(raw_data)}개를 불러왔습니다!\n")
print("[진행] 150자 기준 및 100자 미만 완전 폐기 조건으로 묶는 중...")

grouped_news = {}
for item in raw_data:
    n_id = item["news_id"]
    if n_id not in grouped_news:
        grouped_news[n_id] = []
    grouped_news[n_id].append(item)

unique_final_paragraphs = []

for n_id, sentences in grouped_news.items():
    sentences.sort(key=lambda x: x["sequence"])
    
    current_paragraph = ""
    paragraph_seq = 1 
    sentence_count = 0 
    
    for i, sentence in enumerate(sentences):
        if current_paragraph:
            current_paragraph += " " + sentence["text"]
        else:
            current_paragraph = sentence["text"]
            
        sentence_count += 1
        
        clean_text = re.sub(r'\(([^)]+)\)/\([^)]+\)', r'\1', current_paragraph)
        clean_text = re.sub(r'/\([^)]+\)', '', clean_text)
        clean_text = re.sub(r'(\d+)\s+([가-힣a-zA-Z%])', r'\1\2', clean_text)
        clean_text = re.sub(r'(\d+)(만|억|조)\s+([가-힣])', r'\1\2\3', clean_text)
        
        clean_text = clean_text.strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        is_last_sentence = (i == len(sentences) - 1)
        
        # 🔥 [강력한 하이브리드 로직 적용]
        # 1. 150자 넘으면 무조건 완성
        # 2. 4문장이 모였는데, 길이가 120자 이상으로 꽤 길면 완성 (너무 짧은 4문장은 통과 안 시킴!)
        # 3. 뉴스의 마지막 문장일 때
        if len(clean_text) >= 150 or (sentence_count >= 4 and len(clean_text) >= 120) or is_last_sentence:
            
            # 🔥 [절대 방어선] 위 조건으로 묶었는데도 100자가 안 되면? 가차 없이 쓰레기통으로! (자투리 완벽 제거)
            if len(clean_text) < 100:
                current_paragraph = "" 
                sentence_count = 0
                continue
                
            pure_final = re.sub(r'[^\w\s]', '', clean_text).replace(" ", "")
            
            eojeol_count = len(clean_text.split())
            eumjeol_count = len(pure_final) 
            
            is_final_dup = False
            
            for saved_final in unique_final_paragraphs:
                if difflib.SequenceMatcher(None, pure_final, saved_final["pure"]).ratio() >= 0.90:
                    is_final_dup = True
                    if len(clean_text) > len(saved_final["data"]["paragraph_text"]):
                        saved_final["data"]["paragraph_text"] = clean_text
                        saved_final["data"]["length"] = len(clean_text)
                        saved_final["data"]["eojeol_count"] = eojeol_count
                        saved_final["data"]["eumjeol_count"] = eumjeol_count
                    break
                    
            if not is_final_dup:
                unique_final_paragraphs.append({
                    "pure": pure_final,
                    "data": {
                        "news_id": n_id,
                        "paragraph_seq": paragraph_seq, 
                        "paragraph_text": clean_text,
                        "length": len(clean_text),
                        "eojeol_count": eojeol_count, 
                        "eumjeol_count": eumjeol_count 
                    }
                })
                paragraph_seq += 1 
                
            current_paragraph = "" 
            sentence_count = 0

final_paragraphs = [item["data"] for item in unique_final_paragraphs]

print(f"[완료] 병합 완료! 총 {len(final_paragraphs)}개의 단락이 만들어졌습니다.")

# --- 데이터베이스(DB) 생성 및 저장 ---
print("\n[진행] 데이터베이스(DB) 생성을 시작합니다...")

# mk7으로 새롭게 쾌적하게 출발!
DB_FILE_NAME = 'voice_analysis(mk7).db'  
conn = sqlite3.connect(DB_FILE_NAME)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON")

cursor.executescript("""
DROP TABLE IF EXISTS analysis_result_table;
DROP TABLE IF EXISTS speech_record_table;
DROP TABLE IF EXISTS sentence_table;
DROP TABLE IF EXISTS user_table;
""")

cursor.executescript("""
CREATE TABLE user_table (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_score FLOAT
);

CREATE TABLE sentence_table (
    sentence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT,
    paragraph_seq INTEGER,
    text TEXT NOT NULL,
    length INTEGER NOT NULL,
    eojeol_count INTEGER,
    eumjeol_count INTEGER
);

CREATE TABLE speech_record_table (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    sentence_id INTEGER,
    audio_path TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_table(user_id),
    FOREIGN KEY (sentence_id) REFERENCES sentence_table(sentence_id)
);

CREATE TABLE analysis_result_table (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER,
    recognized_text TEXT,
    cer_score FLOAT,
    speech_rate FLOAT,
    silence_ratio FLOAT,
    clarity_score FLOAT,
    analysis_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES speech_record_table(record_id)
);
""")

db_insert_data = [
    (item["news_id"], item["paragraph_seq"], item["paragraph_text"], item["length"], item["eojeol_count"], item["eumjeol_count"]) 
    for item in final_paragraphs
]

cursor.executemany(
    "INSERT INTO sentence_table (news_id, paragraph_seq, text, length, eojeol_count, eumjeol_count) VALUES (?, ?, ?, ?, ?, ?)",
    db_insert_data
)

conn.commit()
conn.close()

print(f"[성공] 총 {len(db_insert_data)}개의 단락이 '{DB_FILE_NAME}'에 저장되었습니다!")

with open(final_output_file, 'w', encoding='utf-8') as f:
    json.dump(final_paragraphs, f, ensure_ascii=False, indent=4)
print(f"[성공] 결과물이 '{final_output_file}'에도 성공적으로 저장되었습니다!")