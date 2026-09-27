@echo off
chcp 65001 >nul
echo ============================================
echo   方块君 v4.0 - 自建混合AI引擎 启动脚本
echo ============================================
echo.

REM 检查Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装Python 3.9+
    pause
    exit /b 1
)

echo [1/2] 检查依赖...
pip install -r requirements.txt -q

echo.
echo [2/2] 启动方块君...
echo ============================================
echo   A: MC规则引擎 (Minecraft专家)
echo   B: ChatBrain (内置聊天模型)
echo   外部依赖: 无 (纯本地运行)
echo ============================================
echo.
python main.py
pause
