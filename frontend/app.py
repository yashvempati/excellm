from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
import io
from chat_backend import ChatData
import os
import threading
import time
import requests

app = Flask(__name__)
chat_data = ChatData()

# Serve the index.html file manually
with open("index.html", "r") as f:
    INDEX_HTML = f.read()

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_file(f"static/{filename}")

@app.route("/upload/", methods=["POST"])
def upload_excel():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    try:
        file_bytes = io.BytesIO(file.read())
        chat_data.ingest_excel(file_bytes)
        return jsonify({"message": f"File '{secure_filename(file.filename)}' processed successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ask/", methods=["POST"])
def ask_question():
    question = request.form.get("question", "")
    if not question:
        return jsonify({"error": "No question provided."}), 400

    try:
        answer = chat_data.ask(question)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear/", methods=["POST"])
def clear_data():
    chat_data.clear()
    return jsonify({"message": "Data cleared successfully."})

@app.route("/export/", methods=["GET"])
def export_chat():
    export_text = chat_data.export_chat_history()
    export_file = io.BytesIO(export_text.encode("utf-8"))
    export_file.seek(0)
    return send_file(export_file, mimetype="text/plain", as_attachment=True, download_name="chat_history.txt")


# 🔁 Keep-alive pinger to stop Render sleeping
def keep_alive():
    ping_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not ping_url:
        print("RENDER_EXTERNAL_URL not set. Self-ping disabled.")
        return

    def ping_loop():
        while True:
            try:
                print(f"Pinging self at {ping_url}")
                requests.get(ping_url)
            except Exception as e:
                print(f"Ping failed: {e}")
            time.sleep(14 * 60)  # every 14 minutes

    threading.Thread(target=ping_loop, daemon=True).start()

keep_alive()

if __name__ == "__main__":
    app.run(debug=True)
