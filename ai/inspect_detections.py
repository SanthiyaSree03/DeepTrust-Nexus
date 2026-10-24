import sys
import json

filename = sys.argv[1] if len(sys.argv) > 1 else "test_santhiya_out.json"

with open(filename, "rb") as f:
    data = f.read().decode("utf-16", errors="ignore")

start = data.find("{")
end = data.rfind("}") + 1
obj = json.loads(data[start:end])

print(f"File: {filename}")
print(f"Total raw detections: {len(obj.get('raw_detections', []))}")
print("-" * 50)
for i, d in enumerate(obj.get("raw_detections", [])):
    text = d.get("text", "")
    conf = d.get("confidence", 0)
    box = d.get("box", [])
    print(f"[{i:02d}] conf={conf:.2f} box={box[0] if box else '[]'}: {text}")
