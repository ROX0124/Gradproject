import sqlite3
import json
from pathlib import Path

def extract_and_seed_db(root_folder_path):
    root_path = Path(root_folder_path)
    # 1. 파일 이름순으로 정렬해서 가져오기 (문맥 순서 보장)
    json_files = sorted(list(root_path.rglob('*.json'))) 
    
    print(f"총 {len(json_files)}개의 JSON 파일을 찾았습니다. 문장 추출을 시작합니다...")

    raw_sentences_dict = {}

    # 2. 문장 및 source_id 추출
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if "script" in data and "text" in data["script"]:
                    sentence = data["script"]["text"]
                    
                    # 파일명 (예: SPK014KBSCU001 F001.json)
                    filename = file_path.name
                    
                    # 공백 기준 앞부분 추출 (예: SPK014KBSCU001)
                    full_id = filename.split(' ')[0] 
                    
                    # 앞 6글자(SPK014)를 제외한 진짜 뉴스 ID 추출 (예: KBSCU001)
                    source_id = full_id[6:] 
                    
                    if sentence and sentence not in raw_sentences_dict:
                        raw_sentences_dict[sentence] = source_id 
                        
        except Exception as e:
            print(f"파일 읽기 에러 ({file_path.name}): {e}")

    # 3. 데이터 가공
    processed_data = []
    for text, source_id in raw_sentences_dict.items():
        pure_text = text.strip()
        if not pure_text: 
            continue
            
        pure_length = len(pure_text.replace(" ", ""))
        
        # 여기에 "AIHub 뉴스 앵커" 대신 추출한 source_id가 들어갑니다.
        processed_data.append((pure_text, pure_length, source_id))

    if not processed_data:
        print("추출된 문장이 0개입니다. 폴더 경로를 확인해 주세요.")
        return

    # 4. DB 연결 및 테이블 생성
    conn = sqlite3.connect('voice_analysis(mk3).db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS user_table (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        total_score FLOAT
    );

    CREATE TABLE IF NOT EXISTS sentence_table (
        sentence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        length INTEGER NOT NULL,
        source TEXT
    );

    CREATE TABLE IF NOT EXISTS speech_record_table (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sentence_id INTEGER,
        audio_path TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES user_table(user_id),
        FOREIGN KEY (sentence_id) REFERENCES sentence_table(sentence_id)
    );

    CREATE TABLE IF NOT EXISTS analysis_result_table (
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
    
    # 5. DB에 데이터 삽입
    cursor.executemany(
        "INSERT INTO sentence_table (text, length, source) VALUES (?, ?, ?)",
        processed_data
    )
    
    conn.commit()
    conn.close()
    
    print(f"완료! 총 {len(processed_data)}개의 문장이 DB에 성공적으로 저장되었습니다.")

if __name__ == "__main__":
    # 본인 PC의 라벨링 데이터 경로
    extract_and_seed_db("D:/Sample/Sample/02.라벨링데이터")