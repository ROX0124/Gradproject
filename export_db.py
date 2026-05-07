import sqlite3

# 1. DB 연결 (본인의 DB 파일명으로 확인)
db_name = "voice_analysis(mk7).db"
conn = sqlite3.connect(db_name)
cursor = conn.cursor()

try:
    # 새로 만들 복사본 테이블 이름 지정
    new_table_name = "analysis_result_44_to_130"

    # 만약 같은 이름의 테이블이 이미 있다면 지우고 다시 만들기 (에러 방지)
    cursor.execute(f"DROP TABLE IF EXISTS {new_table_name}")

    # 2. 핵심 SQL: 원본 테이블에서 44~130번만 골라서 새 테이블 생성 & 데이터 복사
    query = f"""
    CREATE TABLE {new_table_name} AS 
    SELECT * 
    FROM analysis_result_table 
    WHERE result_id BETWEEN 44 AND 130
    """
    
    cursor.execute(query)
    conn.commit()

    print(f"✅ DB 내부에 '{new_table_name}' 테이블이 새로 생성되고 데이터가 복사되었습니다!")

except Exception as e:
    conn.rollback()
    print(f"❌ 에러 발생: {e}")

finally:
    conn.close()