Archived local model runtime source

Preserved when Planet was paused on 2026-10-21. These are the original
machine-specific scripts, not a portable or newly verified installer.
The previous lab root was ~/Projects/omarchypet-model-lab.
HyperQwen upstream: https://github.com/syv-ai/HyperQwen
Pinned checkout: 95ac251bc3b71017c883e83004cf4fb188d066a4

Weights, virtual environments, compiled caches, private benchmark fixtures
and evidence are deliberately excluded. Model revisions are recorded in
scripts/download_pinned.py. The controller also depends on the separate
~/Projects/h2o-lightning-local installation. Restore the original directory
layout, dependencies and evidence directory before attempting these scripts.
Do not run the downloader or preparation scripts merely to inspect this archive.
