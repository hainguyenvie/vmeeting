# 📝 Tóm Tắt: Nguyên Nhân và Giải Pháp Cho Vấn Đề Mất Segments

## 🎯 Vấn Đề Bạn Gặp Phải

Khi upload full audio file, hệ thống trả về transcripts có **gaps / khoảng trống** giữa các segments:

```
✅ Segment 1: 00:00 - 00:08 (Speaker 1)
❌ MẤT 8 GIÂY (00:08 → 00:16)
✅ Segment 2: 00:16 - 00:25 (Speaker 1)
❌ MẤT 6 GIÂY (00:25 → 00:31)
✅ Segment 3: 00:31 - 00:37 (Speaker 2)
```

Backend log hiển thị: `✅ Full Pipeline Success! Got 3 segments`
→ Vậy vấn đề nằm ở **Whisper Service** (`service.py`), không phải Backend!

---

## 🔍 Nguyên Nhân Gốc Rễ

### 1. **Energy Threshold Quá Cao** ⚠️
```python
# CODE CŨ (WRONG)
energy = np.mean(chunk**2)
if energy < 0.001:  # ← Quá cao!
    continue  # Skip chunk này!
```

**Hậu quả:**
- Các đoạn nói **âm lượng thấp** bị bỏ qua hoàn toàn
- Các từ nhẹ, câu cuối (thường nhỏ hơn) bị mất
- Tạo ra **false gaps** trong timeline

**VÍ DỤ:** 
- Bạn nói: "OK XIN CHÀO BẠN" (to) + "làm ơn nghe tôi nói" (nhỏ)
- Hệ thống chỉ detect: "OK XIN CHÀO BẠN" → Mất đoạn sau!

### 2. **Minimum Duration Filter Quá Dài** ⚠️
```python
# CODE CŨ (WRONG)
if curr_end - curr_start > 1.0:  # ← Chỉ giữ segment > 1s
    merged_timeline.append(...)
```

**Hậu quả:**
- Các câu ngắn (< 1s) bị **loại bỏ hoàn toàn**
- Từ đơn, câu hỏi ngắn không được lưu

**VÍ DỤ:**
- "Hả?" (0.5s) → Bị loại
- "Tí nữa" (0.8s) → Bị loại
- "Hả tính bây giờ chỉ rửa" (0.6s) → Bị loại

### 3. **Gap Merging Không Đủ Linh Hoạt**
```python
# CODE CŨ
if spk == curr_spk and gap < 2.0:  # ← Chỉ merge nếu gap < 2s
```

Nếu có nhiều đoạn bị skip do energy threshold → Tạo gaps > 2s → Tách thành nhiều segments → Một số segments ngắn bị filter

---

## ✅ Giải Pháp Đã Áp Dụng

### Fix #1: **Adaptive Energy Threshold**
```python
# Tính threshold dựa trên RMS của toàn bộ audio
audio_rms = np.sqrt(np.mean(audio**2))
energy_threshold = max(audio_rms * 0.03, 0.0001)  # 3% RMS, min 0.0001

# Dùng RMS thay vì mean energy
rms = np.sqrt(np.mean(chunk**2))
if rms < energy_threshold:  # Adaptive!
```

**Lợi ích:**
- Tự động điều chỉnh theo từng audio file
- Audio nhỏ → threshold thấp → nhạy hơn
- Audio to → threshold cao → vẫn chính xác

### Fix #2: **Giảm Minimum Duration**
```python
# Giảm từ 1.0s → 0.3s
if curr_end - curr_start > 0.3:
    merged_timeline.append(...)
```

**Lợi ích:**
- Giữ lại được các câu ngắn (0.3s - 1.0s)
- Ít bị mất dữ liệu hơn

### Fix #3: **Tăng Gap Tolerance**
```python
# Tăng từ 2.0s → 3.0s
if spk == curr_spk and gap < 3.0:
    curr_end = max(curr_end, e)
```

**Lợi ích:**
- Merge được các đoạn có khoảng im lặng dài hơn
- Giảm số lượng segments phân mảnh

### Fix #4: **Debug Logging Chi Tiết**
```python
# Track và print stats
print(f"📊 Scan Stats: {total_chunks} chunks, {skipped_chunks} skipped")
print(f"📊 Raw Timeline: {len(timeline)} segments")
print(f"📊 Merged Timeline: {len(merged_timeline)} segments")

# Phát hiện gaps
for i in range(len(merged_timeline) - 1):
    gap = merged_timeline[i+1][0] - merged_timeline[i][1]
    if gap > 1.0:
        print(f"⚠️ GAP: {merged_timeline[i][1]:.2f} → {merged_timeline[i+1][0]:.2f} ({gap:.2f}s)")
```

