#!/bin/bash
# 启动内容创作系统

set -e

echo "=== 内容创作系统 启动 ==="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt -q

# 检查.env
if [ ! -f ".env" ]; then
    echo "创建.env配置文件（请修改后重启）..."
    cp .env.example .env
    echo "请编辑 .env 文件配置API Key等信息"
fi

# 创建数据目录
mkdir -p data/{raw/media,processed,reports,scripts_output} logs

# 启动服务
echo "启动服务 http://localhost:8000"
python3 main.py
