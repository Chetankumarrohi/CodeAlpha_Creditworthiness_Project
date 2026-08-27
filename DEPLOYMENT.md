# 🚀 Deployment Guide — Nova Credit AI

Production deployment instructions for the **Nova Credit AI** project.

---

## 1. Local Quickstart

### Streamlit Dashboard
```bash
./run.sh
# or
streamlit run app/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Web Server & REST API
```bash
./run.sh server
# or
python backend/server.py 8085
```
Open [http://localhost:8085](http://localhost:8085) for the web client or test `/api/predict` & `/api/health`.

### Retrain Model
```bash
./run.sh train
```

---

## 2. Docker Deployment

### Run with Docker Compose (Both Dashboard & API Server)
```bash
docker-compose up --build
```
- Streamlit Dashboard: `http://localhost:8501`
- REST API Server: `http://localhost:8085`

### Build Single Docker Image
```bash
docker build -t nova-credit-ai .
docker run -p 8501:8501 nova-credit-ai
```

---

## 3. Deploy to Streamlit Community Cloud (1-Click Free Deploy)

1. Push your repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io).
3. Connect your GitHub repository.
4. Set **Main file path** to `app/app.py`.
5. Click **Deploy**!

---

## 4. Deploy to Render / Railway

1. Connect your repository to Render or Railway.
2. Select **Docker** environment (or Python 3.11 web service).
3. Set Build Command: `pip install -r requirements.txt && python src/train_model.py`
4. Set Start Command: `streamlit run app/app.py --server.port=$PORT --server.address=0.0.0.0`
5. Click Deploy!