**Lợi ích:**
- Thấy được chính xác pipeline làm gì
- Dễ dàng debug và tune parameters

---

## 🧪 Cách Test

### Bước 1: Restart Whisper Service
```powershell
# Stop service cũ (Ctrl+C trong terminal hoặc tìm process)
# Chạy lại:
cd d:\viettel\meeting-minutes\meeting-minutes\web-version\meetily-lite\whisper
python .\service.py
```

### Bước 2: Upload Lại Audio File
- Dùng cùng file audio đã test trước đó
- Upload qua frontend

### Bước 3: Kiểm Tra Terminal Output
Bây giờ bạn sẽ thấy output mới:

```
🎚️ Adaptive Energy Threshold: 0.000234 (Audio RMS: 0.007800)
🔍 [Pipeline] Step 1: Diarizing...
📊 Scan Stats: 45 chunks, 12 skipped (26.7%)
📊 Raw Timeline: 8 segments
  [0] 0.00 - 8.50 Speaker 0 (duration: 8.50s)
  [1] 9.20 - 15.80 Speaker 0 (duration: 6.60s)
  [2] 16.00 - 25.30 Speaker 0 (duration: 9.30s)
  ...

🔗 [Pipeline] Step 2: Merging...
⚠️ Filtered short segment: 2.30-2.50 (duration: 0.20s)
📊 Merged Timeline: 5 segments
  [0] 0.00 - 8.50 Speaker 0 (duration: 8.50s)
  [1] 9.20 - 25.30 Speaker 0 (duration: 16.10s)  ← MERGED!
  ...

🔍 Analyzing gaps between segments:
  ⚠️ GAP: 8.50 → 9.20 (0.70s)  ← Nhỏ hơn trước rất nhiều!

📝 [Pipeline] Step 3: Transcribing...
  ✅ [0.00-8.50] Speaker 1: OK XIN CHÀO BẠN LÀM ƠN HÃY NÓI...
  ✅ [9.20-25.30] Speaker 1: ÚY NÓ VẪN NHẬN DIỆN ĐƯỢC ĐÚNG...
  ...

✅ Full Pipeline Complete in 12.34s
📊 Final Output: 5 transcribed segments
```

### Bước 4: So Sánh Kết Quả

**Trước khi fix:**
```
3 segments với gaps lớn (8s, 6s)
```

**Sau khi fix (dự kiến):**
```
5-7 segments với gaps nhỏ hơn (< 1s)
HOẶC ít segments hơn nhưng mỗi segment dài hơn (merged better)
```

---

## 📊 Kì Vọng

### Trường Hợp Tốt Nhất
- **0 gaps** hoặc **gaps < 0.5s** (chỉ là khoảng im lặng thật sự)
- **Tất cả audio được transcribe**

### Trường Hợp Chấp Nhận Được
- Gaps nhỏ (0.5s - 1.5s) do im lặng thật sự
- Một số đoạn rất ngắn (< 0.3s) vẫn bị filter nhưng đó thường là breathing/noise

### Nếu Vẫn Có Vấn Đề
Có thể tiếp tục tune:
- `energy_threshold = max(audio_rms * 0.02, 0.0001)` (giảm từ 3% → 2%)
- `if curr_end - curr_start > 0.2` (giảm min duration xuống 0.2s)

---

## 🔧 File Đã Thay Đổi

- ✅ **whisper/service.py** - Dòng 513-652 (hàm `run_diarize_first_pipeline`)

**Backup:** `whisper/service_FIXED.py` đã được tạo (nếu cần rollback)

---

## 📚 Documents Tham Khảo

1. **DIARIZATION_FIRST_ANALYSIS.md** - Phân tích chi tiết toàn bộ hệ thống và logic
2. **service_FIXED.py** - Code mới với comments đầy đủ
3. File này - Tóm tắt ngắn gọn

---

## ❓ FAQ

**Q: Tại sao không set threshold = 0 luôn?**
A: Vì sẽ detect cả noise/background sound → Tạo ra rất nhiều segments rác

**Q: Tại sao không bỏ hẳn minimum duration filter?**
A: Vì các segments quá ngắn (< 0.3s) thường là breathing, mouth sounds, không có nội dung có ý nghĩa

**Q: Có cách nào tốt hơn không?**
A: Có! Dùng Silero VAD model thay vì energy threshold. Nhưng cần thêm dependency và phức tạp hơn.

---

## 🎉 Kết Luận

Vấn đề của bạn là do **pipeline diarization-first quá strict** trong việc filter audio:
1. Energy threshold quá cao → Bỏ qua đoạn nhỏ
2. Min duration quá dài → Loại câu ngắn
3. Gap merging không đủ → Tạo fragments

**Giải pháp:** Adaptive threshold + Relaxed filters + Debug logging

**Next step:** Restart service và test lại! 🚀
