import os
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

def download_file(url, dest):
    if not os.path.exists(dest):
        print(f"Downloading {url} to {dest}...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"Downloaded {dest}")
        except Exception as e:
            print(f"Failed to download {dest}: {e}")
    else:
        print(f"File already exists: {dest}")

if __name__ == "__main__":
    base_dir = r"C:\big20\big20_AI_Interview_simulation\LDW\text09\Wav2Lip"
    
    # 1. Wav2Lip-GAN checkpoint
    ckpts_dir = os.path.join(base_dir, "checkpoints")
    os.makedirs(ckpts_dir, exist_ok=True)
    wav2lip_gan_url = "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth"
    download_file(wav2lip_gan_url, os.path.join(ckpts_dir, "wav2lip_gan.pth"))
    
    # 2. Face detection model
    sfd_dir = os.path.join(base_dir, "face_detection", "detection", "sfd")
    os.makedirs(sfd_dir, exist_ok=True)
    sfd_url = "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
    download_file(sfd_url, os.path.join(sfd_dir, "s3fd.pth"))
