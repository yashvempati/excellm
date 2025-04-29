from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.chat_backend import ChatData

app = FastAPI()
chat = ChatData()

# Allow frontend JS to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder (script.js, styles.css)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Serve index.html
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# Upload Excel file
@app.post("/upload/")
async def upload_file(file: UploadFile):
    try:
        contents = await file.read()
        chat.ingest_excel(contents)
        return {"message": f"Uploaded and processed {file.filename}"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

# Ask a question
@app.post("/ask/")
async def ask_question(question: str = Form(...)):
    try:
        answer = chat.ask(question)
        return {"answer": answer}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Clear chat
@app.post("/clear/")
async def clear_chat():
    chat.clear()
    return {"message": "Chat history cleared."}

# Export chat history
@app.get("/export/")
async def export_chat():
    history = chat.export_chat_history()
    file_path = "/tmp/chat_history.txt"
    with open(file_path, "w") as f:
        f.write(history)
    return FileResponse(path=file_path, filename="chat_history.txt", media_type="text/plain")
