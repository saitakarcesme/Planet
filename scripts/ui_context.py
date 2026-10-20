#!/usr/bin/env python3
import json
from desktop import hypr
try:
    window=hypr('activewindow')
    monitors=hypr('monitors')
    cursor=hypr('cursorpos')
    screen=next((m for m in monitors if m['x']<=cursor['x']<m['x']+m['width']/m['scale'] and m['y']<=cursor['y']<m['y']+m['height']/m['scale']),next(m for m in monitors if m['focused']))
    print(json.dumps({'window':window.get('address'),'screen':screen['name']}))
except Exception:
    print('{}')
