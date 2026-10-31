# Company Document AI

A locally hosted chatbot API that answers customer questions using only your own company documents (courses, fees, policies, FAQs). It runs on your own computer with free, open-source tools. No paid AI service is used and no data leaves your machine.

Everything is operated through REST APIs, so Postman is all you need to upload documents and ask questions.

## How it works

1. **Upload** a document (PDF, DOCX, TXT or MD). The system saves it and gives it an ID.
2. **Process** the document. The system reads the text, cuts it into small pieces, turns each piece into numbers (embeddings) and stores them in a database on disk.
3. **Ask** a question. The system finds the pieces of text closest to the question and gives them to the local AI model, which writes a friendly answer using only those facts.
4. If the answer is not in the documents, the customer gets a polite "please call us" message. The bot never guesses.

The knowledge base is saved on disk, so it survives restarts. Adding a new document never rebuilds the whole database, and the AI model is never retrained.

## Tools used

| Tool | Purpose |
|---|---|
| Flask | The REST API |
| Ollama | Runs the AI models locally |
| Qwen2.5 (3b for testing, 7b for production) | Writes the answers (see the license warning under Configuration) |
| nomic-embed-text | Turns text into numbers for searching |
| ChromaDB | Stores the document pieces on disk |
| PyMuPDF, python-docx | Read PDF and Word files |
| Postman | Used to operate and test everything |

## Requirements

- Windows 10/11 (Mac and Linux also work, see the notes in each step)
- **Python 3.11 or 3.12.** Do not use Python 3.13 or newer for now, because several packages do not have ready-made installers for it yet and the install will fail.
- At least 8 GB of RAM and about 5 GB of free disk space
- Internet connection for the first-time downloads
- Postman (free): https://www.postman.com/downloads/

## Installation

### Step 1: Install Python 3.12
Download Python 3.12 from https://www.python.org/downloads/ and run the installer. Tick **Add python.exe to PATH**. Other Python versions can stay installed.

Check in a new PowerShell window:
```
py -0
```
You should see `3.12` in the list.

### Step 2: Install Ollama
Download Ollama from https://ollama.com/download and install it. Keep the Ollama app running in the background (look for its icon in the taskbar tray). Close and reopen your terminal after installing, then check:
```
ollama --version
```

### Step 3: Download the AI models
```
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```
The first model is about 2 GB. Confirm both are installed:
```
ollama list
```

### Step 4: Open the project folder
```
cd path\to\company_document_ai
```

### Step 5: Create the virtual environment
```
py -3.12 -m venv venv
venv\Scripts\activate
python --version
```
The last command must show `Python 3.12.x`, and your prompt must start with `(venv)`.

If PowerShell blocks the activation with "running scripts is disabled", run this once and try again:
```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Mac/Linux: use `python3.12 -m venv venv` and `source venv/bin/activate`.

### Step 6: Install the packages
```
pip install -r requirements.txt
```

### Step 7: Create your settings file
```
copy .env.example .env
```
(Mac/Linux: `cp .env.example .env`.) The default values work as they are. See the Configuration section if you want to change anything.

### Step 8: Start the app
```
python app.py
```
Leave this window open while you use the app. Open http://127.0.0.1:5000/health in your browser. You should see `"status": "healthy"`.

Every time you open a new terminal, activate the environment first (`venv\Scripts\activate`) and then run `python app.py`.

## Using Postman

1. Open Postman and click **Import**.
2. Choose `postman/company_document_ai.postman_collection.json`.
3. Click the collection name, open the **Variables** tab, and check that `base_url` is `http://127.0.0.1:5000`. Leave `api_key` empty unless you set `API_KEY` in `.env`.

### The workflow

| Request | What it does |
|---|---|
| 1. Upload document | Saves a file and returns its `document_id` (set automatically for the next requests) |
| 2. Process (index) document | Reads, cuts and stores the file so it can be searched |
| 3. Check document status | Shows the status: uploaded, processing, indexed or failed |
| 4. List documents | Lists all documents with their IDs and statuses |
| 5. Ask a question | Sends a question and returns the answer and its sources |
| 6. Reindex document | Updates a document whose content changed |
| 7. Delete document | Deletes the file, its details and all its stored pieces |
| 8. Health check | Checks Flask, Ollama, both models and the database |

