const uploadForm = document.getElementById('uploadForm');
const askForm = document.getElementById('askForm');
const clearButton = document.getElementById('clearButton');
const exportButton = document.getElementById('exportButton');
const chatBox = document.getElementById('chatBox');

uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return alert("Please choose an Excel file!");

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const res = await fetch('/upload/', { method: 'POST', body: formData });
    const data = await res.json();
    addMessage("System", data.message || data.error);
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

    const res = await fetch('/ask/', { method: 'POST', body: formData });
    const data = await res.json();
    addMessage("Bot", data.answer || data.error);
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
    let senderClass = "";
    if (sender.toLowerCase() === "system") senderClass = "system";
    else if (sender.toLowerCase() === "bot") senderClass = "bot";

    message.innerHTML = `<b class="${senderClass}">${sender}</b> ${text}`;
    chatBox.appendChild(message);
    chatBox.scrollTop = chatBox.scrollHeight;
}
