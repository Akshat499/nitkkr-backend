import os
import aiofiles
from fastapi import UploadFile
from config import UPLOAD_DIR

NOTIFICATION_DIR = "uploads/notifications"
ANNOUNCEMENT_DIR = "uploads/announcements"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(NOTIFICATION_DIR, exist_ok=True)
os.makedirs(ANNOUNCEMENT_DIR, exist_ok=True)

async def save_file(file: UploadFile) -> str:
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    return file_path

async def save_notification_file(file: UploadFile) -> str:
    file_path = os.path.join(NOTIFICATION_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    return file_path

async def save_announcement_file(file: UploadFile) -> str:
    file_path = os.path.join(ANNOUNCEMENT_DIR, file.filename)
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    return file_path