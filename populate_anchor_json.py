import sqlite3
import json

def populate_from_json():
    db_path = "voice_analysis(mk7).db"  # DB 파일명 (기존과 동일한지 확인)
    json_path = "auto_analysis_results.json"      # 방금 저장한 JSON 파일명
    
    try:
        # 1. JSON 파일 읽어오기
        with open(json_path, 'r', encoding='utf-8') as f:
            data_list = json.load(f)
    except FileNotFoundError:
        print(f"❌ '{json_path}' 파일을 찾을 수 없습니다. 파일이 같은 폴더에 있는지 확인해주세요.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"🚀 {db_path}에 JSON 데이터 주입을 시작합니다...")

    for item in data_list:
        try:
            s_id = item["sentence_id"]
            results = item["results"]["analysis_results"]
            
            # 2. "38.28초" 같은 문자열에서 "초"를 제거하고 실수(Float)로 변환
            duration_str = results.get("duration", "0초").replace("초", "")
            duration = float(duration_str)
            
            # 3. "2.33초" 같은 문자열에서 "초"를 제거하고 실수(Float)로 변환
            silence_str = results.get("total_silence_time", "0초").replace("초", "")
            silence = float(silence_str)
            
            # 4. 세부 타임스탬프 대신 '총 침묵 시간'을 JSON 형태로 변환하여 저장
            # 나중에 파이썬에서 json.loads()로 쉽게 꺼내 쓸 수 있도록 딕셔너리 형태로 묶습니다.
            silence_info = {"total_silence": silence}
            json_silence = json.dumps(silence_info)
            
            # 5. DB 업데이트 실행
            cursor.execute("""
                UPDATE sentence_table 
                SET anchor_duration = ?, anchor_silence_timestamps = ?
                WHERE sentence_id = ?
            """, (duration, json_silence, s_id))
            
            print(f"✅ 문장 ID {s_id}번 업데이트 성공 (길이: {duration}초, 침묵: {silence}초)")
            
        except Exception as e:
            print(f"❌ 문장 ID {item.get('sentence_id', '알수없음')} 업데이트 중 오류 발생: {e}")

    conn.commit()
    conn.close()
    print("✨ 80개 문장(데이터) 주입이 완벽하게 끝났습니다!")

if __name__ == "__main__":
    populate_from_json()