import os

# Create the directory if it doesn't exist
path = "static/sounds"
if not os.path.exists(path):
    os.makedirs(path)
    print(f"Created directory: {path}")

# Create empty placeholder files so the 404 error stops
files = ["sniper_target.mp3", "sell_alert.mp3"]
for f in files:
    full_path = os.path.join(path, f)
    if not os.path.exists(full_path):
        with open(full_path, "wb") as audio:
            audio.write(b"") # Writes an empty file
        print(f"Created placeholder: {full_path}")
