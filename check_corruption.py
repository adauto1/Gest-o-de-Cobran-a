import os

def check_null_bytes(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "rb") as f:
                        content = f.read()
                        if b"\x00" in content:
                            print(f"NULL BYTE FOUND: {path}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    check_null_bytes("app")
