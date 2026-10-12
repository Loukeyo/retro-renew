# Retro Renew companions

A static GitHub Pages catalogue plus one reusable, fixed-recipe installer
engine. No server, database, viewer accounts, paid services, scraping, or automatic
mod updates. No third-party mods or game files are included.

## What is implemented

- Responsive catalogue with series filters and search across games/mods/authors.
- Permanent hash links such as `https://Loukeyo.github.io/retro-renew/#gta-iv`.
- Per-game companion pages, video links, mod lists, original source links, credits,
  draft status, and release-gated installer links.
- Windows-oriented desktop GUI with folder selection, Steam folder discovery,
  manual ZIP imports, Downloads-folder discovery, author links, install/restore,
  launch, diagnostic export, and background work without freezing the UI.
- Strict executable fingerprints, known-conflict checks, pre-install checks,
  HTTPS/host restrictions for approved direct downloads, exact archive and file
  hashes, bounded ZIP expansion, traversal/symlink checks, explicit file mapping,
  process checks on Windows, same-folder operation locking, staged changes,
  verified backups, atomic file replacement, and persistent recovery journals.
- Restore refuses to overwrite user edits or use damaged backups. A crash can
  be recovered with the same setup's Restore / recover button.
- GitHub Actions workflows for Linux/Windows tests, Pages deployment, and
  Windows executable building.

## Current release status

This is an initial implementation, not a tested real-game release. The catalogue
contains six clearly marked draft/example entries. Existing discussion supplied
some project context, but not the final video links, full mod lists, exact
versions, supported executables, or permission evidence. Do not advertise these
drafts as verified game setups.

The runnable training setup uses only harmless original text files, including
a text file named `TrainingGame.exe`. It is NOT an executable or a real game.
The Play button deliberately refuses to launch it.

Python/core and website behavioural checks were run on Linux. The Windows GUI,
Steam discovery, Windows process checks, packaged EXE, and browser appearance
still need validation on Windows/in a browser. No Windows EXE is included in
this source package. PyInstaller builds Windows executables on Windows; the
included workflow performs that build after repository setup.

## Open the website

Open `site/index.html`, or the included standalone `Retro-Renew-Preview.html`.
The site is buildless HTML/CSS/JavaScript. Web fonts are optional; local fallbacks
work offline. Pages do not require cookies or sign-in. Video and installer
buttons appear only when valid HTTPS links exist.

## Publish to GitHub Pages

1. Use the public repository `Loukeyo/retro-renew`.
2. Push the contents of this directory to its `main` branch.
3. In Settings > Pages, select GitHub Actions as the source.
4. Run the Publish companion website workflow if the initial push did not deploy.

Expected address: `https://Loukeyo.github.io/retro-renew/`.
The repository name can be changed; use the actual resulting Pages URL.
The Pages workflow publishes only after GitHub Pages is enabled for the repository.
A build passing does not itself enable Pages.

## Try the safe training setup

With Python 3.12+ and Tk available:

```sh
python tools/create_demo.py demo
python launcher/app.py demo/recipe.json
```

Browse to `demo/Training Game`, add `demo/retro-renew-demo.zip`, review the
notices, and install. `settings.ini` changes and `mods/renew.txt` is added.
Restore returns the original settings and removes only the newly added file.

To get a self-contained Windows EXE without requiring Python on viewers' PCs,
push installer/build changes to `main`, or run Actions > Build Windows launcher
with the recipe field empty. These build the training demo only. Download the
`RetroRenew-Windows` artifact, extract it, and run the EXE against its included
training folder/archive. Test the EXE before distributing it. It is unsigned;
do not tell viewers to disable Windows security to run it.

For a reviewed real recipe, specify `recipes/<game-id>.json` in that workflow.
On a Windows development machine you can alternatively run:

```sh
python -m pip install PyInstaller==6.22.3
python tools/build_launcher.py --recipe recipes/<game-id>.json
```

Build artifacts include `SHA256SUMS.txt` and `build-info.json` with the recipe
fingerprint, packager version, and explicit unverified Windows runtime status.
Compare the EXE hash before publication. Actions artifacts expire after GitHub's
configured retention period; they are review downloads, not permanent release links.

Recipe paths must refer to JSON files within the repository.

Compiled EXEs embed one recipe and do not accept external recipe arguments or
silently fetch replacement recipes. Publish the tested binary through a GitHub
Release, then insert its asset URL in the catalogue. Builds do not automatically
publish releases or mark any game verified.

## Add a video companion page

Edit `site/catalogue.js`: copy one game entry, choose a unique permanent `id`,
and enter its title, series, supported edition, notes, and original mod links.
Set `videoUrl` to the actual video link. Leave `installerUrl` null for a
reference-only page. Use `status: 'reference'` once the list is confirmed.

