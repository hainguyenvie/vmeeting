# ==========================================
# FIXED VERSION - Changes marked with # FIX:
# ==========================================

async def run_diarize_first_pipeline(audio_bytes, speaker_mgr, stt_engine):
    start_time = time.time()
    
    # 1. Load Audio
    try:
        audio, sr = load_audio_robust(io.BytesIO(audio_bytes))
        if len(audio.shape) > 1: audio = audio.mean(axis=1)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    except Exception as e:
        print(f"❌ Error loading audio for pipeline: {e}")
        return []

    # 2. Preprocess
    audio = preprocess_audio_pipeline(audio)
    
    # FIX: Calculate adaptive energy threshold based on audio RMS
    audio_rms = np.sqrt(np.mean(audio**2))
    energy_threshold = max(audio_rms * 0.03, 0.0001)  # 3% of RMS, minimum 0.0001
    print(f"🎚️ Adaptive Energy Threshold: {energy_threshold:.6f} (Audio RMS: {audio_rms:.6f})")
    
    # 3. Diarize (Full Scan)
    print("🔍 [Pipeline] Step 1: Diarizing...")
    
    # Reuse speaker_mgr
    if not speaker_mgr.loaded: speaker_mgr.load()
    
    window_sec = 2.0
    step_sec = 1.0
    window_samples = int(window_sec * 16000)
    step_samples = int(step_sec * 16000)
    
    timeline = [] # (start, end, speaker_id)
    current_spk = -1
    current_start = 0.0
    
    total_len = len(audio)
    
    # Local speaker registry for this session
    session_speakers = [] # {id, centroid, vector_sum, count}
    
    # FIX: Track statistics for debugging
    total_chunks = 0
    skipped_chunks = 0
    
    def get_embedding(chunk):
        stream = speaker_mgr.extractor.create_stream()
        stream.accept_waveform(16000, chunk)
        stream.input_finished()
        if not speaker_mgr.extractor.is_ready(stream): return None
        emb = np.array(speaker_mgr.extractor.compute(stream))
        n = np.linalg.norm(emb)
        if n > 0: emb /= n
        return emb

    def assign_local(emb, threshold=0.30):
        best_sim = -1.0
        best_idx = -1
        for i, spk in enumerate(session_speakers):
            sim = np.dot(emb, spk['centroid'])
            if sim > best_sim:
                best_sim = sim
                best_idx = i
        
        if best_sim > threshold:
             spk = session_speakers[best_idx]
             spk['vector_sum'] += emb
             spk['count'] += 1
             spk['centroid'] = spk['vector_sum'] / np.linalg.norm(spk['vector_sum'])
             return best_idx
        else:
             new_id = len(session_speakers)
             session_speakers.append({
                 'id': new_id, 'centroid': emb, 'vector_sum': emb, 'count': 1
             })
             return new_id

    # Scan
    for i in range(0, total_len - window_samples, step_samples):
        chunk = audio[i : i+window_samples]
        total_chunks += 1
        
        # FIX: Use RMS instead of mean energy for better detection
        rms = np.sqrt(np.mean(chunk**2))
        
        # FIX: Use adaptive threshold
        if rms < energy_threshold:
            skipped_chunks += 1
            # FIX: Debug logging for skipped chunks
            if i % (16000 * 5) == 0:  # Log every 5 seconds
                print(f"⚡ Skip low energy chunk at {i/16000.0:.2f}s (RMS={rms:.6f} < threshold={energy_threshold:.6f})")
            
            if current_spk != -1:
                timeline.append((current_start, i/16000.0 + window_sec, current_spk))
                current_spk = -1
            continue
            
        emb = get_embedding(chunk)
        if emb is None: continue
        
        spk_id = assign_local(emb)
        ts = i / 16000.0
        
        if spk_id != current_spk:
            if current_spk != -1:
                timeline.append((current_start, ts, current_spk))
            current_spk = spk_id
            current_start = ts
            
    if current_spk != -1:
         timeline.append((current_start, total_len/16000.0, current_spk))

    # FIX: Print scan statistics
    print(f"📊 Scan Stats: {total_chunks} chunks, {skipped_chunks} skipped ({skipped_chunks/total_chunks*100:.1f}%)")
    print(f"📊 Raw Timeline: {len(timeline)} segments")
    
    # FIX: Debug - print all raw timeline segments
    for idx, (start, end, spk) in enumerate(timeline[:20]):  # First 20 segments
        print(f"  [{idx}] {start:.2f} - {end:.2f} Speaker {spk} (duration: {end-start:.2f}s)")
    if len(timeline) > 20:
        print(f"  ... and {len(timeline)-20} more segments")

    # 4. Merge
    print("🔗 [Pipeline] Step 2: Merging...")
    merged_timeline = []
    if timeline:
        curr_start, curr_end, curr_spk = timeline[0]
        for i in range(1, len(timeline)):
            s, e, spk = timeline[i]
            gap = s - curr_end
            
            # FIX: Increase gap tolerance to 3.0s (from 2.0s)
            if spk == curr_spk and gap < 3.0:
                curr_end = max(curr_end, e)
            else:
                # FIX: Decrease minimum duration to 0.3s (from 1.0s)
                if curr_end - curr_start > 0.3:
                    merged_timeline.append((curr_start, curr_end, curr_spk))
                else:
                    print(f"⚠️ Filtered short segment: {curr_start:.2f}-{curr_end:.2f} (duration: {curr_end-curr_start:.2f}s)")
                curr_start = s
                curr_end = e
                curr_spk = spk
        
        # FIX: Decrease minimum duration for final segment
        if curr_end - curr_start > 0.3:
            merged_timeline.append((curr_start, curr_end, curr_spk))
        else:
            print(f"⚠️ Filtered short final segment: {curr_start:.2f}-{curr_end:.2f} (duration: {curr_end-curr_start:.2f}s)")
    
    # FIX: Print merged timeline
    print(f"📊 Merged Timeline: {len(merged_timeline)} segments")
    for idx, (start, end, spk) in enumerate(merged_timeline):
        print(f"  [{idx}] {start:.2f} - {end:.2f} Speaker {spk} (duration: {end-start:.2f}s)")
    
    # FIX: Check for gaps in merged timeline
    if len(merged_timeline) > 1:
        print("🔍 Analyzing gaps between segments:")
        for i in range(len(merged_timeline) - 1):
            gap = merged_timeline[i+1][0] - merged_timeline[i][1]
            if gap > 1.0:  # Report gaps > 1s
                print(f"  ⚠️ GAP: {merged_timeline[i][1]:.2f} → {merged_timeline[i+1][0]:.2f} ({gap:.2f}s)")
        
    # 5. Transcribe Segments
    print("📝 [Pipeline] Step 3: Transcribing...")
    final_output = []
    
    for start, end, spk in merged_timeline:
        s_idx = max(0, int((start - 0.1) * 16000))
        e_idx = min(len(audio), int((end + 0.1) * 16000))
        seg_audio = audio[s_idx:e_idx]
        
        # Use ZipformerEngine's recognizer directly
        # stt_engine is a ZipformerEngine instance
        s = stt_engine.recognizer.create_stream()
        s.accept_waveform(16000, seg_audio)
        stt_engine.recognizer.decode_stream(s)
        text = s.result.text.strip()
        
        if text and len(text) > 1:
            final_output.append({
                "start": start,
                "end": end,
                "speaker": f"Speaker {spk+1}",
                "text": text
            })
            print(f"  ✅ [{start:.2f}-{end:.2f}] Speaker {spk+1}: {text[:50]}...")
        else:
            print(f"  ⚠️ Empty transcription for segment {start:.2f}-{end:.2f}")
            
    elapsed = time.time() - start_time
    print(f"✅ Full Pipeline Complete in {elapsed:.2f}s")
    print(f"📊 Final Output: {len(final_output)} transcribed segments")
    return final_output
