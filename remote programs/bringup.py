import shutil
import subprocess

if __name__ == "__main__":
    for name in ["rotsub.py", "remconpub.py"]:
        subprocess.Popen([shutil.which("python3"), "~/CourtHelp/" + name])
    subprocess.Popen([shutil.which("ros2"), "launch", "tutlebot3_bringup", "robot.launch.py"])
