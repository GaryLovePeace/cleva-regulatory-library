# 从 v0.4 升级到 v0.5

v0.5重点解决“最新法规更新排序靠后、历史法规过多、主管机构说明不突出”的问题。

## 新增功能

- 搜索目标：
  - 最新法规动态 / 官方更新
  - 现行法规原文 / 当前要求
  - 全部相关资料
- 发布时间范围：最近30天、90天、1年、3年或全部；
- Brave freshness参数；
- 近期结果加权；
- 主管监管机构和实施指南优先；
- UK化学品主题下优先HSE；
- `GB CLP`自动扩展为HSE更新、修订法规及正式法定文书查询；
- 搜索结果按“官方更新 / 正式法规原文 / 其他官方资料 / 专业解读”分组；
- 展示实际检索计划，便于核查关键词是否使用AND组合；
- `Governor + PFAS`等查询会要求结果同时匹配Governor和法规主题词，不会单独运行Governor。

## 安全覆盖方式

假设新版解压在：

```text
~/Downloads/cleva_v05
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
  ~/Downloads/cleva_v05/ \
  ~/Downloads/cleva-regulatory-library-github/
```

检查并测试：

```bash
cd ~/Downloads/cleva-regulatory-library-github
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m py_compile app.py search.py source_registry.py us_state_sources.py
python -m unittest discover -s tests -v
```

上传GitHub：

```bash
git add -A
git commit -m "Upgrade regulatory library to v0.5 with freshness ranking"
git push origin main
```

## 推荐验收测试

### GB CLP近期更新

```text
搜索词：GB CLP
地区：UK
主题：Chemicals / REACH / RoHS / PFAS
搜索目标：最新法规动态 / 官方更新
发布时间范围：最近一年
检索模式：仅官方来源
```

理想结果应优先显示HSE更新说明和近期修订法规，而不是大量2009、2015年的旧法规。

### Governor组合查询

```text
搜索词：California Governor PFAS
地区：US States
搜索目标：最新法规动态 / 官方更新
发布时间范围：最近一年
```

展开“查看本次实际检索计划”，每条查询都应同时包含Governor和PFAS；Governor不会单独运行。
