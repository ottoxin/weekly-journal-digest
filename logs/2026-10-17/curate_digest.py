"""Candidate-backed editorial review of the October 17 Saturday edition."""
import json,re
from pathlib import Path
from collections import defaultdict
folder=Path(__file__).resolve().parent
candidate=json.loads((folder/'candidate_digest-2026-10-17.json').read_text())
sections=candidate['sections']
previous=(folder.parent/'2026-10-10/reviewed_digest-2026-10-10.structured.md').read_text()
previous_dois={x.lower() for x in re.findall(r'^  DOI: (.+)$',previous,re.M)}
dedicated={'Journal of Communication','Journal of Computer-Mediated Communication','Political Communication','Human Communication Research','Communication Research','Communication Methods and Measures','American Journal of Political Science','American Political Science Review','Political Analysis'}
# Broad-science additions and highlight explanations are reviewed against the final candidate.
review=json.loads((folder/'editorial_selection.json').read_text())
kept={k:[] for k in sections}; decisions=[]
for key,items in sections.items():
 for i,a in enumerate(items):
  doi=(a.get('doi') or '').lower()
  noise=any(x in a['title'].lower() for x in ['issue information','erratum','corrigendum','farewell'])
  reason='Outside strict COMAP scope: natural science, clinical or technical research without a clear social-science connection.'
  retain=False
  if doi in previous_dois: reason='Already delivered in October 10 edition.'
  elif noise: reason='Publication noise: issue information, correction or farewell editorial.'
  elif a['journal'] in dedicated: retain=True;reason='Substantive dedicated communication or political-science article.'
  elif doi in review['broad_keep']: retain=True;reason=review['broad_keep'][doi]
  if retain: kept[key].append(a)
  decisions.append(dict(section=key,index=i,doi=doi,title=a['title'],kept=retain,reason=reason))
counts={k:len(v) for k,v in sections.items()};curated={k:len(v) for k,v in kept.items()}
lines=['Subject: Weekly journal digest for 2026-10-12 to 2026-10-17','','## Summary','',review['summary'],'','You may have received two September 7 emails because the first was sent before that collection window closed; the second completed the same edition. Saturday delivery now aligns collection and sending, so each future email represents a distinct Monday–Saturday edition.','','## Collection Snapshot','',f"- Total collected candidates: {sum(counts.values())}",f"- New This Week candidates: {counts['new_this_week']}",f"- Previous Week Catch-Up candidates: {counts['previous_week_catch_up']}",f"- Late Additions candidates: {counts['late_additions']}",f"- Curated digest below: {curated['new_this_week']} new, {curated['previous_week_catch_up']} catch-up, {curated['late_additions']} late additions",'- These candidates passed automated source filters; counts precede manual relevance filtering. The full curated digest and attached PDF apply the stricter COMAP threshold.',review['coverage_note'],'','## Highlights','']
for doi,why in review['highlights'].items():
 a=next(a for a in kept['new_this_week'] if a.get('doi','').lower()==doi)
 lines += [f"- **{a['title']}**",f"  Journal: {a['journal']}",f"  Published: {a['published_date']}",f"  Why it matters: {why}",f"  Link: {a['link']}",'']
lines+=['## Full Curated Digest','']
for key,heading in [('new_this_week','New This Week'),('previous_week_catch_up','Previous Week Catch-Up'),('late_additions','Late Additions')]:
 if not kept[key]: continue
 lines+=['### '+heading,''];groups=defaultdict(list)
 for a in kept[key]: groups[a['journal']].append(a)
 for journal in sorted(groups):
  lines+=['#### '+journal,'']
  for a in groups[journal]:
   lines += [f"- **{a['title']}**",f"  Published: {a['published_date']}"]
   for field,label in [('authors','Authors'),('affiliations','Affiliations')]:
    if a.get(field):lines+=['  '+label+': '+'; '.join(a[field])]
   if a.get('doi'):lines+=['  DOI: '+a['doi']]
   lines+=['  Link: '+a['link'],'  Abstract: '+(a.get('abstract') or 'Abstract unavailable.'),'']
(folder/'reviewed_digest-2026-10-17.structured.md').write_text('\n'.join(lines))
report=dict(digest_date='2026-10-17',windows=candidate['windows'],candidate_counts=counts,curated_counts=curated,highlights=len(review['highlights']),decisions=decisions)
for field in ['abstract','authors','affiliations']:
 report['missing_'+field]=[a['title'] for v in kept.values() for a in v if not a.get(field) or a.get(field)=='Abstract unavailable.']
(folder/'curation_audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='decisions'},indent=2))
