FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/tmp \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    SAL_USE_VCLPLUGIN=svp \
    LIBREOFFICE_PATH=/usr/bin/libreoffice \
    PNG_RENDER_TIMEOUT_SECONDS=18

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-calc \
        libreoffice-core \
        fonts-noto-core \
        fonts-khmeros-core \
        fontconfig \
        ca-certificates \
    && fc-cache -f -v \
    && fc-match -f '%{family}|%{file}\n' "Khmer OS System" \
        | grep -i "Khmer OS" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/exports \
    && chmod -R 775 /app/exports

CMD ["python", "-m", "app.bot.run_bot"]
