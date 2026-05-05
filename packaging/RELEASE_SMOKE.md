# 发布前自检（Windows 安装包）

在干净或接近干净的 Windows 10/11 x64 环境执行（实体机或虚拟机均可）。构建步骤见仓库根目录 `scripts/build_windows.ps1` 与 `packaging/`。

## 构建产物

- [ ] `dist/RealTimeTranslation/` 存在且内含 `RealTimeTranslation.exe`。
- [ ] （若已装 Inno Setup 6）`dist/RealTimeTranslation-Setup.exe` 已生成。

## 绿色包（dist/RealTimeTranslation）

- [ ] 双击 `RealTimeTranslation.exe` 能启动主窗口，无立即崩溃。
- [ ] 打开 **设置**，能保存并关闭（API Key 可用测试用 Key 或占位）。
- [ ] 托盘图标出现；关闭窗口后行为符合设计（如最小化到托盘）。
- [ ] **开始** / **暂停** 按钮状态与逻辑正常（可先不连真实 API，仅看 UI）。

## 安装包（RealTimeTranslation-Setup.exe）

- [ ] 双击安装向导能走完；默认安装路径下文件完整。
- [ ] 开始菜单出现 **Real Time Translation** 快捷方式；可选桌面图标任务正常。
- [ ] 安装结束勾选 **运行** 时能启动应用。
- [ ] **应用与功能** 中能卸载，卸载后快捷方式移除。

## 联网与 API（可选但建议）

- [ ] 填入有效转写/翻译配置后，播放系统音频，能完成至少一轮「有原文、有译文」的流程（或出现可预期的业务错误而非崩溃）。

## 记录

- 测试日期：________  
- Windows 版本：________  
- 构建 commit / 版本号：________  