To cover the same game in multiple videos, use a new ID per setup, e.g.
`gta-iv-collection-2026`. Never silently repurpose an existing shared URL.

The code intentionally does not claim draft mods were all featured in the video.
Confirm the final list before removing draft labels. Optional mods can be listed
without including them in a tested installer.

## Add a real installer recipe

Copy `recipes/game.template.json` to a real recipe path. The template is
deliberately invalid for installation. Fill every checksum and permission field,
then change `status` to `released` only after review and testing.

- `markers`: fingerprints of the actual supported game files; MUST include the
  executable. This engine refuses to replace identity markers or executables.
- `conflicts`: known conflicting file/directory paths. Unknown destination files
  are also blocked automatically. This is not universal mod-conflict detection.
- `protected`: directories/files that must never be installed over, e.g. saves.
- `artifacts`: exact ZIP archives. `max_bytes` and `expanded_bytes` bound input.
- `files`: explicit source/destination pairs and the extracted file hashes.
  `original_sha256: null` means the destination MUST NOT exist. For replacement,
  provide the supported original file hash. No globbing or blind extraction.
- `permission`: record the applicable licence clause or written permission,
  review date, author, and source. `reviewed: true` is a maintainer declaration,
  not proof generated by the software. Preserve required licence files by adding
  them explicitly to the file mappings where appropriate.
- `method: manual`: viewer downloads from the original page and imports the ZIP.
- `method: direct`: only after confirming author AND hosting permission. Add an
  exact HTTPS `url` and `allowed_hosts`, including legitimate redirect hosts.
  Never use latest-release URLs for version-pinned recipes. Never bypass logins,
  payment, download buttons, or site restrictions.

Fingerprint a file with `python tools/fingerprint.py path/to/file`.

The engine cannot infer legal permission, software compatibility, dependency
requirements, or correct load order. Recipe order is installation order, with
overlapping destinations rejected. Resolve all compatibility decisions first.
If combinations need merged files, create your own permitted configuration file
or obtain permission for altered assets before using them.

## Real-game release checklist

- Confirm the exact supported edition, files, tool licences, download permissions,
  dependency requirements, and author notices. Never include game/BIOS files.
- Test a clean supported game, a wrong edition, conflicting mods, low disk space,
  running game, invalid archive, interrupted installation, damaged backup,
  changed installed files, and full restoration.
- Run the compiled EXE on supported Windows versions and normal non-admin accounts.
- Start and play the game after install; file checks cannot establish playability.
- Validate launch from Steam/GOG as appropriate; direct EXE launching is optional
  and may not suit every store. Viewers can use their regular store client.
- Confirm screen-reader/readability/navigation and scaling in the Windows GUI.
- Publish the tested EXE, checksum, supported edition, limitations, and test date.
- Add the real `installerUrl` and `testedDate`, and mark the catalogue entry
  `released` only when the corresponding released recipe is present.

## Deliberate limits

ZIP file-copy installations only. No RAR/7z, executable patching/downgrades,
registry edits, arbitrary shell hooks, driver installation, automated external
installers, or silent runtime installation. Games needing those features stay
reference-only until a separately designed and tested integration exists.

Local game folders only; symlink/junction game paths and Windows UNC folders
are rejected. No administrator escalation. Protected game folders may need a
different installation location. No promise of universal system compatibility.

Backups and journals live in `<game>/.retro-renew`. Keep them until you no
longer need restoration. All files changed by a setup must still match either
the original or installed hash for automatic recovery. Recovery refuses unknown
edits rather than deleting them. Do not edit journals or recovery folders.

Each file replacement is atomic, but the whole installation is not a single
filesystem transaction. Power loss/crashes can leave a partial installation;
the persistent journal supports recovery. Storage hardware failures, hostile
concurrent programs, and deleted/corrupted recovery data cannot be fixed by this
installer. The tool cannot prevent someone starting a game between process checks.

Fixed versions reduce maintenance; upstream downloads can still disappear.
Mark an unavailable setup accordingly instead of substituting untested files.
Direct downloads use 30-second per-request timeouts; there is no mid-operation
cancel button, automatic retry loop, or promise of a total download time limit.

## Checks

```sh
python -m unittest discover -s tests -v
python tools/check_project.py
node tests/test_site.js
```

The site checker requires Node. Tests use only standard-library Python/Node.
CI runs installer tests on Linux and Windows. Website behaviour tests use a
minimal DOM stub, not a rendered browser. Third-party permissions and actual
game compatibility always need human review.

## Licence

MIT for original project code and training fixtures. Third-party projects
retain their own rights. No redistribution rights are implied by reference links.
