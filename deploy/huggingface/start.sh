#!/bin/bash
# Khởi động app: lấy code mới nhất từ GitHub, ghi Secrets, chạy Streamlit ở cổng 7860.
cd "$HOME/app" || exit 1

if git fetch --depth 1 origin "$BRANCH" && git reset --hard FETCH_HEAD; then
    echo "Đã lấy code mới nhất: $(git log -1 --format='%h %s')"
    pip install --no-cache-dir --user -q -r requirements.txt || echo "Cảnh báo: cài thư viện lỗi"
else
    echo "Không tải được code mới từ GitHub, chạy bản đã có."
fi

# Secret STREAMLIT_SECRETS (trong Settings của Space) = nguyên nội dung Secrets bên Streamlit
mkdir -p .streamlit
if [ -n "$STREAMLIT_SECRETS" ]; then
    printf '%s\n' "$STREAMLIT_SECRETS" > .streamlit/secrets.toml
    echo "Đã ghi secrets.toml"
else
    echo "Cảnh báo: chưa có secret STREAMLIT_SECRETS"
fi

exec streamlit run app.py \
    --server.port 7860 --server.address 0.0.0.0 --server.headless true \
    --server.enableXsrfProtection false --server.enableCORS false \
    --browser.gatherUsageStats false
