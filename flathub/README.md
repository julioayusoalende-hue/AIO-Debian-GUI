# Flathub submission preparation (v1.0.16)

The file `io.github.julioayusoalende_hue.aio_debian_gui.yml` is a **candidate** for Flathub submission. It fetches a pinned Git commit rather than relying on a local `path: ..` source. The file in this directory is **not yet published to Flathub**.

## Blocking prerequisites

1. Add authentic application screenshots to AppStream metadata using stable, publicly accessible image URLs. Flathub requires screenshots; there are none in this project's repository at present. Do not invent or generate mock screenshots purporting to demonstrate the app.
2. Provide high-quality English-default AppStream metadata, desktop integration and user interface; keep Spanish translations available.
3. Review the host-helper design. The application currently uses `flatpak-spawn --host` to launch a host-installed privileged helper via `pkexec`. Maintenance functions are unavailable until this helper and its Polkit policy are installed on Debian. This must be disclosed and discussed with Flathub reviewers; the Flatpak must not silently install or replace privileged host files.
4. Run `flatpak-builder` with this manifest and `flatpak-builder-lint manifest`, `flatpak-builder-lint repo`, and AppStream validation. A successful GitHub bundle build is not equivalent to Flathub acceptance.
5. After the prerequisites, copy the manifest to the **root of a fork of `flathub/flathub`**, create a submission branch from `new-pr`, and open a PR targeting `new-pr`. Flathub does not accept submissions against `master`.

Reference: https://docs.flathub.org/docs/for-app-authors/submission
