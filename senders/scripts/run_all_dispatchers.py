import pathlib
import subprocess

dispatcher_dir = pathlib.Path(__file__).parent.parent / "dispatchers"
failures = []

for pyfile in dispatcher_dir.glob("*.py"):
    module_name = f"dispatchers.{pyfile.stem}"
    print(f"Running {module_name} ...")
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", module_name],
            capture_output=True,
            text=True,
            check=True,
            cwd=dispatcher_dir.parent  # This sets working dir to 'senders'
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
