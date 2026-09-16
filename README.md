# Minecraft Offline Account Switcher

In-game overlay to switch offline Minecraft accounts. Opens with the **UP ARROW** key.

## How to use

1. Push this repo to GitHub.
2. The `Build Client` workflow runs automatically and produces an artifact `mc-account-switcher`.
3. Download the artifact — it contains `client.dll` and `injector.exe`.
4. Put them in the same folder.
5. Launch Minecraft.
6. Run `injector.exe` (as Administrator if needed) — it auto-detects `javaw.exe`.
7. In-game, press **UP ARROW** to open the switcher.
8. Add a username, click it to switch — the live game's Session is replaced via JNI.

Accounts are stored in `%APPDATA%\.mc-account-switcher\accounts.txt`.

## Notes

- Offline UUIDs are computed the same way vanilla does (`UUID.nameUUIDFromBytes("OfflinePlayer:"+name)`).
- On some versions the `Session` constructor signature differs; the DLL tries the modern ctor
  `(String, UUID, String, Optional)` then falls back to the legacy `(String, String, String, String)`.
