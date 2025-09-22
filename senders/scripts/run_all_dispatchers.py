import pathlib
import subprocess

dispatcher_dir = pathlib.Path(__file__).parent.parent / "dispatchers"
failures = []

for pyfile in dispatcher_dir.glob("*.py"):
    print(f"Running {pyfile} ...")
    try:
        result = subprocess.run(
            [f"cd  /home/runner/work/linebot/linebot/senders && uv run python -m dispatchers.{str(pyfile.name).replace(",py", "")}"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"{pyfile.name} succeeded.")
    except subprocess.CalledProcessError as e:
        print(f"{pyfile.name} failed!")
        failures.append({
            "file": pyfile.name,
            "returncode": e.returncode,
            "stdout": e.stdout,
            "stderr": e.stderr
        })

print("\nSummary:")
if failures:
    for fail in failures:
        print(f"FAILED: {fail['file']}")
        print(f"Return code: {fail['returncode']}")
        print(f"Stdout:\n{fail['stdout']}")
        print(f"Stderr:\n{fail['stderr']}")
        print("-" * 40)
else:
    print("All dispatcher scripts ran successfully.")
