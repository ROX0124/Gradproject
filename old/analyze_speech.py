import whisper
import Levenshtein

def calculate_clarity(audio_path, original_text):
    print(f"\n [{audio_path}] 분석 시작...")
    
    # 1. 모델 로드 (테스트용이므로 빠르고 가벼운 base 모델 사용)
    model = whisper.load_model("large")

    
    # 2. Whisper 음성 인식 (핵심: 단어 단위 타임스탬프 활성화!)
    print("오디오를 텍스트로 변환하고 미세 침묵을 분석 중입니다...")
    result = model.transcribe(audio_path, word_timestamps=True)
    recognized_text = result["text"].strip()
    
    # 3. CER (조음 정확도) 계산
    orig_chars = original_text.replace(" ", "")
    recog_chars = recognized_text.replace(" ", "")
    
    edit_distance = Levenshtein.distance(orig_chars, recog_chars)
    cer = edit_distance / len(orig_chars) if len(orig_chars) > 0 else 0
    cer_score = max(0.0, 1.0 - cer)

    # 4. 발화 속도 및 침묵 비율 계산 (단어 단위 정밀 분석)
    segments = result["segments"]
    total_audio_time = segments[-1]["end"] if segments else 0
    syllables = len(recog_chars)
    silence_time = 0.0
    
    if segments:
        # 첫 단어 시작 전까지의 공백 더하기
        silence_time += segments[0]["words"][0]["start"]
        
        for segment in segments:
            words = segment["words"]
            # 같은 조각(Segment) 내에서 단어와 단어 사이의 공백 더하기
            for i in range(len(words) - 1):
                gap = words[i+1]["start"] - words[i]["end"]
                if gap > 0:
                    silence_time += gap
                    
        # 조각(Segment)과 조각 사이의 공백 더하기
        for i in range(len(segments) - 1):
            gap = segments[i+1]["words"][0]["start"] - segments[i]["words"][-1]["end"]
            if gap > 0:
                silence_time += gap

    # 순수하게 말한 시간 = 전체 시간 - 침묵 시간
    speech_time = total_audio_time - silence_time
    
    raw_speech_rate = syllables / speech_time if speech_time > 0 else 0
    raw_silence_ratio = silence_time / total_audio_time if total_audio_time > 0 else 0

    # 5. 정규화 (설계서 기준 적용)
    target_rate = 5.59  # 아까 추출한 완벽한 앵커 평균!
    rate_diff = abs(target_rate - raw_speech_rate)
    speech_rate_score = max(0.0, 1.0 - (rate_diff * 0.2))

    target_silence = 0.15 # 15% 침묵을 만점 기준으로 설정
    silence_diff = abs(target_silence - raw_silence_ratio)
    silence_score = max(0.0, 1.0 - (silence_diff * 2.0))

    # 6. 최종 말 명료도 계산
    clarity_score = (cer_score * 0.5) + (speech_rate_score * 0.3) + (silence_score * 0.2)

    # 7. 결과 출력
    print("\n=========================================")
    print("📝 [텍스트 비교]")
    print(f"원본 대본: {original_text}")
    print(f"인식 결과: {recognized_text}")
    print("-----------------------------------------")
    print("📊 [상세 분석 결과]")
    print(f"1. 조음 정확도 (CER): {cer*100:.1f}% 오답률 -> [ {cer_score*100:.1f}점 ]")
    print(f"2. 발화 속도: 초당 {raw_speech_rate:.2f}음절 -> [ {speech_rate_score*100:.1f}점 ]")
    print(f"3. 침묵 비율: {raw_silence_ratio*100:.1f}% -> [ {silence_score*100:.1f}점 ]")
    print("=========================================")
    print(f"🌟 최종 말 명료도 점수: {clarity_score*100:.1f}점 / 100점 🌟")
    print("=========================================\n")

# --- 실행 부분 ---
# 실제 테스트할 오디오 파일 경로와 대본으로 수정해주세요!
TEST_AUDIO =  "D:/Sample/Sample/01.원천데이터/SPK014/SPK014KBSCU001/SPK014KBSCU001F001.wav"
ORIGINAL_TEXT = "지난해 극장을 찾은 연간 관객 수가 역대 최다치를 기록했습니다."

calculate_clarity(TEST_AUDIO, ORIGINAL_TEXT)