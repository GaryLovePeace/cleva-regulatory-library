# GitHub + Streamlit Community Cloud 部署

## 重要说明

- `.env` 和 `.streamlit/secrets.toml` 不得上传 GitHub。
- Community Cloud 中的 API Key 请放到应用的 **Advanced settings → Secrets**。
- 当前版本使用 SQLite。它适合在线演示，但云端应用重启或重新部署后，运行期间新增的数据可能丢失。正式公司版应迁移到 PostgreSQL / Supabase / Azure SQL 等持久数据库。
- 请配置 `APP_PASSWORD`，否则任何知道网址的人都可能消耗 Brave 与 DeepSeek API 额度。

## 1. 上传 GitHub

在 Mac 终端进入项目目录：

```bash
cd ~/Downloads/cleva_regulatory_library_mvp/cleva_regulatory_library_mvp
```

确认敏感文件不会进入 Git：

```bash
git check-ignore -v .env
```

如果尚未安装 GitHub CLI：

```bash
brew install gh
```

登录：

```bash
gh auth login
```

初始化并创建私有仓库：

```bash
git init
git branch -M main
git add .
git commit -m "Initial deployable Cleva Regulatory Library"
gh repo create cleva-regulatory-library --private --source=. --remote=origin --push
```

## 2. 部署 Streamlit Community Cloud

1. 登录 `share.streamlit.io`，连接 GitHub。
2. 点击 **Create app**。
3. Repository 选择 `cleva-regulatory-library`。
4. Branch 选择 `main`。
5. Main file path 填 `app.py`。
6. Python 建议选 3.11。
7. 打开 **Advanced settings**，将 `.streamlit/secrets.toml.example` 的内容复制进去，并替换真实 Key 与访问密码。
8. 点击 **Deploy**。

## 3. 后续更新

```bash
git add .
git commit -m "Update regulatory library"
git push
```

Streamlit Cloud 会从 GitHub 自动重新部署。
