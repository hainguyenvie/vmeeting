import json
import webbrowser
import os
import sys

# Tên file cần đọc
INPUT_FILE = "sample.json"
# Tên file HTML sẽ tạo ra
OUTPUT_FILE = "preview_meeting.html"

def main():
    print(f"🔍 Dang tim file '{INPUT_FILE}'...")
    
    # Kiểm tra file tồn tại
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Loi: Khong tim thay file '{INPUT_FILE}' trong thu muc nay.")
        print(f"👉 Vui long dam bao file '{INPUT_FILE}' nam cung thu muc voi script nay.")
        input("Nhan Enter de thoat...")
        return

    try:
        # Đọc file JSON
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Kiểm tra field html
        if 'html' in data and data['html']:
            fragment_html = data['html']
            
            # Wrapper HTML để hiển thị đẹp khi preview
            # (API trả về fragment, tool này sẽ thêm khung bao ngoài)
            full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meeting Minutes Preview</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: #fff;
        }}
        h1 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-bottom: 16px; font-size: 2em; }}
        h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; margin-bottom: 16px; font-size: 1.5em; }}
        p {{ margin-bottom: 16px; }}
        ul {{ padding-left: 2em; margin-bottom: 16px; }}
        li {{ margin-bottom: 4px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; display: block; overflow: auto; }}
        th, td {{ padding: 6px 13px; border: 1px solid #dfe2e5; }}
        th {{ font-weight: 600; background-color: #f6f8fa; }}
        tr:nth-child(2n) {{ background-color: #f8f9fa; }}
        .citation {{ color: #0366d6; background-color: #f1f8ff; padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 0.85em; margin-left: 4px; border: 1px solid #e1e4e8; }}
        hr {{ height: 0.25em; padding: 0; margin: 24px 0; background-color: #e1e4e8; border: 0; }}
        strong {{ font-weight: 600; }}
        @media print {{
            body {{ padding: 0; }}
        }}
    </style>
</head>
<body>
    {fragment_html}
</body>
</html>"""
            
            # Ghi ra file HTML
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(full_html)
            
            print(f"✅ Da trich xuat HTML thanh cong!")
            print(f"📄 Da tao file: {os.path.abspath(OUTPUT_FILE)}")
            print("🌐 Dang mo trinh duyet...")
            
            # Mở trình duyệt
            webbrowser.open('file://' + os.path.abspath(OUTPUT_FILE))
            
        else:
            print("⚠️ File JSON hop le nhung khong tim thay truong 'html'.")
            print("Cac truong co trong file:", list(data.keys()))
            
    except json.JSONDecodeError:
        print(f"❌ Loi: File '{INPUT_FILE}' khong phai la file JSON hop le.")
    except Exception as e:
        print(f"❌ Loi khong mong muon: {str(e)}")

if __name__ == "__main__":
    main()
