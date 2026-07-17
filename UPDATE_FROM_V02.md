# 从 v0.2 升级到 v0.3

本次只需要替换 `app.py`、`search.py`、`source_registry.py`，不会修改 `.env` 或现有数据库。

```bash
cd ~/Downloads/cleva_v0_2/cleva_regulatory_library_mvp
cp app.py app.py.v02.backup
cp search.py search.py.v02.backup
cp source_registry.py source_registry.py.v02.backup
```

将v0.3压缩包解压后覆盖三个文件，随后运行：

```bash
python -m py_compile app.py search.py source_registry.py
git add app.py search.py source_registry.py README.md UPDATE_FROM_V02.md
git commit -m "Improve exact regulation search and relevance ranking"
git push
```

Streamlit Cloud通常会自动重新部署。测试：

- 搜索词：`California SB343`
- 地区：即使选择 `US Federal + US States`，系统也应提示实际检索范围自动调整为 `US States`；
- 结果应优先出现California Legislature、CalRecycle、California Governor或Intertek；
- 不含 `SB 343` 的Federal Register结果应被隐藏。
