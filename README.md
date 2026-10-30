# HerMotion

女性日常状态与轻运动陪伴Web应用。参赛方向：2026北京开源创新赛赛道一。

## 当前交付

包含React/TypeScript源码、Vite本地对话代理、可选云端函数、Yoga及舌面服务、模型/WASM/本地示范视频、依赖锁文件和实测前端构建。目录共45项（21瑜伽、12普拉提、12产后恢复）；目录数不代表全部已专项识别。前端明确接入6个Yoga分类目标。

浏览器关键点、本机分类、可选DeepSeek推荐分工；没有密钥时使用本地推荐路径。本项目不提供医学诊断、治疗或训练处方。

## 安装与缓存位置

先准备Node.js、pnpm及Python3.10/3.11，再进入本目录。所有新依赖、模型与缓存均应存放本目录；不要全局安装。本包不携带node_modules或虚拟环境。

Windows PowerShell首次安装示例：

```powershell
$env:PIP_CACHE_DIR = Join-Path (Get-Location) '.runtime/pip-cache'
$env:XDG_CACHE_HOME = Join-Path (Get-Location) '.runtime/cache'
$env:PNPM_HOME = Join-Path (Get-Location) '.runtime/pnpm-home'
python -m venv .venv-runtime
.\.venv-runtime\Scripts\python.exe -m pip install --cache-dir .runtime/pip-cache -r requirements-runtime.txt
pnpm install --frozen-lockfile --store-dir .runtime/pnpm-store --node-linker=hoisted
```

若python命令不可用，请使用已安装Python的实际路径；若pnpm不可用，先按本机环境准备包管理器，不要误把README当成已安装依赖的证明。无GPU可用CPU运行，torch安装较大。Python依赖仍是范围约束，干净电脑需要另行验证兼容性。

## Windows启动

完成安装后双击Windows双击启动.bat，或在PowerShell执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_final_demo_windows.ps1
```

此启动脚本只运行已安装依赖，不会自动安装。页面 http://127.0.0.1:3001，Yoga服务8765，舌面服务8766。关闭前端终端时清理本脚本启动的模型服务。端口被占用时先关闭之前的实例，勿盲目杀其他进程。

## 手动启动与构建

在三个终端依次运行（模型服务需要先激活本地虚拟环境）：

```text
.venv-runtime/Scripts/python.exe yoga_model/runtime/server.py --checkpoint models/yoga/best.pt --config yoga_model/config/runtime_gate.json --port 8765
.venv-runtime/Scripts/python.exe -m uvicorn tongue_model.service:app --host 127.0.0.1 --port 8766
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3001 --strictPort
```

源码检查和构建：

```text
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
```

macOS/Linux的本地Python路径改为.venv-runtime/bin/python，安装缓存同样指定本目录。此整理副本未新增宣称跨平台全量验收的自动脚本。

## 已验证与限制

2026-10-28本机完成源码构建、椅上计时/暂停/继续/PNG记录、无面部拒绝、本地模型HTTP推理与无密钥响应检查；22项模型资源SHA256一致。复用了本机已有torch2.14.0+cpu、torchvision0.29.0+cpu，并非干净电脑验证。

首页仍显示39项的旧文案，真实目录45项。舌面服务缺少充分的非舌面图片拒绝能力；不能因返回标签便称分析有效。真实人体/舌面准确率、真实摄像头完整链路及云端成功调用尚未验证。首页背景视频和字体依赖外部网络。

## 目录

- src：前端；functions/api/chat.ts：可选托管函数。
- yoga_model/runtime：本地Yoga分类服务；tongue_model：舌面服务与训练相关代码。
- models：专项权重和原报告；public：MediaPipe/WASM与本地示范视频。
- dist：2026-10-28本机实测源码生成的前端构建，仅静态预览不包含Vite对话代理。
- MODEL_SHA256SUMS.txt：22项模型与运行资源校验。

## 开源与贡献

项目自有代码许可证和模型/数据/素材授权须由实际权利人确认。本整理过程不新增未经授权的开源声明；未完成确认前不能据此称开源治理已合规。见开源归属核对.md。

问题反馈：仓库发布后使用Issue，附环境、复现步骤、预期/实际行为及脱敏日志。贡献前讨论范围，PR注明改动与验证结果；维护人员和响应安排由团队填写。不得提交密钥、个人身体图像或无授权资源。
