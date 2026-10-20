# Planet product requirements

- All application-authored user-facing copy must be English: labels, placeholders,
  statuses, help, demo captions, errors, CLI output, and future model responses.
  Preserve user-authored text and accept requests in other languages.
- Do not implement natural-language requests as hardcoded phrase, keyword, app,
  or URL mappings. Model-driven action planning must observe desktop state and
  use generic tools. Do not substitute a browser URL for an app task.
- The desktop companion is normally the only visible element. Clicking it or
  invoking the global shortcut reveals the borderless floating conversation.
- Use black, gray and white. The companion is an irregular circular field of
  distinct white dots with clearly visible size animation. Dots must never touch.
- Keep the chat compact in width and cap history height; overflow must scroll.
- Local H2O and Qwen are connected through typed tools. Never simulate successful
  actions or execute model-generated shell commands. Check observed postconditions.
- Native applications and standard desktop APIs take precedence over web fallbacks.
- Keep live benchmark fixtures and private UI/model traces out of Git.
