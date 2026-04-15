# Upgrade Guide

1. Backup current data:
   - `python main.py backup --role administrator`
2. Deploy new release into a new release folder.
3. Keep `BONIFACIY_DATA_DIR` unchanged.
4. Run readiness checks:
   - `./scripts/prod_readiness_check.sh`
5. Start new release API and worker services.
6. Run smoke checks (`/health`, `/auth/login`, `/projects`, mail queue + worker).

If rollout fails:
- stop new release services;
- restore with previous release binary while keeping same data directory;
- if secret leak is suspected: rotate keys + `python main.py revoke-sessions`.
