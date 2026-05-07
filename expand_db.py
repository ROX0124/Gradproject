import sqlite3

def expand_database():
    db_path = "voice_analysis(mk7).db"  # 
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 추가할 컬럼 정보 정의
    alter_queries = [
        # 1. sentence_table: 아나운서 기준 데이터 보강 [cite: 42, 227]
        "ALTER TABLE sentence_table ADD COLUMN anchor_duration REAL",
        "ALTER TABLE sentence_table ADD COLUMN anchor_silence_timestamps TEXT",
        
        # 2. analysis_result_table: 사용자 정밀 분석 결과 및 피드백 [cite: 42, 227]
        "ALTER TABLE analysis_result_table ADD COLUMN error_words TEXT",
        "ALTER TABLE analysis_result_table ADD COLUMN feedback_message TEXT"
    ]

    print(f"🚀 {db_path} 스키마 확장 시작...")

    for query in alter_queries:
        try:
            cursor.execute(query)
            column_name = query.split("ADD COLUMN ")[1].split(" ")[0]
            print(f"✅ 컬럼 추가 완료: {column_name}")
        except sqlite3.OperationalError as e:
            # 이미 컬럼이 존재하는 경우 에러가 발생하므로 이를 무시합니다.
            if "duplicate column name" in str(e):
                print(f"ℹ️ 이미 존재하는 컬럼입니다: {query.split('ADD COLUMN ')[1]}")
            else:
                print(f"❌ 에러 발생: {e}")

    conn.commit()
    conn.close()
    print("✨ 데이터베이스 구조 업데이트 완료!")

if __name__ == "__main__":
    expand_database()