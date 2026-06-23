from fastapi import FastAPI
from routers import parking, camera, auth
from core.celery_app import celery_app

app = FastAPI(title="Parking System")

app.include_router(auth.router)
app.include_router(parking.router)
app.include_router(camera.router)

@app.on_event("startup")
async def startup_event():
    # При необходимости можно проверить соединение с Redis и т.п.
    print("Приложение запущено")

@app.get("/task/check-expiring")
async def trigger_check_expiring():
    task = celery_app.send_task("tasks.parking_tasks.check_expiring_sessions")
    return {"task_id": task.id}