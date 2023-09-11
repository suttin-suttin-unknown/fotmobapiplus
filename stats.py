"""
Helper script for checking storage etc.
"""

import os
import psutil

paths = []
for root, _, files in os.walk("data"):
    for file in files:
        paths.append(os.path.join(root, file))

total_size = 0
for path in paths:
    total_size += os.path.getsize(path)

if os.path.exists("fotmob.json"):
    total_size += os.path.getsize("fotmob.json")

total_size = total_size / (1024 * 1024)

print(f"Total Size: {total_size:.2f} MB")

total_storage = psutil.disk_usage("/").free
total_storage = total_storage / (1024 ** 3)

print(f"Total storage available: {total_storage:.2f} GB")
