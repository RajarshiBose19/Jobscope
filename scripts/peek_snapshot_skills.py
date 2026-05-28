import json
from pathlib import Path

snap = Path("projects/jobscope/state/current_job.json")
d = json.loads(snap.read_text(encoding="utf-8"))
skills = (d.get("analysis") or {}).get("skills") or []
print(f"snapshot has {len(skills)} skills:")
for s in skills:
    print(f"  kind={s.get('kind'):12} match={s.get('match'):8} as_written={s.get('as_written')}")