### Adding a document
1. In request 1, open **Body**, select the `file` row, choose **File**, pick your file, and click **Send**. You should get status `201`.
2. In request 2, click **Send**. You should see `"status": "indexed"`.
3. Repeat for each file. Upload only one file per request.

To try the system with sample files, use the documents in the `documents_example/upload_these` folder (see **Example documents** below).

Important: uploading only saves the file. The chatbot cannot use it until you also run request 2 (Process).

### Asking a question
In request 5, set the body to:
```json
{ "question": "How long is the Python course?" }
```
Example response:
```json
{
  "success": true,
  "question": "How long is the Python course?",
  "answer": "The Python Algo Class lasts 3 months...",
  "answer_found": true,
  "sources": [{ "document_id": "doc_123", "filename": "02_courses_and_fees.md", "page": null }]
}
```
When the answer is not in the documents, `answer_found` is `false` and the `answer` is the polite "please call us" message.

### Updating a document
1. Edit the file on your computer.
2. In request 6, put the document's ID in the URL (for example `{{base_url}}/api/documents/doc_8172b18572a6/reindex`).
3. In **Body**, tick the `file` row, select the edited file (it must be the same file type), and click **Send**.

The old pieces are replaced only after the new ones are saved, so a failed update never damages the knowledge base.

### Deleting a document
In request 7, put the document's ID at the end of the URL and click **Send**. Check the ID carefully because deleted documents cannot be recovered.

### Starting again from zero
1. Stop the app with Ctrl+C.
2. In the `storage` folder, delete everything inside `documents`, `metadata` and `vector_db` (keep the folders).
3. Start the app again with `python app.py`.

## Example documents (demo data)

The project includes a ready-made set of sample CodertechPRO documents in the `documents_example` folder, so you can try the whole system straight away.

```
documents_example/
├── README_READ_FIRST.txt        Explains that the example details are not real
├── upload_these/                The 8 documents to upload in Postman
└── do_not_upload/
    └── test_questions.md        Test questions with expected answers (do not upload)
```

**Important:** the files marked `_DEMO` contain example details that were made up for demonstration only (for example the syllabus, some batch dates, installments, the refund rule, custom bot prices, lab timings and hiring steps). They are not confirmed company information. Use them for testing and demos only. Before real customers use the chatbot, replace them with your real details.

### How to load the example documents
1. Start the app (`python app.py`).
2. In Postman, request 1 (Upload document), open **Body**, select the `file` row, choose **File**, and pick the first file from `documents_example/upload_these`. Click **Send**.
3. In request 2 (Process), click **Send**.
4. Repeat steps 2 and 3 for each of the 8 files, one file at a time.
5. In request 4 (List documents), check that all 8 are `indexed`.
6. Ask the questions from `documents_example/do_not_upload/test_questions.md` in request 5 and compare the answers.

To remove the example data later, see **Starting again from zero** above, then upload your real documents.

## Preparing documents for upload

The chatbot is only as accurate as the documents. This section applies on your computer and on a server.

### Supported formats

| Format | Use it? | Notes |
|---|---|---|
| `.md` (Markdown) | Best | Clean text, headings are kept. Use this for most documents |
| `.txt` | Best | Plain text in UTF-8 |
| `.docx` (Word) | Good | Paragraphs and tables are read. Images, text boxes, headers and footers are ignored |
| `.pdf` | Good, with care | Only text-based PDFs work. Page numbers are saved and shown in the sources |
| Scanned PDFs, images, `.xlsx`, `.csv`, `.pptx`, `.html` | Not supported | Convert the content to `.md` or `.docx` first (run OCR on scans) |

Size limit: 25 MB per file by default (`MAX_UPLOAD_MB`). Real documents are far smaller, so keep each file under 1 MB and about 2 to 5 pages.

### Rules for writing the documents

