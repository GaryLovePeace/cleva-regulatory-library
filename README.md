# Cleva Global Regulatory Library MVP v0.3

这一版将知识库拆成两类记录：

1. **正式法规库**：政府、监管机构或官方法规数据库原文；
2. **法规情报库**：Intertek、TBT资讯网、REACH24H、CAA等专业机构的解读、预警、注册通知和行业动态。

第三方页面不会被系统直接当成正式法规。人工审核时，只有补充并核验官方法规链接后，才能作为正式法规入库。

## v0.3重点改进

- 识别 `California SB343`、`EU 2025/40` 等法规编号；
- 州级法案自动排除美国联邦来源；
- 对法规编号使用精确短语搜索和州级优先来源；
- 对搜索结果进行本地相关度评分，隐藏不含目标编号的网页；
- A/B级官方来源优先，展示排序理由；
- 自动拆分过长域名查询，避免Brave 422错误；
- 新增California Governor和Intertek全球法规源。

## v0.2已有功能

- 信息源中心：统一维护官方来源和专业信息源；
- 已加入以下专业来源：
  - Intertek China Regulatory & Standards
  - 技术性贸易措施资讯网（新闻速递、预警信息、TBT/SPS）
  - REACH24H
  - In Compliance Magazine
  - Deutsche Recycling
  - GWP Packaging
  - Product Compliance Institute
  - Circular Action Alliance
  - 《电器》杂志
- 三种检索模式：
  - **快速检索**：搜索已维护的官方和专业信息源；
  - **仅官方来源**：用于最终法律核验；
  - **深度检索**：多关键词查询，并增加一次全网搜索；
- 可指定一个或多个信息源进行搜索；
- 待审核资料可分流进入“正式法规库”或“法规情报库”；
- 第三方来源如需进入正式法规库，必须填写官方法规链接；
- 法规库和情报库分别导出Excel；
- 自动兼容并升级v0.1已经创建的SQLite数据库。

## 1. 安装

```bash
cd cleva_regulatory_library_mvp
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

## 4. 推荐使用方法

### 日常快速查找

选择：

- 检索模式：`快速检索`
- 国家/地区：例如 `EU`
- 法规主题：例如 `Packaging / PPWR / EPR`

系统会搜索与该市场和主题相关的已维护信息源，减少无关结果和Brave用量。

### 最终人工核验

选择：

- 检索模式：`仅官方来源`

只搜索政府、监管机构和官方法规数据库。

### 全面专题调查

选择：

- 检索模式：`深度检索`

系统会生成多组关键词，并增加一次不限制域名的全网搜索。该模式会使用更多搜索API请求。

## 5. 审核规则

- 官方来源可以直接人工核验并进入正式法规库；
- 专业机构、PRO、媒体或行业文章默认进入法规情报库；
- 第三方页面要进入正式法规库，必须填写其对应的政府或官方法规数据库链接；
- AI摘要、法规编号、日期和法律状态均需人工核验；
- 正式法规和情报资料应保留原始链接、审核人及最后核验日期。

## 6. 数据库兼容

系统启动时会自动为旧版数据库增加新字段和 `intelligence_records` 表，无需删除原来的：

```text
data/regulatory_library.sqlite3
```

建议升级前仍复制一份数据库作为备份。

## 7. GitHub 与 Streamlit Cloud 部署

部署版已经包含：

- `.gitignore`：排除 `.env`、API Key、虚拟环境和本地 SQLite；
- `.streamlit/secrets.toml.example`：Streamlit Cloud 密钥模板；
- 可选 `APP_PASSWORD` 访问保护；
- 云端 SQLite 非持久化风险提示；
- 详细步骤见 `DEPLOY_TO_STREAMLIT.md`。

在线演示可以继续使用 SQLite；正式内部知识库应切换到持久数据库。
