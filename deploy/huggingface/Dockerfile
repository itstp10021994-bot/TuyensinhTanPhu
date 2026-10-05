# Chạy app tuyển sinh trên Hugging Face Spaces (Docker).
# Code lấy thẳng từ GitHub; mỗi lần Space khởi động lại sẽ tự lấy bản mới nhất (start.sh).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face chạy container bằng user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /home/user

ENV REPO=https://github.com/itstp10021994-bot/TuyensinhTanPhu.git \
    BRANCH=claude/affectionate-hamilton-yqdr6u

# Cài sẵn thư viện lúc build để khởi động nhanh
RUN git clone --depth 1 -b "$BRANCH" "$REPO" app \
    && pip install --no-cache-dir --user -r app/requirements.txt

COPY --chown=user start.sh /home/user/start.sh
EXPOSE 7860
CMD ["bash", "/home/user/start.sh"]
