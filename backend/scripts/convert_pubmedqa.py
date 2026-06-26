import json
import os
import re

src = r'E:\Python\Skill-First-Hybrid-RAG\backend\knowledge\medical\pubmedqa_ori_pqal.json'
out_dir = r'E:\Python\Skill-First-Hybrid-RAG\backend\knowledge\medical\literature'

with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total records: {len(data)}')

count = 0
for pmid, item in data.items():
    question = item.get('QUESTION', '')
    contexts = item.get('CONTEXTS', [])
    labels = item.get('LABELS', [])
    meshes = item.get('MESHES', [])
    year = item.get('YEAR', '')
    decision = item.get('final_decision', '')
    long_answer = item.get('LONG_ANSWER', '')

    lines = []
    lines.append('---')
    lines.append(f'pmid: "{pmid}"')
    lines.append('document_type: literature')
    if year:
        lines.append(f'year: {year}')
    if meshes:
        mesh_str = ', '.join(f'"{m}"' for m in meshes)
        lines.append(f'meshes: [{mesh_str}]')
    if decision:
        lines.append(f'final_decision: {decision}')
    lines.append('---')
    lines.append('')
    lines.append('# 研究问题')
    lines.append('')
    lines.append(question)
    lines.append('')

    for i, ctx in enumerate(contexts):
        label = labels[i] if i < len(labels) else 'TEXT'
        lines.append(f'# {label}')
        lines.append('')
        lines.append(ctx)
        lines.append('')

    if long_answer:
        lines.append('# 详细答案')
        lines.append('')
        lines.append(long_answer)
        lines.append('')

    safe = re.sub(r'[^\w\-]', '_', question[:50])
    fname = f'pubmed_{pmid}_{safe}.md'
    fpath = os.path.join(out_dir, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    count += 1

print(f'Converted {count} PubMedQA records to Markdown')
