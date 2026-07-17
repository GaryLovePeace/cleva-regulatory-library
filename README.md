# Cleva Global Regulatory Library MVP v0.4

Cleva全球法规知识库用于搜索欧盟、英国、美国和加拿大的官方法规及专业法规情报，并通过人工审核将资料分流到：

1. **正式法规库**：政府、监管机构或官方法规数据库原文；
2. **法规情报库**：Intertek、TBT资讯网、REACH24H、CAA等专业机构的解读、预警、注册通知和行业动态。

第三方页面不会被系统直接当成正式法规。人工审核时，只有补充并核验官方法规链接后，才能作为正式法规入库。

## v0.4重点改进：美国50州＋Washington, D.C.

- 覆盖美国50州及Washington, D.C.；
- 每个州/特区至少维护：
  - 官方立法网站；
  - 官方环境、废弃物、包装、电池或化学品主管部门；
- 新增“美国州/特区”筛选器；
- 搜索词写明州名时可自动识别，无需手工选择；
- 只输入法案编号时，可先选择一个州，例如选择Texas后输入 `HB 3`；
- 支持常见州级编号：
  - `SB / AB / HB`
  - `HF / SF`
  - `A / S / H`
  - `LD / LB`
  - `HJR / SJR / HCR / SCR / HR / SR`
  - Washington, D.C.的 `B25-0123` 等格式；
- 州级法案自动排除Federal Register、eCFR和Regulations.gov等联邦来源；
- 精确法案检索仅搜索目标州的官方来源及精选专业来源；
- 搜索结果必须包含准确编号，低相关结果会被隐藏；
- 信息源中心增加“州/地区”字段；
- 增加51个州/特区的来源覆盖清单及自动化测试。

## v0.3已有改进

- 识别 `California SB343`、`EU 2025/40` 等法规编号；
- 对搜索结果进行本地相关度评分；
- A/B级官方来源优先并展示排序理由；
- 自动拆分过长查询，避免Brave 422错误。

## 主要功能

- 快速检索：搜索已维护的官方和专业信息源；
- 仅官方来源：用于最终法律核验；
- 深度检索：多关键词查询，并增加一次全网搜索；
- AI生成中文摘要、法规类型和相关性字段；
- 人工审核并分流到正式法规库或法规情报库；
- Excel和Word导出；
- 信息源中心；
- GitHub与Streamlit Cloud部署支持。

## 1. 安装

```bash
cd cleva_regulatory_library
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## 2. 配置

编辑 `.env`：

```env
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=你的BraveKey

LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的DeepSeekKey
DEEPSEEK_MODEL=deepseek-chat
```

## 3. 启动

```bash
python -m streamlit run app.py
```

## 4. 美国州级法规使用示例

### 已知州名和法案号

```text
搜索词：Minnesota HF 3911 packaging
地区：US States
主题：Packaging / PPWR / EPR
模式：仅官方来源
```

系统会自动仅搜索Minnesota Revisor、Minnesota House/Senate和州主管部门。

### 只知道法案号

```text
美国州/特区：Texas
搜索词：HB 3
```

系统会使用Texas作为州提示，将其识别为精确法案检索。

### 州级专题搜索

```text
搜索词：Maine PFAS products reporting
地区：US States
主题：Chemicals / REACH / RoHS / PFAS
```

系统会优先Maine Legislature和Maine DEP，同时在快速检索模式中保留精选专业解读来源。

## 5. 三种检索模式

- **快速检索**：官方来源＋精选专业来源，适合日常查找；
- **仅官方来源**：只搜索政府、监管机构及官方法规数据库，适合最终核验；
- **深度检索**：生成多组关键词并进行全网补充，适合专题排查和补漏。

## 6. 审核规则

- 官方来源可以直接人工核验并进入正式法规库；
- 专业机构、PRO、媒体或行业文章默认进入法规情报库；
- 第三方页面要进入正式法规库，必须填写对应官方法规链接；
- AI摘要、法规编号、日期和法律状态均需人工核验；
- 正式法规和情报资料应保留原始链接、审核人及最后核验日期。

## 7. 数据和部署

系统默认使用：

```text
data/regulatory_library.sqlite3
```

本地使用可继续使用SQLite。Streamlit Community Cloud上的本地SQLite可能在重新部署后丢失，正式公司版应迁移至PostgreSQL等持久数据库。

部署步骤见 `DEPLOY_TO_STREAMLIT.md`，从v0.3升级见 `UPDATE_FROM_V03.md`。