1. **One topic per file.** For example: courses, services, careers, contact, policies. Do not mix everything in one long file.
2. **Write in English, in short, clear sentences.** Mention the company name (CodertechPRO) inside the sentences, because the system cuts files into small pieces and each piece must make sense on its own. The embedding model is mainly English, so Malayalam or mixed-language documents and questions are searched less accurately.
3. **Use a question-and-answer style** for common questions, with one fact per answer.
4. **Turn tables into sentences.** For example "The Master Course costs Rs. 20,000 and lasts 12 weeks" instead of a table.
5. **Never keep two different versions of the same fact** (for example two fees) in different files. Keep each fact in one place where possible. When a fact changes, update every file that mentions it and reindex each one.
6. **Write dates and amounts in full** ("starts on December 1st, 2026", "Rs. 20,000"). Review the files every month and whenever a batch, fee or policy changes.
7. **Only put in facts that customers may see.** Anything in a document can appear in an answer. Never upload passwords, internal salaries, personal data of students, or confidential contracts.
8. **Do not upload notes to yourself**, test lists, drafts, or files with "FILL IN" placeholders.
9. **Do not write instructions to the AI** inside documents (for example "always say..."). Documents are treated as facts only.
10. **Use clear file names**: numbered, lowercase, no spaces or special characters, for example `02_courses_and_fees.md`. The same file content cannot be uploaded twice (the system rejects exact duplicates).

### After every upload
1. Run request 2 (Process) and check that request 4 (List documents) shows `indexed`.
2. Ask 5 to 10 real customer questions (use `test_questions.md` as a starting point).
3. If an answer is wrong, find the file that is missing or contradicting the fact, fix it, and reindex it (request 6).

Keep a safe copy of the approved, final documents outside the `storage` folder, so the knowledge base can always be rebuilt by uploading them again.

## How the chat replies

- Greetings and thanks ("hi", "how are you", "thank you", "bye") get a friendly ready-made reply without searching.
- Other questions are answered from the documents in a short, friendly tone.
- If the answer is not in the documents, the "not found" message is shown. To change it, edit `NOT_FOUND_MESSAGE` in `services/llm_service.py`.
- To change the tone of the answers, edit `SYSTEM_PROMPT` in `services/llm_service.py`.
- To change the greeting replies, edit the `smalltalk` function in `routes/chat_routes.py`.

Restart the app after changing any code file.

## Configuration (.env)

| Setting | Default | Meaning |
|---|---|---|
| FLASK_HOST / FLASK_PORT | 127.0.0.1 / 5000 | Where the API runs |
| FLASK_DEBUG | false | Keep false |
| OLLAMA_BASE_URL | http://127.0.0.1:11434 | Where Ollama runs |
| LLM_MODEL | qwen2.5:3b | The model that writes answers |
| EMBEDDING_MODEL | nomic-embed-text | The model that creates embeddings |
| DOCUMENT_STORAGE_PATH | ./storage/documents | Where uploaded files are saved |
| VECTOR_DB_PATH | ./storage/vector_db | Where the database is saved |
| CHUNK_SIZE / CHUNK_OVERLAP | 800 / 120 | How documents are cut. Changing these requires reindexing every document |
| TOP_K | 4 | How many pieces of text are sent to the AI per question |
| RELEVANCE_MAX_DISTANCE | 1.0 | How loosely a piece may match the question (lower is stricter) |
| MAX_UPLOAD_MB | 25 | Largest allowed upload |
| LLM_TIMEOUT_SECONDS | 120 | How long to wait for the AI to answer |
| API_KEY | (empty) | If set, every request must send the header `X-API-Key` |

Only switch `LLM_MODEL` to a bigger model (for example `qwen2.5:7b`) after `ollama list` shows it. A bigger model is more accurate but slower.

**License warning:** `qwen2.5:3b` is released under the Qwen Research License, which allows research and evaluation only. Use it for testing and demos. For a real company deployment, use `qwen2.5:7b` (Apache 2.0, commercial use allowed), or get a commercial license from Alibaba Cloud for the 3b model. `nomic-embed-text` is Apache 2.0. Always re-check the license on each model's Ollama page before going live.

## Security notes

- Before any public deployment, set a long random `API_KEY` in `.env` and put the same value in the Postman `api_key` variable. Requests then need the `X-API-Key` header.
- Serve the app behind HTTPS with a production server (for example waitress) instead of `python app.py`.
- Uploaded files are validated for type and size, and internal file paths are never shown in responses.
- Document text is treated as untrusted. The AI is instructed never to follow instructions found inside documents.
- For several companies on one server, run one copy of the app per company with separate storage paths.

