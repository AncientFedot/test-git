# Backup & Restore

## Backup

```bash
python main.py backup
```

Result includes:
- `*.tar.gz` archive
- `*.manifest.json` with DB checksum and expected structure

## Restore

```bash
python main.py restore /path/to/backup.tar.gz
```

Restore safety model:
1. Extract to staging temp directory.
2. Validate manifest + DB checksum.
3. Snapshot current DB/uploads.
4. Replace active data.
5. Roll back to previous snapshot if any error happens.
