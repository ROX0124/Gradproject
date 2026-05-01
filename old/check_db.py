import sqlite3

def check_database():
    # DB 연결
    conn = sqlite3.connect('voice_analysis.db')
    cursor = conn.cursor()

    # 1. 전체 데이터 개수 확인
    cursor.execute("SELECT COUNT(*) FROM sentence_table")
    total_count = cursor.fetchone()[0]
    print(f"✅ DB에 저장된 총 문장 개수: {total_count}개\n")

    # 2. 데이터 미리보기 (상위 5개만)
    cursor.execute("SELECT * FROM sentence_table LIMIT 5")
    rows = cursor.fetchall()

    print("--- 📝 저장된 데이터 미리보기 (상위 5개) ---")
    # row 형태: (sentence_id, text, length, source)
    for row in rows:
        print(f"ID: {row[0]} | 길이: {row[2]} | 출처: {row[3]}")
        print(f"문장: {row[1]}\n")

    conn.close()

if __name__ == "__main__":
    check_database()