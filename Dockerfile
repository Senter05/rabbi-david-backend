FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8100
ENV RENDER=true
EXPOSE 8100
CMD ["python", "server.py", "--enable-voice"]
