# Customer Discovery website example

The walkthrough uses `customer-discovery.json` as its shared source for six authored teaching excerpts and a three-step playbook. These represent a YouTube talk, podcast, research PDF, article, team notes, and workshop video. Actual packaged inputs are VTT, TXT, Markdown, and SRT. No original media, live retrieval, or automatic transcription is implied.

`build_pack.py` uses real Lectic ingestion, checkpoints, reconciliation, method/result validation, pack export, and installation. All work runs in temporary homes. It exports `../packs/customer-discovery.lectic` and writes `pack-info.json` after a fresh recipient install and evidence verification pass. The twelve source procedures are explicit; combining them into the playbook is authored synthesis. These are MIT-licensed fictional teaching materials, not an effectiveness study.

To rebuild after changing the sample content, run `python docs/demo/build_pack.py` from the repository root with the package dependencies installed. Commit the JSON, pack, and checksum metadata together. Rebuilding changes archive timestamps and therefore the checksum. The website previews this artifact rather than calling a backend. Its download is separate from the starter bundled in Lectic 0.3.1, so it can be installed without changing the package release.

Before publishing, check source selectors, all three journey tabs and keyboard navigation, playbook evidence switching, install-request copying, download checksum, failed data-loading fallback, and narrow layouts.
