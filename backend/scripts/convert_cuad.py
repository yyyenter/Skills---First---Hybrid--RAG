import json
import os
import re

src = r'E:\Python\Skill-First-Hybrid-RAG\backend\knowledge\legal\contracts\CUAD_v1.json'
out_dir = r'E:\Python\Skill-First-Hybrid-RAG\backend\knowledge\legal\contracts'

with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

contracts = data.get('data', [])
print(f'Total contracts: {len(contracts)}')

count = 0
for idx, contract in enumerate(contracts):
    title = contract.get('title', f'contract_{idx}')
    paragraphs = contract.get('paragraphs', [])

    # Extract full text from all paragraphs
    full_texts = []
    all_qas = []
    for para in paragraphs:
        ctx = para.get('context', '')
        if ctx:
            full_texts.append(ctx)
        qas = para.get('qas', [])
        for qa in qas:
            q = qa.get('question', '')
            answers = qa.get('answers', [])
            ans_texts = [a.get('text', '') for a in answers]
            all_qas.append({'question': q, 'answers': ans_texts})

    lines = []
    lines.append('---')
    lines.append(f'contract_name: "{title}"')
    lines.append('document_type: contract')
    lines.append(f'contract_index: {idx}')
    lines.append('---')
    lines.append('')
    lines.append('# 合同全文')
    lines.append('')
    for ctx in full_texts:
        lines.append(ctx)
        lines.append('')

    # Add QA annotations as appendix
    if all_qas:
        lines.append('# 条款标注')
        lines.append('')
        for i, qa in enumerate(all_qas[:20]):  # limit to first 20 to avoid huge files
            q = qa['question']
            ans = qa['answers']
            lines.append(f'## 标注 {i+1}')
            lines.append(f'**问题**: {q}')
            if ans:
                lines.append(f'**答案**: {ans[0]}')
            lines.append('')

    safe = re.sub(r'[^\w\-]', '_', title[:60])
    fname = f'cuad_{idx:04d}_{safe}.md'
    fpath = os.path.join(out_dir, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    count += 1

print(f'Converted {count} CUAD contracts to Markdown')
