import csv
import json
from pathlib import Path

# training_output 폴더 경로 지정
out_dir = Path("output/training_output")

for filename in ["total_train.jsonl", "total_test.jsonl"]:
    jsonl_path = out_dir / filename
    csv_path = out_dir / filename.replace(".jsonl", ".csv")
    
    if not jsonl_path.exists():
        print(f"파일이 없습니다: {jsonl_path}")
        continue

    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            
            # JSONL 내부 구조(category, prompt, completion)를 엑셀 행 형태로 펼쳐 담기
            category = data.get("category", "")
            
            # prompt 리스트에서 user 메시지(질문/사실목록) 추출
            user_content = ""
            for msg in data.get("prompt", []):
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")
            
            # completion 리스트에서 assistant 메시지(정답 본문) 추출
            assistant_content = ""
            for msg in data.get("completion", []):
                if msg.get("role") == "assistant":
                    assistant_content = msg.get("content", "")
            
            rows.append({
                "category": category,
                "prompt": user_content,
                "completion": assistant_content
            })

    # CSV 파일로 저장
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "prompt", "completion"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"변환 완료: {csv_path.name} (총 {len(rows)}행)")