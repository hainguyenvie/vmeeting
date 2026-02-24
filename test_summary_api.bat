@echo off
echo Testing Summary API with HTML output...
echo.

curl -X POST "http://localhost:5167/api/summary/generate" ^
-H "Content-Type: application/json" ^
-d "{\"transcript\": \"[00:15] Nguyen Van A: Xin chao moi nguoi, hom nay chung ta hop de thao luan ve tien do du an Q1. [00:30] Tran Thi B: Da, em bao cao ve phan marketing. Hien tai chung em da hoan thanh 80%% ke hoach quang cao. [00:45] Nguyen Van A: Tot lam. Vay deadline cuoi cung la khi nao? [00:52] Tran Thi B: Da, em du kien hoan thanh vao thu 6 tuan nay a. [01:10] Le Van C: Anh xin phep gop y ve ngan sach. Hien tai phong ky thuat can bo sung them 50 trieu de mua thiet bi server. [01:30] Nguyen Van A: Duoc, toi chot quyet dinh phe duyet them 50 trieu cho phong ky thuat. Anh C lam giay de xuat gui cho toi truoc thu 4.\", \"template_id\": \"bien_ban_hop_vn\", \"metadata\": {\"meeting_title\": \"Hop tien do du an Q1 2026\", \"date\": \"09/02/2026\", \"participants\": [\"Nguyen Van A\", \"Tran Thi B\", \"Le Van C\"]}}"

echo.
echo Test completed!
pause