## Running the tests

```
pytest
```
The tests use fake stand-ins for Ollama and ChromaDB, so they run quickly without any models.

## Deploying to a server

### What the server needs

The AI model runs on the server, so the server's memory and processor decide how fast the chatbot answers. The numbers below are approximate estimates, not exact measurements. Measure on your own server (Task Manager on Windows, `htop` on Linux, and `ollama ps`).

| Setup | CPU | RAM | Disk | Model | Typical answer time | Good for |
|---|---|---|---|---|---|---|
| Demo / testing (CPU only) | 4 cores | 8 GB | 20 GB SSD | `qwen2.5:3b` (research license only) | 10 to 30 seconds | 1 to 2 people testing |
| Small production (CPU only) | 8 cores | 16 GB | 40 GB SSD | `qwen2.5:7b` | 20 to 60 seconds | Very light traffic |
| Recommended production | 4 to 8 cores | 16 GB, plus a GPU with 8 GB or more VRAM (for example NVIDIA T4 or RTX 3060) | 50 GB SSD | `qwen2.5:7b` | 2 to 6 seconds | A website chatbot with several visitors |

Where the memory goes (approximate):
- `qwen2.5:3b`: about 2 GB file, about 3 to 4 GB of RAM while answering.
- `qwen2.5:7b`: about 4.7 GB file, about 6 to 8 GB of RAM while answering.
- `nomic-embed-text`: about 0.3 GB.
- Flask and ChromaDB: about 0.5 to 1 GB.
- The operating system: about 1 to 2 GB.

CPU use:
- Idle: close to 0%.
- While answering a question on a CPU-only server: all cores run near 100% for the whole answer (10 to 60 seconds). Several people asking at once will queue and slow each other down.
- Indexing a document: short bursts of high CPU while embeddings are created, usually a few seconds per document.
- On a GPU server, the CPU stays low and the GPU does the work.

Disk: the models take about 2.5 GB (3b) or 5 GB (7b). Uploaded documents and the vector database are small (a few MB for hundreds of pages). Leave extra room for logs and backups.

If answers are too slow for visitors, add a GPU, or use a smaller model such as `qwen2.5:1.5b` (Apache 2.0, less accurate).

### Deployment steps (Ubuntu 22.04 or 24.04)

1. Install the software. On Ubuntu 22.04 you may first need the "deadsnakes" package source for Python 3.12.
```
sudo apt update
sudo apt install -y python3.12 python3.12-venv git nginx
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```
2. Copy the project to the server (with Git or by uploading the folder) and install it:
```
git clone https://github.com/YOUR-NAME/company_document_ai.git
cd company_document_ai
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt waitress
cp .env.example .env
nano .env
```
In `.env`, set `LLM_MODEL=qwen2.5:7b`, set a long random `API_KEY`, and set `LLM_TIMEOUT_SECONDS=200` if the server has no GPU.

3. Test it by hand:
```
waitress-serve --host=127.0.0.1 --port=5000 --threads=4 --call app:create_app
```
Open a second terminal and run `curl http://127.0.0.1:5000/health`. Stop it with Ctrl+C.

Use only one server process (as above). The app keeps its document locks in memory, so do not run several worker processes against the same `storage` folder.

4. Run it as a service so it starts automatically. Create `/etc/systemd/system/document-ai.service`:
```
[Unit]
Description=Company Document AI
After=network.target ollama.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/company_document_ai
ExecStart=/home/ubuntu/company_document_ai/venv/bin/waitress-serve --host=127.0.0.1 --port=5000 --threads=4 --call app:create_app
Restart=always

[Install]
WantedBy=multi-user.target
```
Change `User` and the paths to match your server, then run:
```
sudo systemctl daemon-reload
sudo systemctl enable --now document-ai
sudo systemctl status document-ai
```
5. Put Nginx in front of it for HTTPS. Create `/etc/nginx/sites-available/document-ai`:
```
server {
    server_name chat.yourdomain.com;
    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_read_timeout 200s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
Then enable it and add a free HTTPS certificate:
```
sudo ln -s /etc/nginx/sites-available/document-ai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d chat.yourdomain.com
```
6. Open only the needed ports:
```
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```
Do not open port 11434 (Ollama) or 5000 (Flask) to the internet. They must stay on the server itself.

7. Upload your documents. In Postman, set `base_url` to `https://chat.yourdomain.com` and `api_key` to the key from `.env`, then upload and process each file as before.

