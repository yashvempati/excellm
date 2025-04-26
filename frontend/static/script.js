document.addEventListener("DOMContentLoaded", () => {
    const uploadForm = document.getElementById("upload-form");
    const questionForm = document.getElementById("question-form");
    const clearBtn = document.getElementById("clear-btn");
    const exportBtn = document.getElementById("export-btn");
    const chatBox = document.getElementById("chat-box");

    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById("file-upload");
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        const response = await fetch("/upload/", {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        alert(result.message || result.error);
    });

    questionForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const questionInput = document.getElementById("question-input");
        const formData = new FormData();
        formData.append("question", questionInput.value);

        const response = await fetch("/ask/", {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        if (result.answer) {
            const message = document.createElement("div");
            message.className = "chat-message";
            message.innerHTML = `<strong>You:</strong> ${questionInput.value}<br><strong>Bot:</strong> ${result.answer}`;
            chatBox.appendChild(message);
            chatBox.scrollTop = chatBox.scrollHeight;
            questionInput.value = "";
        } else {
            alert(result.error);
        }
    });

    clearBtn.addEventListener("click", async () => {
        const response = await fetch("/clear/", { method: "POST" });
        const result = await response.json();
        alert(result.message || result.error);
        chatBox.innerHTML = "";
    });

    exportBtn.addEventListener("click", () => {
        window.location.href = "/export/";
    });
});