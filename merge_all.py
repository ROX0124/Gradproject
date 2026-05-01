import os
import subprocess

# 1. 경로 설정
BASE_DIR = "announcer_voice"      # 원본 폴더
OUTPUT_DIR = "merged_voices_final" # 통합본 저장 폴더
os.makedirs(OUTPUT_DIR, exist_ok=True)

def merge_audio_folders():
    # 폴더 구조: 화자ID / 대본ID / 문장ID(1,2,3..)
    for speaker_id in os.listdir(BASE_DIR):
        speaker_path = os.path.join(BASE_DIR, speaker_id)
        if not os.path.isdir(speaker_path): continue

        for script_id in os.listdir(speaker_path):
            script_path = os.path.join(speaker_path, script_id)
            if not os.path.isdir(script_path): continue

            for paragraph_id in os.listdir(script_path):
                paragraph_path = os.path.join(script_path, paragraph_id)
                if not os.path.isdir(paragraph_path): continue

                # 2. 해당 폴더 안의 wav 파일 찾기
                wav_files = [f for f in os.listdir(paragraph_path) if f.endswith(".wav")]
                wav_files.sort() # 순서대로 정렬 (F001, F002...)

                if not wav_files: continue

                # 3. 통합 파일 이름 규칙 (예: merged_SPK014_CU001_1.wav)
                output_filename = f"merged_{speaker_id}_{script_id}_{paragraph_id}.wav"
                output_path = os.path.join(OUTPUT_DIR, output_filename)

                # 4. FFmpeg용 리스트 파일 생성
                list_file = "temp_list.txt"
                with open(list_file, "w", encoding="utf-8") as f:
                    for wav in wav_files:
                        abs_path = os.path.abspath(os.path.join(paragraph_path, wav)).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")

                # 5. FFmpeg 병합 실행
                print(f"병합 중: {output_filename}...")
                subprocess.run([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", list_file, "-c", "copy", output_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists("temp_list.txt"):
        os.remove("temp_list.txt")
    print("✅ 모든 파일 통합이 완료되었습니다!")

if __name__ == "__main__":
    merge_audio_folders()