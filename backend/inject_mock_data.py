import sqlite3
import uuid
import time
import sys
from pathlib import Path

# Force UTF-8 for Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Mock Data from test_reframe_mock.py
MOCK_TRANSCRIPTS = [
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Chào mọi người. Cảm ơn đã tham gia buổi họp kick-off dự án 'Chuyển đổi số 2026' hôm nay. Mục tiêu chính của chúng ta là chốt lại phạm vi dự án, ngân sách và lộ trình triển khai trong Quý 1. Mời anh Bình báo cáo tình hình chuẩn bị hạ tầng.", "start": 5.0, "end": 20.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "Vâng thưa anh An. Về hạ tầng server, đội IT đã hoàn tất việc nâng cấp cụm máy chủ tại Data Center Hòa Lạc. Chúng ta đã lắp đặt thêm 4 server GPU H100 để phục vụ cho module AI. Tuy nhiên, có một rủi ro là giấy phép phần mềm từ đối tác Microsoft đang bị chậm 2 tuần do vấn đề thủ tục hải quan. Tôi đề xuất chúng ta tạm thời dùng license trial trong 30 ngày để development team có thể bắt đầu code ngay vào thứ Hai tới (20/01).", "start": 45.0, "end": 90.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Được, tôi đồng ý phương án đó. Nhưng anh Bình phải cam kết đốc thúc bên vendor để có license chính thức trước ngày 15/02. Nếu không kịp thì sẽ ảnh hưởng đến việc go-live giai đoạn 1. Còn về Marketing thì sao chị Chi?", "start": 135.0, "end": 160.0},
    {"speaker": "Trưởng phòng Marketing (Lê Lan Chi)", "text": "Dạ, team Marketing đã lên plan truyền thông nội bộ. Chúng ta sẽ có buổi Townhall vào ngày 25/01 để công bố dự án này cho toàn thể nhân viên. Em cần xin duyệt ngân sách 50 triệu cho việc in ấn tài liệu và tiệc trà cho buổi Townhall này. Ngoài ra, em đề xuất chúng ta nên có một cái tên dự án nghe kêu hơn, ví dụ như 'Project Phoenix'.", "start": 180.0, "end": 220.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "50 triệu thì hơi cao cho một buổi tiệc nội bộ. Tôi duyệt tối đa 30 triệu thôi. Chị Chi cân đối lại nhé. Về tên dự án 'Project Phoenix', tôi thấy ổn. Chốt tên này luôn. Vậy tóm lại các việc cần làm: 1. IT bắt đầu dev vào 20/01 dùng trial license. 2. Anh Bình xử lý license chính thức trước 15/02. 3. Marketing tổ chức Townhall vào 25/01, ngân sách 30 triệu. Chị Chi gửi lại kế hoạch chi tiết cho tôi vào cuối ngày mai.", "start": 250.0, "end": 310.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "Rõ thưa anh. À còn một việc nữa, chúng ta có cần tuyển thêm BA không ạ? Hiện tại team đang thiếu người viết tài liệu.", "start": 330.0, "end": 340.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Chưa cần tuyển mới. Tạm thời điều chuyển bạn Hoa từ team Mobile sang hỗ trợ trong 2 tháng. Thôi chúng ta dừng ở đây. Mọi người triển khai nhé.", "start": 350.0, "end": 370.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "À khoan đã anh An, còn vấn đề về bảo mật dữ liệu nữa. Vì chúng ta sẽ đưa dữ liệu khách hàng lên cloud, em nghĩ cần có một buổi review riêng với bên Security trong tuần này.", "start": 380.0, "end": 400.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Đúng rồi, tí nữa thì quên. Cậu sắp xếp họp với anh Hùng bên Security vào chiều thứ Năm nhé. Bắt buộc phải có biên bản đánh giá rủi ro trước khi deploy release đầu tiên.", "start": 410.0, "end": 430.0},
    {"speaker": "Trưởng phòng Marketing (Lê Lan Chi)", "text": "Anh An ơi, về logo cho dự án Project Phoenix, em có thể thuê designer ngoài được không ạ? Team design nội bộ đang full load với campaign Tết rồi.", "start": 450.0, "end": 470.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Không được. Dự án nội bộ không cần logo quá cầu kỳ đâu. Bảo mấy bạn design làm đơn giản thôi, hoặc dùng logo công ty thêm chữ Project Phoenix vào là được. Tiết kiệm chi phí nhé.", "start": 480.0, "end": 500.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "Vâng, em cũng đồng ý. Tập trung vào chất lượng sản phẩm trước. Logo tính sau.", "start": 510.0, "end": 520.0},
    {"speaker": "Trưởng phòng Marketing (Lê Lan Chi)", "text": "Vâng ạ, em sẽ bảo các bạn làm nhanh. À còn lịch demo sản phẩm MVP (Minimum Viable Product), anh dự kiến vào bao giờ ạ?", "start": 530.0, "end": 550.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Dự kiến 15/03. Anh Bình lưu ý mốc này nhé. Đến lúc đó phải có bản chạy được nhưng tính năng cơ bản nhất để trình Hội đồng quản trị.", "start": 560.0, "end": 580.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "15/03 thì hơi căng đấy ạ vì vướng Tết Nguyên Đán mất gần 2 tuần nghỉ. Nhưng team sẽ cố gắng OT để kịp tiến độ.", "start": 590.0, "end": 610.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Cố gắng lên. Nếu hoàn thành đúng hạn và chất lượng tốt, tôi sẽ đề xuất thưởng nóng cho team dự án. À còn vấn đề nhân sự, nghe nói bên team Mobile đang có bạn nghỉ việc à?", "start": 620.0, "end": 640.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "Dạ vâng, bạn Tuấn lead team Mobile báo nghỉ vì lý do gia đình. Em đang tìm người thay thế nhưng khá khó tuyển dev cứng dịp gần Tết.", "start": 650.0, "end": 670.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Khó cũng phải tìm. Dự án Phoenix này cần support từ Mobile nhiều đấy. Nếu cần thì thuê headhunter gấp. Ngân sách tuyển dụng tôi sẽ duyệt thêm.", "start": 680.0, "end": 700.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "Vâng em sẽ liên hệ HR để push mạnh kênh headhunter. Hy vọng ra Tết có người.", "start": 710.0, "end": 720.0},
    {"speaker": "Trưởng phòng Marketing (Lê Lan Chi)", "text": "Anh Bình ơi, team em cũng cần tuyển thêm 1 bạn Content Writer chuyên viết về công nghệ để làm nội dung cho dự án này. Em gửi JD cho HR rồi mà chưa thấy CV nào.", "start": 730.0, "end": 750.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Marketing thì tự lo đi. Tôi chỉ ưu tiên ngân sách tuyển Tech thôi. Content thì thuê freelancer hoặc để team hiện tại kiêm nhiệm.", "start": 760.0, "end": 780.0},
    {"speaker": "Trưởng phòng Marketing (Lê Lan Chi)", "text": "Hic, vâng ạ. Em sẽ cố gắng xoay sở.", "start": 790.0, "end": 800.0},
    {"speaker": "Giám đốc (Nguyễn Văn An)", "text": "Thôi chốt lại nhé. Mọi người nắm rõ action items chưa? 1. License, 2. Townhall, 3. Security Review, 4. Tuyển dụng. Triển khai đi.", "start": 810.0, "end": 830.0},
    {"speaker": "Trưởng phòng IT (Trần Bình)", "text": "Rõ thưa anh. Em xin phép về làm việc.", "start": 840.0, "end": 845.0},
    {"speaker": "Trưởng phòng Marketing (Lê Lan Chi)", "text": "Chào các anh ạ. Chúc dự án thành công!", "start": 846.0, "end": 850.0}
]

DB_PATH = Path("D:/viettel/meeting-minutes/meeting-minutes/backend/meeting_minutes.db")

def inject_mock_data():
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # 1. Create Meeting
        meeting_id = str(uuid.uuid4())
        created_at = int(time.time() * 1000) # milliseconds
        title = "Họp Kick-off Dự án (Mock Data Transcripts)"
        
        cursor.execute(
            "INSERT INTO meetings (id, title, created_at) VALUES (?, ?, ?)",
            (meeting_id, title, created_at)
        )
        print(f"Created meeting: {title} (ID: {meeting_id})")

        # 2. Insert Transcripts
        for transcript in MOCK_TRANSCRIPTS:
            t_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO transcripts 
                (id, meeting_id, speaker, transcript, audio_start_time, audio_end_time, timestamp) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    t_id, 
                    meeting_id, 
                    transcript["speaker"], 
                    transcript["text"], 
                    transcript["start"], 
                    transcript["end"], 
                    created_at  # placeholder
                )
            )
        
        conn.commit()
        conn.close()
        print(f"Injected {len(MOCK_TRANSCRIPTS)} transcript segments.")
        print("\nPlease refresh the web page to see the new meeting.")

    except Exception as e:
        print(f"Error injecting data: {e}")

if __name__ == "__main__":
    inject_mock_data()
