#!/bin/bash
# 一键安装环境

set -e
echo "=== 内容创作系统 环境安装 ==="

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装Python依赖
pip install -r requirements.txt

# 安装Playwright浏览器（爬虫需要）
playwright install chromium

# 安装yt-dlp（媒体下载需要）
pip install yt-dlp

# 创建配置文件
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "已创建 .env，请编辑配置后启动"
fi

# 创建数据目录
mkdir -p data/{raw/media,processed,reports,scripts_output} logs

echo ""
echo "=== 安装完成 ==="
echo "下一步:"
echo "  1. 编辑 .env 文件，填入API Key等配置"
echo "  2. 运行 bash scripts/start.sh 启动系统"
echo "  3. 浏览器打开 http://localhost:8000"