### Security checklist for a server
- `API_KEY` is set, and Postman and your website backend send it in the `X-API-Key` header.
- Do not put the API key inside website JavaScript, because anyone can read it. Let your website's own backend call this API, or add rate limiting in Nginx (`limit_req`). If a browser must call the API directly, CORS support has to be added to the app first.
- HTTPS is on, and ports 5000 and 11434 are closed to the internet.
- Documents contain no confidential or personal data.
- Postman collections that contain the real API key are not shared or committed to Git.

### Backups and monitoring
- Back up the `storage` folder regularly (copy it while the app is stopped, or use server snapshots). If it is lost, upload the original documents again and process them.
- Check `https://chat.yourdomain.com/health` regularly. It should show `"status": "healthy"`.
- Read `logs/app.log` when something goes wrong.

## Project structure

```
company_document_ai/
├── app.py                  Starts the Flask app, error handling, logging
├── config.py               Reads the .env settings
├── requirements.txt
├── .env.example
├── routes/
│   ├── document_routes.py  Upload, process, status, list, reindex, delete
│   ├── chat_routes.py      Chat endpoint and greeting replies
│   ├── health_routes.py    Health check
│   └── auth.py             Optional API key check
├── services/
│   ├── document_service.py     Saves files and runs the indexing steps
│   ├── extraction_service.py   Reads PDF/DOCX/TXT/MD and cuts text into pieces
│   ├── embedding_service.py    Creates embeddings through Ollama
│   ├── vector_store_service.py ChromaDB storage
│   ├── retrieval_service.py    Finds the best pieces for a question
│   ├── llm_service.py          Writes the answer through Ollama
│   └── errors.py
├── documents_example/      Sample documents (demo data) to upload in Postman
│   ├── README_READ_FIRST.txt
│   ├── upload_these/       The 8 example documents
│   └── do_not_upload/      test_questions.md (test questions, not to be uploaded)
├── storage/                Saved documents, details and the database (created automatically)
├── logs/                   app.log
├── tests/
└── postman/                The Postman collection to import
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `pip install` fails with a numpy or compiler error | You are using a Python version that is too new. Install Python 3.12 and recreate the venv (Step 1 and Step 5) |
| `py -3.12` says no suitable runtime | Close and reopen the terminal. If it still fails, reinstall Python 3.12 |
| `ollama` is not recognized | Close and reopen the terminal or VS Code. If it still fails, restart the PC |
| `No module named 'flask'` | The venv is not active. Run `venv\Scripts\activate` and check that the prompt starts with `(venv)` |
| `/health` shows `degraded` | Read the `checks` part. `ollama: unavailable` means start the Ollama app. `missing: model` means run `ollama pull` for that model |
| Postman shows 503 "Model ... is not installed" | The model in `.env` is not installed. Run `ollama list` and set `LLM_MODEL` to a model in that list |
| Postman shows `EISDIR: illegal operation on a directory` | Extract the zip first, remove the file from the `file` row, and select it again |
| Upload returns 409 duplicate | This exact file was already uploaded. Use its existing ID, or delete it first |
| Process returns 409 "already indexed" | Use request 6 (Reindex) to update an indexed document |
| Answers say "not found" for things you wrote | Check request 4 that the document is `indexed` (not `uploaded`), and that no old file contradicts it |
| Answers are slow | The AI runs on your own processor. The first question after a break is the slowest because the models load. Close heavy programs, and keep `TOP_K` at 4 or lower |
| `ollama pull` is very slow or fails with "redirect target not allowed" | Change your DNS to 8.8.8.8 and 8.8.4.4 in Windows network settings, or try another network |
| A new document causes wrong answers | Look for old documents saying something different about the same topic, then update or delete them |

Logs are saved in `logs/app.log`.