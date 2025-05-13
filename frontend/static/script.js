const uploadForm = document.getElementById('uploadForm');
const askForm = document.getElementById('askForm');
const clearButton = document.getElementById('clearButton');
const exportButton = document.getElementById('exportButton');
const chatBox = document.getElementById('chatBox');

uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) {
        addMessage("System", "Please choose an Excel file!");
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.endsWith('.xlsx')) {
        addMessage("System", "Only .xlsx files are allowed!");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    // Show loading message while uploading
    addMessage("System", "Uploading file, please wait...");

    try {
        const res = await fetch('/upload/', {
            method: 'POST',
            body: formData,
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.detail || errorData.error || 'Failed to upload file');
        }
        
        const data = await res.json();
        addMessage("System", data.message || "File uploaded successfully!");
        
        // Clear the file input after successful upload
        fileInput.value = '';
        
    } catch (error) {
        addMessage("System", `Error: ${error.message || "Failed to upload file"}`);
        console.error('Upload error:', error);
    }
});

askForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const questionInput = document.getElementById('questionInput');
    const question = questionInput.value.trim();
    if (!question) return;

    addMessage("You", question);
    questionInput.value = "";

    const formData = new FormData();
    formData.append('question', question);

    // Show loading message while waiting for response
    addMessage("System", "Getting response from the bot...");

    const res = await fetch('/ask/', { method: 'POST', body: formData });
    const data = await res.json();

    // Show bot's answer or error
    if (res.ok) {
        addMessage("Bot", data.answer || "No answer found.");
    } else {
        addMessage("Bot", data.error || "Error occurred while processing your question.");
    }
});

clearButton.addEventListener('click', async () => {
    const res = await fetch('/clear/', { method: 'POST' });
    const data = await res.json();
    addMessage("System", data.message || data.error);
});

exportButton.addEventListener('click', async () => {
    const res = await fetch('/export/');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = 'chat_history.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
});

function addMessage(sender, text) {
    const message = document.createElement('div');
    message.innerHTML = `<b>${sender}:</b> ${text}`;
    chatBox.appendChild(message);
    chatBox.scrollTop = chatBox.scrollHeight;
}
