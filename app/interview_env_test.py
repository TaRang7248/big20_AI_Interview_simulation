"""Test script for the AI interview environment.

Run this script inside the `interview_env` virtual environment to verify
that key libraries are installed correctly and that CUDA is available.

Usage (once `interview_env` is activated):

    python interview_env_test.py

The script attempts to import each critical library and prints
information such as version numbers and whether CUDA is available for
PyTorch.  If any import fails, you will see a clear error message.
"""

import importlib
import sys


def check_import(name: str):
    """Try to import a module by name and return the imported module.

    If the import fails, print an error message and return None.
    """
    try:
        module = importlib.import_module(name)
    except Exception as e:
        print(f"❌ Failed to import '{name}': {e}")
        return None
    else:
        print(f"✅ Successfully imported '{name}'")
        return module


def main() -> None:
    """Run a series of import checks and report versions and CUDA status."""
    print("\n=== Environment Test ===\n")

    # Check PyTorch and related packages
    torch = check_import("torch")
    if torch is not None:
        print(f"PyTorch version: {torch.__version__}")
        if torch.cuda.is_available():
            print(f"CUDA is available. GPU device count: {torch.cuda.device_count()}")
            print(f"Current CUDA device: {torch.cuda.get_device_name(torch.cuda.current_device())}")
        else:
            print("CUDA is NOT available. Using CPU fallback.")

    # TorchVision
    torchvision = check_import("torchvision")
    if torchvision is not None:
        # torchvision.__version__ can be a function or attribute depending on version
        version = getattr(torchvision, "__version__", None)
        print(f"TorchVision version: {version}")

    # TorchAudio
    torchaudio = check_import("torchaudio")
    if torchaudio is not None:
        version = getattr(torchaudio, "__version__", None)
        print(f"TorchAudio version: {version}")

    # pyannote.audio
    pyannote = check_import("pyannote.audio")
    if pyannote is not None:
        version = getattr(pyannote, "__version__", None)
        print(f"pyannote.audio version: {version}")

    # numpy
    numpy_mod = check_import("numpy")
    if numpy_mod is not None:
        print(f"NumPy version: {numpy_mod.__version__}")

    # Additional checks can be added here (e.g., whisper, fastapi, etc.)

    print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")
        sys.exit(1)