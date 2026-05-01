import sqlite3

# 우리가 사용 중인 DB 파일 이름
DB_PATH = "voice_analysis(mk7).db"

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # analysis_result_table에 original_text 컬럼(문자열 타입) 추가
    cursor.execute("ALTER TABLE analysis_result_table ADD COLUMN original_text TEXT;")
    conn.commit()
    
    print("original_text 컬럼이 완벽하게 추가되었습니다")
    
except sqlite3.OperationalError as e:
    # 이미 컬럼을 추가했거나 다른 문제가 있을 때 알려줌
    print(f"안내 (또는 에러): {e}")
    
finally:
    conn.close()