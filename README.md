# SecretsPaste

Decky plugin that lets you keep sensitive snippets encrypted via gopass or a built-in encrypted local vault, and copy them to the clipboard with an automatic wipe timer. This was definitely not built to deal with a game launcher that rhymes with SploobyShmoft Shmonnect constantly asking for my password when I wanted to play Assassins Creed 2.

## Requirements

- Steam Game Mode environment (SteamOS, Bazzite, CachyOS, etc.) with DeckyLoader installed.
- Node.js + npm (for building locally).
- Optional: [gopass](https://www.gopass.pw/) installed and initialized on the Deck (GPG key set up, store created) if you choose the gopass backend. SecretsPaste writes entries under the `secretspaste/` path in your gopass store.

## Features

- Choose storage backend: gopass (GPG-backed) or a built-in encrypted local vault stored under the plugin data directory.
- Optional unlock password for the local vault.
- Store secrets with a friendly name; values are never shown after save.
- Copy a saved secret to the clipboard; after a configurable timeout the clipboard is replaced with a blank string.
- Search/filter stored secrets by name.
- Delete stored secrets with a confirmation; no edit path (delete and recreate instead).

## Configuration

- Pick a backend in the plugin UI: gopass or Local encrypted.
- For the Local backend you can set an optional unlock password; if set, you must unlock before adding/copying/deleting.

## Development

1. Install dependencies:
   ```bash
   npm install
   ```
2. Build once:
   ```bash
   npm run build
   ```
   The output bundle and backend are placed in `dist/`.
3. For iterative work, run:
   ```bash
   npm run watch
   ```
4. To test in Decky, copy or symlink the project (or `dist/`) into your Decky plugins folder (e.g. `~/homebrew/plugins/SecretsPaste`) and reload DeckyLoader. Ensure `gopass` works on the Deck.
5. Backend Python dependency is listed in `backend/requirements.txt` (cryptography); Decky packaging installs it, but if running manually ensure it is available.

## Specification

See `SPEC.md` for a high-level overview of architecture, backends, and expected behaviours.

## License

MIT — see `LICENSE`.

## Notes on storage

- With the gopass backend, secrets live in gopass; the plugin only keeps local metadata (name, id, created timestamp) to drive the UI.
- With the Local backend, secrets are stored in an encrypted file under the plugin data directory with a generated key (optionally wrapped by your unlock password).
- Clipboard clearing runs on the front-end after the configured timeout; you can adjust this in the plugin UI.
