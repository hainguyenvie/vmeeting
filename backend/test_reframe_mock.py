import requests
import json
import time

# Mock Data: A comprehensive project planning meeting (Vietnamese)
# This simulates a high-quality transcript where FRAME should excel.
MOCK_TRANSCRIPT = """
00:00:05 - Giám đốc (Nguyễn Văn An):
Chào mọi người. Cảm ơn đã tham gia buổi họp kick-off dự án "Chuyển đổi số 2026" hôm nay.
Mục tiêu chính của chúng ta là chốt lại phạm vi dự án, ngân sách và lộ trình triển khai trong Quý 1.
Mời anh Bình báo cáo tình hình chuẩn bị hạ tầng.

00:00:45 - Trưởng phòng IT (Trần Bình):
Vâng thưa anh An. Về hạ tầng server, đội IT đã hoàn tất việc nâng cấp cụm máy chủ tại Data Center Hòa Lạc.
Chúng ta đã lắp đặt thêm 4 server GPU H100 để phục vụ cho module AI.
Tuy nhiên, có một rủi ro là giấy phép phần mềm từ đối tác Microsoft đang bị chậm 2 tuần do vấn đề thủ tục hải quan.
Tôi đề xuất chúng ta tạm thời dùng license trial trong 30 ngày để development team có thể bắt đầu code ngay vào thứ Hai tới (20/01).

00:02:15 - Giám đốc (Nguyễn Văn An):
Được, tôi đồng ý phương án đó. Nhưng anh Bình phải cam kết đốc thúc bên vendor để có license chính thức trước ngày 15/02.
Nếu không kịp thì sẽ ảnh hưởng đến việc go-live giai đoạn 1.
Còn về Marketing thì sao chị Chi?

00:03:00 - Trưởng phòng Marketing (Lê Lan Chi):
Dạ, team Marketing đã lên plan truyền thông nội bộ. Chúng ta sẽ có buổi Townhall vào ngày 25/01 để công bố dự án này cho toàn thể nhân viên.
Em cần xin duyệt ngân sách 50 triệu cho việc in ấn tài liệu và tiệc trà cho buổi Townhall này.
Ngoài ra, em đề xuất chúng ta nên có một cái tên dự án nghe kêu hơn, ví dụ như "Project Phoenix".

00:04:10 - Giám đốc (Nguyễn Văn An):
50 triệu thì hơi cao cho một buổi tiệc nội bộ. Tôi duyệt tối đa 30 triệu thôi. Chị Chi cân đối lại nhé.
Về tên dự án "Project Phoenix", tôi thấy ổn. Chốt tên này luôn.
Vậy tóm lại các việc cần làm:
1. IT bắt đầu dev vào 20/01 dùng trial license.
2. Anh Bình xử lý license chính thức trước 15/02.
3. Marketing tổ chức Townhall vào 25/01, ngân sách 30 triệu.
Chị Chi gửi lại kế hoạch chi tiết cho tôi vào cuối ngày mai.

00:05:30 - Trưởng phòng IT (Trần Bình):
Rõ thưa anh. À còn một việc nữa, chúng ta có cần tuyển thêm BA không ạ? Hiện tại team đang thiếu người viết tài liệu.

00:05:50 - Giám đốc (Nguyễn Văn An):
Chưa cần tuyển mới. Tạm thời điều chuyển bạn Hoa từ team Mobile sang hỗ trợ trong 2 tháng.
Thôi chúng ta dừng ở đây. Mọi người triển khai nhé.
"""

API_URL = "http://localhost:5167"
TEMPLATE_ID = "bien_ban_hop_vn"  # Ensure this ID matches a valid template in your DB/JSON

def test_generate_summary():
    print(f"🚀 Sending request to {API_URL}/api/summary/generate...")
    
    payload = {
        "transcript": MOCK_TRANSCRIPT,
        "template_id": TEMPLATE_ID,
        "provider": "openai", # Or ollama, checking default
        "model": "gpt-4o",    # Or your specific model
        "api_key": "YOUR_OPENAI_API_KEY_HERE",
        "metadata": {
            "meeting_title": "Họp Kick-off Dự án Chuyển đổi số 2026 (Mock Data Test)",
            "date": "2026-01-15 14:00:00",
            "participants": ["Nguyễn Văn An (Giám đốc)", "Trần Bình (IT)", "Lê Lan Chi (Marketing)"]
        }
    }

    try:
        # Check if server is up first
        health = requests.get(f"{API_URL}/health")
        if health.status_code != 200:
            print("❌ Backend is not healthy or not running!")
            return

        start_time = time.time()
        response = requests.post(f"{API_URL}/api/summary/generate", json=payload)
        end_time = time.time()

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! Time taken: {end_time - start_time:.2f}s")
            
            # Print Raw Summary or Parsed JSON
            summary = data.get("summary", {})
            print("\n📄 GENERATED SUMMARY CONTENT:")
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            
            if data.get("raw_summary"):
                print("\n📝 RAW AI OUTPUT:")
                print(data.get("raw_summary")[:500] + "... (truncated)")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    test_generate_summary()
