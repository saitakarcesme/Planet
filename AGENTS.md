# Planet product requirements

- All application-authored user-facing copy must be English: labels, placeholders,
  statuses, help, demo captions, errors, CLI output, and future model responses.
  Preserve user-authored text and accept requests in other languages.
- The user approved 100 explicit reusable native capabilities and anchored
  natural-language aliases. Validate parameters, observe native targets and
  verify postconditions. Unknown tasks use the general model planner. Compose up to four fully matched
  capability clauses; never execute only the recognized part of a request.
  Do not substitute a browser URL for a native application task.
- Nothing is normally visible. Super+Alt+P opens one wide centered command
  field on the pointer's monitor, with a white glow on all four screen edges.
- Use black, gray and white. No pet, message bubbles or conversation chain.
  Requested output and errors replace the current result in the same panel.
- Enter runs a command, Escape closes the panel, and Stop cancels work.
- Successful action-only tasks close silently. Never hide a requested answer.
- Local H2O and Qwen are connected through typed tools. Never simulate successful
  actions or execute model-generated shell commands. Check observed postconditions.
- Native applications and standard desktop APIs take precedence over web fallbacks.
- Keep live benchmark fixtures and private UI/model traces out of Git.
