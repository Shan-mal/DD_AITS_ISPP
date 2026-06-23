from fastapi import APIRouter, UploadFile, File
from tasks.recognition_tasks import process_entry_camera
import shutil
import os

router = APIRouter()

@router.post("/camera/entry")
async def camera_entry(file: UploadFile = File(...)):
    temp_path = f"/tmp/parking_cam_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    task = process_entry_camera.delay(temp_path)
    return {"task_id": task.id}