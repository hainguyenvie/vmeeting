import sys
import unittest
from unittest.mock import MagicMock
import numpy as np
import time

# Mock sherpa_onnx before importing stt_server (or just copy class logic to test isolated)
# Since importing stt_server might try to load real models, let's copy the class logic we want to test
# or better, just import the file but mock os.getenv to avoid loading real models immediately

# Minimal Mock of SpeakerManager for logic testing
class SpeakerManagerLogicTest(unittest.TestCase):
    def setUp(self):
        # Recreate the logic we implemented in stt_server.py
        self.registry = {} 
        self.next_id = 0
        self.threshold = 0.45
        self.last_speaker_id = -1
        self.last_speaker_time = 0
        
    def identify_simulated(self, embedding, current_time):
        # Norm
        norm = np.linalg.norm(embedding)
        if norm > 0: embedding /= norm
        
        best_score = -1
        best_id = -1
        
        for pid, data in self.registry.items():
            score = np.dot(embedding, data['centroid'])
            
            # Temporal Bias Logic
            if pid == self.last_speaker_id and (current_time - self.last_speaker_time) < 3.0:
                 score += 0.1 
                 
            if score > best_score:
                best_score = score
                best_id = pid
        
        final_id = -1
        if best_score > self.threshold:
            final_id = best_id
            
            # Update centroid (Moving Average)
            alpha = 0.95
            old_centroid = self.registry[best_id]['centroid']
            new_centroid = alpha * old_centroid + (1 - alpha) * embedding
            new_norm = np.linalg.norm(new_centroid)
            if new_norm > 0: new_centroid /= new_norm
            
            self.registry[best_id]['centroid'] = new_centroid
            self.registry[best_id]['count'] += 1
            self.registry[best_id]['last_seen'] = current_time
            
        else:
            final_id = self.next_id
            self.registry[final_id] = {
                'centroid': embedding, 
                'count': 1,
                'last_seen': current_time
            }
            self.next_id += 1
            
        self.last_speaker_id = final_id
        self.last_speaker_time = current_time
            
        return final_id, best_score

    def test_bias_application(self):
        print("\nTest: Temporal Bias Application")
        # 1. New Speaker 0
        emb1 = np.array([1.0, 0.0])
        t1 = 1000.0
        sid, score = self.identify_simulated(emb1, t1)
        self.assertEqual(sid, 0)
        print(f"  Step 1: Created Speaker {sid}")

        # 2. Same Speaker, slightly different embedding (0.4 similarity without bias)
        # 0.4 < 0.45 Threshold, but Bias (+0.1) should make it 0.5 > 0.45
        emb2 = np.array([0.4, np.sqrt(1 - 0.4**2)]) # Dot product with [1,0] is 0.4
        t2 = 1000.5 # 0.5s later (within 3s window)
        
        sid, score = self.identify_simulated(emb2, t2)
        print(f"  Step 2: Score raw ~0.4, with bias should be >0.45. Result ID: {sid}")
        self.assertEqual(sid, 0, "Should match Speaker 0 due to bias")

    def test_bias_expiry(self):
        print("\nTest: Temporal Bias Expiry")
        # 1. New Speaker 0
        emb1 = np.array([1.0, 0.0])
        t1 = 1000.0
        sid, _ = self.identify_simulated(emb1, t1)
        
        # 2. Same Speaker, 0.4 similarity, 5s later (Bias expired)
        emb2 = np.array([0.4, np.sqrt(1 - 0.4**2)])
        t2 = 1005.0 
        
        sid, _ = self.identify_simulated(emb2, t2)
        print(f"  Step 2: Score raw ~0.4, bias expired. Result ID: {sid}")
        self.assertNotEqual(sid, 0, "Should NOT match Speaker 0 (Bias expired)")
        self.assertEqual(sid, 1, "Should create new Speaker 1")

    def test_centroid_update(self):
        print("\nTest: Centroid Update")
        # 1. Speaker 0: [1, 0]
        emb1 = np.array([1.0, 0.0])
        self.identify_simulated(emb1, 1000.0)
        
        # 2. Speaker 0: [0, 1] (Perfectly orthogonal, but let's force match manually or set high bias?)
        # Let's use [0.6, 0.8] -> similarity 0.6 > 0.45
        emb2 = np.array([0.6, 0.8])
        self.identify_simulated(emb2, 1001.0)
        
        # Centroid should move towards emb2
        # Old: [1, 0]
        # New: 0.95*[1,0] + 0.05*[0.6, 0.8] = [0.95 + 0.03, 0.04] = [0.98, 0.04]
        # Normalized...
        c = self.registry[0]['centroid']
        print(f"  Updated Centroid: {c}")
        self.assertTrue(c[0] < 1.0, "Centroid should have moved away from [1,0]")
        self.assertTrue(c[1] > 0.0, "Centroid should have picked up y-component")

if __name__ == '__main__':
    unittest.main()
