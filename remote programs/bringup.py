import shutil
import subprocess

if __name__ == "__main__":
    for name in ["camera_publisher.py", "rotsub.py", "remconpub.py"]:
        subprocess.run([shutil.which("python3"), name])
