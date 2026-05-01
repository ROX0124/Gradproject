import os
import json
import re
import difflib

folder_path = r"D:\Sample\Sample\02.라벨링데이터"
final_output_file = "merged_paragraphs.json"

unique_sentences = [] 

print("[알림] 라벨링데이터 폴더와 모든 하위 폴더를 탐색합니다...")

for root, dirs, files in os.walk(folder_path):
    for filename in files:
        if filename.endswith(".json"):
            file_path = os.path.join(root, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    script_info = data.get("script", {})
                    n_id = script_info.get("id", "알수없는뉴스") 
                    seq = script_info.get("index", 0)           
                    txt = script_info.get("text", "").strip()           
                    
                    if txt:
                        txt = re.sub(r'\s+', ' ', txt)
                        pure_txt = re.sub(r'[^\w\s]', '', txt).replace(" ", "")
                        
                        is_duplicate = False
                        
                        for saved in unique_sentences:
                            if difflib.SequenceMatcher(None, pure_txt, saved["pure"]).ratio() >= 0.90:
                                is_duplicate = True
                                if len(txt) > len(saved["data"]["text"]):
                                    saved["data"]["text"] = txt
                                break
                        
                        if not is_duplicate:
                            unique_sentences.append({
                                "pure": pure_txt,
                                "data": {
                                    "news_id": n_id,
                                    "sequence": seq,
                                    "text": txt
                                }
                            })
                            
            except Exception as e:
                print(f"[경고] {filename} 파일을 읽는 중 오류 발생: {e}")

raw_data = [item["data"] for item in unique_sentences]

print(f"[성공] 띄어쓰기가 잘 된 문장만 골라낸 데이터 {len(raw_data)}개를 불러왔습니다!\n")
print("[진행] 100자 이상 OR 4문장 이상 기준으로 스마트하게 묶는 중...")

grouped_news = {}
for item in raw_data:
    n_id = item["news_id"]
    if n_id not in grouped_news:
        grouped_news[n_id] = []
    grouped_news[n_id].append(item)

unique_final_paragraphs = []

for n_id, sentences in grouped_news.items():
    sentences.sort(key=lambda x: x["sequence"])
    
    current_paragraph = ""
    sentence_count = 0  # 🔥 몇 문장이 합쳐졌는지 세는 카운터 추가!
    
    for sentence in sentences:
        if current_paragraph:
            current_paragraph += " " + sentence["text"]
        else:
            current_paragraph = sentence["text"]
            
        sentence_count += 1 # 문장을 하나 합칠 때마다 1씩 증가
        
        clean_text = re.sub(r'\(([^)]+)\)/\([^)]+\)', r'\1', current_paragraph)
        clean_text = re.sub(r'/\([^)]+\)', '', clean_text)
        clean_text = re.sub(r'(\d+)\s+([가-힣a-zA-Z%])', r'\1\2', clean_text)
        clean_text = re.sub(r'(\d+)(만|억|조)\s+([가-힣])', r'\1\2\3', clean_text)
        
        clean_text = clean_text.strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        # 🔥 [핵심 변경 포인트] 글자 수가 100자 이상이거나, 합친 문장이 4개 이상이면 무조건 스톱!
        if len(clean_text) >= 100 or sentence_count >= 4:
            pure_final = re.sub(r'[^\w\s]', '', clean_text).replace(" ", "")
            is_final_dup = False
            
            for saved_final in unique_final_paragraphs:
                if difflib.SequenceMatcher(None, pure_final, saved_final["pure"]).ratio() >= 0.90:
                    is_final_dup = True
                    if len(clean_text) > len(saved_final["data"]["paragraph_text"]):
                        saved_final["data"]["paragraph_text"] = clean_text
                        saved_final["data"]["length"] = len(clean_text)
                        # 혹시 나중에 DB에 문장 개수도 넣고 싶을까봐 추가해 둠!
                        saved_final["data"]["sentence_count"] = sentence_count 
                    break
                    
            if not is_final_dup:
                unique_final_paragraphs.append({
                    "pure": pure_final,
                    "data": {
                        "news_id": n_id,
                        "paragraph_text": clean_text,
                        "length": len(clean_text),
                        "sentence_count": sentence_count # 문장 개수 저장
                    }
                })
            # 다음 단락을 위해 텍스트와 카운터 모두 초기화!
            current_paragraph = "" 
            sentence_count = 0

final_paragraphs = [item["data"] for item in unique_final_paragraphs]

print(f"[완료] 병합 완료! 총 {len(final_paragraphs)}개의 완벽한 평가용 단락이 만들어졌습니다.")

with open(final_output_file, 'w', encoding='utf-8') as f:
    json.dump(final_paragraphs, f, ensure_ascii=False, indent=4)

print(f"[저장] 결과물이 '{final_output_file}'에 성공적으로 저장되었습니다!")