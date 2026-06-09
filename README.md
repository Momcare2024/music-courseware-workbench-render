# 音乐课件工作台

私有音乐课件生成网页。第一版先解决最关键的工作流：

```text
输入课程信息 / 上传参考资料
  -> 生成教案草稿
  -> 人工审核教案
  -> 生成 PPT 逐页设计稿
  -> 人工审核设计稿
  -> 导出教案、设计稿、素材清单
```

这不是通用 PPT 生成器。它面向音乐课堂，强调教案、音频、视频、曲谱、歌词、节奏、律动和课堂互动之间的关系。

## 当前能力

- 网页创建音乐课件任务
- 粘贴教案与 PPT 页面设计稿
- 自动按 P1/P2 或“第1页”拆分页面
- 使用火山方舟/即梦图片 API 逐页生成画面
- 一键生成剩余页面
- 人工编辑并保存每页提示词
- 导出：
  - 图片版 PPTX
  - WPS AIPPT 可上传 PDF
  - 页面图片 ZIP
  - 页面设计稿与分页 JSON

## 暂不做

- 暂不保证生成可编辑 PPT 图层
- 暂不嵌入音频/视频
- 暂不做完整用户系统，只提供简单访问码
- 暂不做多人并发队列

这些留到第二阶段。第一阶段先把“页面设计稿 -> 逐页画面 -> WPS 上传包”跑顺。

## 安装

```bash
cd /Users/linda/Documents/ppt-master-web
/Users/linda/.local/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```env
ARK_API_KEY=你的火山方舟 API Key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_IMAGE_MODEL=doubao-seedream-4-0-250828

# 可选：文本模型
VECTORENGINE_API_KEY=你的 VectorEngine Key
VECTORENGINE_BASE_URL=https://api.vectorengine.ai/v1
TEXT_MODEL=你想测试的文本模型

# 可选：给分享版加访问码
ACCESS_CODE=
```

如果不填 `ARK_API_KEY`，网页仍能运行，但无法生成即梦图片。

## 启动

```bash
cd /Users/linda/Documents/ppt-master-web
source .venv/bin/activate
./scripts/run_dev.sh
```

打开：

```text
http://127.0.0.1:8765
```

## 部署到 Render

本项目已经包含 `render.yaml`，可以作为 Render Web Service 部署。

推荐流程：

1. 创建一个私有 GitHub 仓库，把本项目推上去。
2. 在 Render 新建 Blueprint 或 Web Service，连接该仓库。
3. Build Command:

```bash
pip install -r requirements.txt
```

4. Start Command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. 在 Render 环境变量中填写：

```env
ARK_API_KEY=你的火山方舟 API Key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_IMAGE_MODEL=doubao-seedream-4-0-250828
ACCESS_CODE=你想分享给朋友的访问码
ALLOW_WEB_CONFIG=false
WORKBENCH_DATA_DIR=/opt/render/project/src/data
```

如果需要文本模型，再额外填写：

```env
VECTORENGINE_API_KEY=你的文本模型 API Key
VECTORENGINE_BASE_URL=https://api.vectorengine.ai/v1
TEXT_MODEL=你的文本模型
```

注意：免费/普通云端文件系统可能会在重启或重新部署后丢失生成文件。小范围测试没问题；如果要长期保存项目，需要后续接对象存储或数据库。

## 推荐使用方式

1. 输入课题，例如“绿色的祖国”。
2. 粘贴已写好的教案和 PPT 页面设计稿。
3. 点击“创建并拆分页”。
4. 逐页检查提示词，先生成 2-3 页测试效果。
5. 满意后点击“一键生成剩余全部页面”。
6. 点击“导出WPS上传PDF/图片包”。
7. 将 PDF 或解压后的 JPG 图片上传到 WPS AIPPT 做后续图文分层。

## 下一阶段

建议下一阶段按这个顺序扩展：

1. 增加模型 A/B 测试。
2. 增加素材状态标注：已有 / 需生成 / 需老师提供。
3. 接入 PPT Master，生成基础 PPTX。
4. 增加音频、视频、曲谱页面模板。
5. 增加音乐课件专用模板库。
