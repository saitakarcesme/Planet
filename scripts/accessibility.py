"""Bounded, contextual native accessibility snapshots, including deep CEF trees."""
import time


def has_readable_content(items):
    # Button labels do not expose custom-drawn results (e.g. a calculator
    # display). Supplement those trees with OCR instead of losing the readout.
    readouts = {'static', 'label', 'paragraph', 'text', 'entry', 'document text',
                'heading', 'table row', 'link', 'combo box'}
    return any(n.get('role') in readouts and (n.get('name') or n.get('text')) for n in items)


def snapshot(root, atspi, serial, address, nodes, limit=240):
    items = []
    visited = 0
    deadline = time.monotonic() + 3
    truncated = False
    scopes = {'landmark', 'table', 'table row', 'dialog', 'document frame', 'menu'}

    def walk(node, depth=0, context=(), ancestor_names=()):
        nonlocal visited, truncated
        if depth > 40 or visited >= 4000 or time.monotonic() > deadline or len(items) >= limit:
            truncated = True
            return
        visited += 1
        try:
            role = node.get_role_name()
            if 'password' in role.lower():
                return
            state = node.get_state_set()
            visible = state.contains(atspi.StateType.SHOWING)
            # Virtualized lists expose thousands of offscreen descendants. Never
            # let those displace the visible document or offer invisible actions.
            if not visible and role in ('table row', 'menu item', 'list item'):
                return
            name = node.get_name() or ''
            actions = [node.get_action_name(i) for i in range(node.get_n_actions())] if node.is_action() else []
            if role in ('static', 'label', 'paragraph', 'table cell', 'heading', 'landmark', 'table'):
                actions = []  # CEF advertises clickAncestor even on decorative text.
            editable = node.is_editable_text()
            content = ''
            if visible and node.is_text() and role not in ('document web', 'panel', 'section', 'table', 'table row'):
                text = node.get_text_iface()
                # Accessible.get_text() is the deprecated interface accessor;
                # GI otherwise resolves it instead of Text.get_text(start, end).
                content = atspi.Text.get_text(text, 0, min(text.get_character_count(), 500)) or ''
            meaningful = actions or editable or role in scopes or role == 'heading'
            label = (name or content).replace('\ufffc', '').strip()
            duplicate = label and any(label in ancestor for ancestor in ancestor_names if ancestor)
            if visible and (label or editable) and (meaningful or not duplicate) and role not in ('panel', 'section', 'image', 'frame', 'document web'):
                key = f'a{serial}:{len(items)}'
                nodes[key] = ('atspi', node, address, actions)
                item = {'id': key, 'source': 'atspi', 'role': role, 'name': name[:300]}
                if content and content != name:
                    item['text'] = content
                if actions:
                    item['actions'] = actions
                if editable:
                    item['editable'] = True
                if context:
                    item['context'] = list(context[-3:])
                if state.contains(atspi.StateType.FOCUSED):
                    item['focused'] = True
                if state.contains(atspi.StateType.SELECTED):
                    item['selected'] = True
                items.append(item)
            next_context = (*context, f'{role}: {name[:300]}') if name and role in scopes else context
            names = (*ancestor_names[-5:], name) if name else ancestor_names
            count = node.get_child_count()
            if count > 160:
                truncated = True
            for i in range(min(count, 160)):
                walk(node.get_child_at_index(i), depth+1, next_context, names)
                if len(items) >= limit or time.monotonic() > deadline:
                    if i+1 < count:
                        truncated = True
                    break
        except Exception:
            truncated = True

    walk(root)
    return items, truncated
