"""Export aggregate acceptance results without prompts, paths or private UI data."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('tags', nargs='+')
args = parser.parse_args()
out = ROOT/'reports';out.mkdir(exist_ok=True)
summary = {'runs': {}, 'total_attempts': 0, 'total_functional_passes': 0,
           'note': 'Includes exploratory failures and regression repetitions. Functional checks do not independently score English prose. Latencies include verification; some cases include waiting for a serialized drag diagnostic. No universal desktop capability is claimed.'}
rows = []
prompts=set()
correction_file=ROOT/'output/acceptance/oracle-corrections.json'
corrections=json.loads(correction_file.read_text()) if correction_file.exists() else {}
for tag in args.tags:
    if not tag.replace('-', '').isalnum():raise SystemExit('Invalid tag')
    records = [json.loads(line) for line in (ROOT/'output/acceptance'/f'{tag}.jsonl').read_text().splitlines()]
    for record in records:
        correction=corrections.get(tag+':'+record['id'])
        if correction:record['pass']=correction['pass']
    categories = defaultdict(list)
    for r in records:
        prompts.add(r['prompt'])
        categories[r['category']].append(r)
        rows.append({'run': tag, 'case': r['id'], 'category': r['category'],
                     'functional_pass': r['pass'], 'wall_seconds': r['seconds']})
    summary['runs'][tag] = {'attempts': len(records), 'functional_passes': sum(r['pass'] for r in records),
        'categories': {name: {'attempts':len(group), 'functional_passes':sum(r['pass'] for r in group),
                             'median_wall_seconds':round(statistics.median(r['seconds'] for r in group),3)}
                       for name,group in categories.items()},
        'failures':[r['id'] for r in records if not r['pass']]}
    summary['total_attempts'] += len(records)
    summary['total_functional_passes'] += sum(r['pass'] for r in records)
summary['distinct_request_texts']=len(prompts)
(out/'acceptance-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
(out/'oracle-corrections.json').write_text(json.dumps(corrections,indent=2)+'\n')
with (out/'acceptance-cases.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=['run','case','category','functional_pass','wall_seconds'],lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
print(json.dumps({k:summary[k] for k in ('total_attempts','total_functional_passes')}))
