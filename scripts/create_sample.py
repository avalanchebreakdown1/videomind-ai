"""Create locally synthesized speech; no downloaded or copyrighted sample required."""
from pathlib import Path
import subprocess


TEXT = (
    "Welcome to Video Mind. Today we will learn how solar panels produce electricity. "
    "Solar panels convert sunlight into electrical energy. "
    "This energy can power lights and charge batteries. "
    "The recording ends with the words thank you for listening."
)


if __name__ == "__main__":
    folder = Path("samples/generated")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "speech.wav"
    subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
        "-f", "lavfi", "-i", f"flite=text={TEXT}:voice=slt",
        "-ar", "16000", "-ac", "1", str(target),
    ], check=True, timeout=60)
    (folder / "expected.txt").write_text(TEXT + "\n", encoding="utf-8")
    print(target)
