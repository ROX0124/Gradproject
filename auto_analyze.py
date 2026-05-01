import os
import requests
import time
import json

# ==========================================
# ⚙️ 설정 부분 (내 환경에 맞게 확인하세요)
# ==========================================
# 1. FastAPI 서버 주소 (서버가 켜져 있어야 합니다)
SERVER_URL = "http://localhost:8080/upload"  # 기존 엔드포인트 이름이 /analyze 였다면 수정해주세요.

# 2. 아나운서 통합 음성이 들어있는 폴더 경로
AUDIO_DIR = "merged_voices_final"

# 3. 결과를 따로 텍스트로 저장할지 여부
RESULT_LOG_FILE = "auto_analysis_results.json"
# ==========================================

def run_auto_analysis():
    # 폴더 내의 모든 wav 파일 목록 가져오기
    if not os.path.exists(AUDIO_DIR):
        print(f"❌ 폴더를 찾을 수 없습니다: {AUDIO_DIR}")
        return

    audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(".wav")]
    print(f"🎯 총 {len(audio_files)}개의 음성 파일을 찾았습니다. 자동 분석을 시작합니다!\n")

    all_results = []

    for filename in audio_files:
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # 💡 파일명에서 sentence_id 추출 (예: merged_SPK014_..._67.wav -> 67)
        # 파일명 구조에 따라 수정이 필요할 수 있습니다.
        try:
            sentence_id = int(filename.split("_")[-1].replace(".wav", ""))
        except ValueError:
            print(f"⚠️ {filename}에서 문장 ID를 추출할 수 없어 1번으로 기본 설정합니다.")
            sentence_id = 1 

        print(f"▶️ 분석 중: {filename} (문장 ID: {sentence_id})...", end=" ")

        # 서버로 파일 전송
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "audio/wav")}
            params = {"sentence_id": sentence_id}  # ⭕ URL 쿼리 파라미터로 변경!
            
            try:
                # data 대신 params=params 로 변경!
                response = requests.post(SERVER_URL, files=files, params=params)
                
                if response.status_code == 200:
                    result_data = response.json()
                    print(f"\nDEBUG - 서버가 준 데이터: {result_data}")
                    print(f"✅ 완료! (정확도: {result_data.get('analysis_results', {}).get('clarity_score', 'N/A')})")
                    all_results.append({
                        "filename": filename,
                        "sentence_id": sentence_id,
                        "results": result_data
                    })
                else:
                    print(f"❌ 에러 발생: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ 서버 통신 실패: {e}")

        # Whisper 모델이 너무 뜨거워지지(?) 않도록 1초씩 쉬어줍니다.
        time.sleep(1)

    # 전체 결과를 JSON 파일로 예쁘게 저장 (엑셀로 변환하기도 편함)
    with open(RESULT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 모든 분석이 끝났습니다! 결과는 {RESULT_LOG_FILE}에 저장되었고, DB에도 기록되었습니다.")

if __name__ == "__main__":
    run_auto_analysis()