# First release milestone

Goal: publish the Retro Renew game companion catalogue and establish a reproducible
Windows training-demo build before approving any real-game installer.

Acceptance:
- Catalogue source published to the public repository.
- GitHub Pages serves the catalogue, preserving draft/example labels and original creator links.
- Linux and Windows installer regression checks pass.
- Windows workflow produces the training EXE, fixture, checksums, and build metadata.
- Real-game downloads remain disabled until a supported executable, exact mod versions,
  permissions, and actual gameplay/restoration tests have been reviewed.

Three developers worked on catalogue navigation/accessibility, installer recovery,
and build/deployment tooling. Root integration also fixes packaging so it never
regenerates over a user's existing training fixture.

Next milestone: approve one essential-fixes recipe for one specific game edition,
test the compiled launcher on supported Windows systems, then publish a numbered release.
