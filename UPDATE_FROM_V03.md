# 从 v0.3 升级到 v0.4

v0.4新增美国50州＋Washington, D.C.的通用检索框架。建议用完整项目覆盖代码，但保留 `.env`、`.git`、`.venv` 和 `data`。

## 安全覆盖方式

假设新版解压在：

```text
~/Downloads/cleva_v04
```

现有GitHub项目目录为：

```text
~/Downloads/cleva-regulatory-library-github
```

执行：

```bash
rsync -av --delete \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='.venv/' \
  --exclude='data/*.sqlite3' \
  --exclude='data/*.db' \
  ~/Downloads/cleva_v04/ \
  ~/Downloads/cleva-regulatory-library-github/
```

进入项目并检查：

```bash
cd ~/Downloads/cleva-regulatory-library-github
python -m py_compile app.py search.py source_registry.py us_state_sources.py
python -m unittest discover -s tests -v
```

上传GitHub：

```bash
git add -A
git commit -m "Upgrade regulatory library to v0.4 with all US states"
git push origin main
```

Streamlit Cloud通常会自动重新部署。API Key继续保存在Streamlit Secrets中，不需要重新填写。

## 推荐测试

```text
California SB 343
Minnesota HF 3911
Maine LD 1541
Nebraska LB 123
New York A 1234
Massachusetts H. 321
Texas HB 3
District of Columbia B25-0123
```

测试时选择 `US States`。也可以先在“美国州/特区”中选择一个州，再只输入法案编号。
