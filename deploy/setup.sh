#!/bin/bash
# StockPicky 서버 초기 설정 스크립트
# 사용법: bash setup.sh
set -e

REPO_DIR="/home/ubuntu/stockpicky"
SERVICE_NAME="stockpicky"

echo "=== 1. 시스템 패키지 업데이트 ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git

echo "=== 2. Python 버전 확인 ==="
python3 --version

echo "=== 3. 가상환경 생성 ==="
cd "$REPO_DIR"
python3 -m venv .venv

echo "=== 4. 의존성 설치 ==="
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "=== 5. systemd 서비스 등록 ==="
sudo cp deploy/stockpicky.service /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

echo ""
echo "=== 설정 완료! ==="
echo ""
echo "다음 단계:"
echo "  1. .env 파일을 생성하고 환경변수를 입력하세요:"
echo "     cp .env.example .env && nano .env"
echo ""
echo "  2. 봇 시작:"
echo "     sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "  3. 로그 확인:"
echo "     sudo journalctl -u ${SERVICE_NAME} -f"
