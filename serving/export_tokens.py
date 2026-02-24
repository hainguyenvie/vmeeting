
import sentencepiece as spm
import sys
import os

def export_tokens(bpe_model_path, output_path):
    if not os.path.exists(bpe_model_path):
        print(f"Error: {bpe_model_path} not found")
        return

    sp = spm.SentencePieceProcessor()
    sp.load(bpe_model_path)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for i in range(sp.get_piece_size()):
            piece = sp.id_to_piece(i)
            # Sherpa needs specific format: "token id"
            # And handles generic tokens differently but simple 'space' separated usually works
            f.write(f"{piece} {i}\n")
            
    print(f"Successfully exported {output_path} from {bpe_model_path}")

if __name__ == "__main__":
    bpe_path = "models/zipformer/bpe.model"
    tokens_path = "models/zipformer/tokens.txt"
    
    if len(sys.argv) > 1: bpe_path = sys.argv[1]
    if len(sys.argv) > 2: tokens_path = sys.argv[2]
    
    export_tokens(bpe_path, tokens_path)
