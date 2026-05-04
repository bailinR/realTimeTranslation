我刚才是在 PowerShell 里按下面步骤做的，路径就是你的项目目录。

```powershell
cd D:\project\jmcy\realTimeTranslation
```

创建虚拟环境：

```powershell
python -m venv .venv
```

用虚拟环境里的 Python 安装项目依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

检查环境是否正常：

```powershell
.\start.ps1 -CheckOnly
```

运行测试确认项目没问题：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

启动程序：

```powershell
.\start.ps1 -Background
```

如果你想前台启动，也可以用：

```powershell
.\start.ps1
```

或者直接用 Python 模块方式启动：

```powershell
.\.venv\Scripts\python.exe -m app.main
```

可选：如果要安装本地 Whisper / 本地 ASR 模式，再执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[local-asr]"
```

最短版就是这三步：

```powershell
cd D:\project\jmcy\realTimeTranslation
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\start.ps1
```