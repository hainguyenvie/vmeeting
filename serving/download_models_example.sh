
# Create models directory
mkdir -p models/zipformer
mkdir -p models/speaker

# 1. Download Zipformer (En)
# This is a good standard model. If you have your own int8 model, use that instead.
cd models/zipformer
echo "Downloading Zipformer..."
wget -q https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-en-2023-06-26.tar.bz2
tar xvf sherpa-onnx-zipformer-en-2023-06-26.tar.bz2
# Move files up one level and cleanup
mv sherpa-onnx-zipformer-en-2023-06-26/* .
rmdir sherpa-onnx-zipformer-en-2023-06-26
rm sherpa-onnx-zipformer-en-2023-06-26.tar.bz2
cd ../..

# 2. Download 3D-Speaker (The one you asked for)
cd models/speaker
echo "Downloading 3D-Speaker..."
wget -q https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
cd ../..

echo "✅ Downloads complete! Models are ready in ./models"
