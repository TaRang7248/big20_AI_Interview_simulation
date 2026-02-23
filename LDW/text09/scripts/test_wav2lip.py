import os
import subprocess
import glob

test_audio = r"C:\big20\big20_AI_Interview_simulation\LDW\text09\uploads\tts_audio\test.mp3"
if not os.path.exists(test_audio):
    os.makedirs(os.path.dirname(test_audio), exist_ok=True)
    with open(test_audio, "wb") as f:
        pass

wav2lip_dir = r"C:\big20\big20_AI_Interview_simulation\LDW\text09\Wav2Lip"
inference_script = os.path.join(wav2lip_dir, "inference.py")
checkpoint_path = os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth")
face_image = r"C:\big20\big20_AI_Interview_simulation\LDW\text09\data\면접관.png"

mp3_files = glob.glob(r"C:\big20\big20_AI_Interview_simulation\LDW\text09\uploads\tts_audio\*.mp3")
if mp3_files:
    test_audio = max(mp3_files, key=os.path.getctime)
    print(f"Using actual audio: {test_audio}")
else:
    print("No mp3 found")

cmd = [
    "python", inference_script,
    "--checkpoint_path", checkpoint_path,
    "--face", face_image,
    "--audio", test_audio,
    "--outfile", "test_out.mp4",
    "--pads", "0", "20", "0", "0"
]

print("Running command:", " ".join(cmd))
result = subprocess.run(cmd, cwd=wav2lip_dir, capture_output=True, text=True)
print("RETURN CODE:", result.returncode)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
