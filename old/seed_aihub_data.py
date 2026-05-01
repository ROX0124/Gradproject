import sqlite3
import json
from pathlib import Path

def extract_and_seed_db(root_folder_path):
    # 1. JSON 파일 찾기 및 정렬 (같은 뉴스 폴더/이름끼리 묶이도록)
    root_path = Path(root_folder_path)
    
    # sorted()를 추가하여 파일 경로/이름 순으로 정렬합니다.
    json_files = sorted(list(root_path.rglob('*.json'))) 
    
    print(f"총 {len(json_files)}개의 JSON 파일을 찾았습니다. 문장 추출을 시작합니다...")

    # set 대신 dict 사용 (순서 유지하면서 중복 제거)
    raw_sentences_dict = {}

# 2. 문장 추출 로직 수정
    raw_sentences_dict = {}

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if "script" in data and "text" in data["script"]:
                    sentence = data["script"]["text"]
                    
                    # 파일명: "SPK014KBSCU001 F001.json"
                    filename = file_path.name
                    
                    # 1. 공백 기준 앞부분 추출 -> "SPK014KBSCU001"
                    full_id = filename.split(' ')[0] 
                    
                    # 2. 앞의 'SPK014' (6글자)를 떼고 뉴스 ID만 추출 -> "KBSCU001"
                    # 만약 화자 정보까지 포함하고 싶다면 그냥 full_id를 사용하세요!
                    source_id = full_id[6:] 
                    
                    if sentence and sentence not in raw_sentences_dict:
                        # 딕셔너리에 뉴스 ID(source)를 함께 저장
                        raw_sentences_dict[sentence] = source_id
                        
        except Exception as e:
            print(f"파일 읽기 에러 ({file_path.name}): {e}")

    # 3. 데이터 가공 (공백 제거 및 글자 수 계산)
    processed_data = []
    
    # dict의 키(문장)를 순회하면, 데이터가 삽입된 순서(파일 정렬 순서)대로 나옵니다.
    for text in raw_sentences_dict.keys():
        pure_text = text.strip()
        if not pure_text: 
            continue
            
        pure_length = len(pure_text.replace(" ", ""))
        
        # 튜플에 'AIHub 뉴스 앵커' 대신 추출한 source_id를 넣습니다.
        processed_data.append((text, pure_length, source_id))



    if not processed_data:
        print("추출된 문장이 0개입니다. 폴더 경로를 확인해 주세요.")
        return

    # 4. DB 연결 및 테이블 생성 (이 부분이 추가되었습니다!)
    conn = sqlite3.connect('voice_analysis.db(mk3)')
    cursor = conn.cursor()
    
    # 외래 키 설정 활성화
    cursor.execute("PRAGMA foreign_keys = ON")

    # 설계서에 있는 4개의 테이블을 먼저 무조건 생성합니다. (이미 있으면 건너뜀)
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
    
    print(f"🎉 완료! 테이블 생성 및 중복을 제외한 총 {len(processed_data)}개의 문장이 DB에 성공적으로 저장되었습니다.")

if __name__ == "__main__":
    
    extract_and_seed_db("D:/Sample/Sample/02.라벨링데이터")