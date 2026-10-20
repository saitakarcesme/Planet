"""Window OCR with line-local recognition for large display text.

Sparse page segmentation can misrecognize even high-confidence large digits.
Re-read large lines from the same snapshot with single-line segmentation; never
replace screen contents with a calculated or model-inferred expected value.
"""
import csv
import io
import os
from pathlib import Path


def read_lines(image, scratch, command):
    def words(path, mode):
        text = command(['tesseract', str(path), 'stdout', '-l', 'eng', '--psm', str(mode), 'tsv'],
                       timeout=12, env=dict(os.environ, OMP_THREAD_LIMIT='2'))
        # Tesseract TSV is raw text, not CSV-quoted. A literal double quote in
        # a title must not consume subsequent lines as a quoted CSV field.
        return [r for r in csv.DictReader(io.StringIO(text), delimiter='\t', quoting=csv.QUOTE_NONE)
                if (r.get('text') or '').strip() and float(r.get('conf', '-1')) >= 35]

    groups = {}
    for row in words(image, 11):
        groups.setdefault((0,row['block_num'], row['par_num'], row['line_num']), []).append(row)
    high_contrast=Path(scratch)/'contrast.png'
    command(['magick', str(image), '-colorspace', 'Gray', '-threshold', '65%', '-negate', str(high_contrast)])
    for row in words(high_contrast,11):
        if float(row['conf'])>=60:
            groups.setdefault((1,row['block_num'],row['par_num'],row['line_num']),[]).append(row)
    result = []
    refined = 0
    for rows in list(groups.values())[:100]:
        text = ' '.join(r['text'] for r in rows)
        left = min(int(r['left']) for r in rows)
        top = min(int(r['top']) for r in rows)
        right = max(int(r['left'])+int(r['width']) for r in rows)
        bottom = max(int(r['top'])+int(r['height']) for r in rows)
        confidence=sum(float(r['conf']) for r in rows)/len(rows)
        overlaps=[]
        for i,prior in enumerate(result):
            l,t,r,b=prior['bounds']
            intersection=max(0,min(right,r)-max(left,l))*max(0,min(bottom,b)-max(top,t))
            if intersection/max(1,min((right-left)*(bottom-top),(r-l)*(b-t)))>.65:overlaps.append(i)
        if overlaps and any(result[i]['confidence']>=confidence-5 for i in overlaps):continue
        for i in reversed(overlaps):result.pop(i)
        if bottom-top >= 48 and refined < 6:
            # Input is captured at 2x desktop resolution. Crop from that image,
            # retaining a small margin and the actual background.
            x = max(0, left-10);y = max(0, top-10)
            crop = Path(scratch)/f'line-{refined}.png';refined += 1
            command(['magick', str(image), '-crop', f'{right-x+10}x{bottom-y+10}+{x}+{y}',
                     '+repage', str(crop)])
            local = words(crop, 7)
            if local:
                text = ' '.join(r['text'] for r in local)
        result.append({'text': text, 'bounds': [left, top, right, bottom], 'confidence': confidence})
    return sorted(result,key=lambda line:(line['bounds'][1],line['bounds'][0]))[:100]
