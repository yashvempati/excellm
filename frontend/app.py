import os
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from backend.chat_backend import ChatData

app = FastAPI()

# Initialize Chat Engine
chat_engine = ChatData()

# Serve static frontend
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        return f.read()

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        excel_stream = io.BytesIO(file_content)
        chat_engine.ingest_excel(excel_stream)
        return JSONResponse({"message": f"Successfully ingested {file.filename}"})
    except Exception as e:
        return JSONResponse({"error": f"File upload failed: {str(e)}"}, status_code=400)

@app.post("/ask/")
async def ask_question(question: str = Form(...)):
    try:
        answer = chat_engine.ask(question)
        return JSONResponse({"answer": answer})
    except Exception as e:
        return JSONResponse({"error": f"Answering failed: {str(e)}"}, status_code=500)

@app.post("/clear/")
async def clear_data():
    try:
        chat_engine.clear()
        return JSONResponse({"message": "All data cleared."})
    except Exception as e:
        return JSONResponse({"error": f"Clearing failed: {str(e)}"}, status_code=500)

@app.get("/export/")
async def export_chat():
    try:
        history_text = chat_engine.export_chat_history()
        return StreamingResponse(
            iter([history_text]),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=chat_history.txt"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Export failed: {str(e)}"}, status_code=500)

