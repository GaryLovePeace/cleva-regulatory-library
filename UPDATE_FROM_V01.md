# 从v0.1升级到v0.2（Mac）

升级前先停止Streamlit：

```bash
Control + C
```

备份数据库和环境变量：

```bash
cd ~/Downloads/cleva_regulatory_library_mvp/cleva_regulatory_library_mvp
cp .env .env.backup
cp data/regulatory_library.sqlite3 data/regulatory_library.backup.sqlite3 2>/dev/null || true
```

将v0.2压缩包放到Downloads后解压到临时目录：

```bash
cd ~/Downloads
unzip -o cleva_regulatory_library_mvp_v0_2.zip -d cleva_v0_2
```

复制新程序文件，但保留原来的 `.env` 和 `data`：

```bash
rsync -av --exclude='.env' --exclude='data/' \
  ~/Downloads/cleva_v0_2/cleva_regulatory_library_mvp/ \
  ~/Downloads/cleva_regulatory_library_mvp/cleva_regulatory_library_mvp/
```

重新安装依赖并启动：

```bash
cd ~/Downloads/cleva_regulatory_library_mvp/cleva_regulatory_library_mvp
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

应用启动时会自动升级旧数据库表，不需要删除原有法规记录。
