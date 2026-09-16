
# Alt Manager

Injects `client.dll` into a running Minecraft (Java) process and lets you
swap the game account from an in-game ImGui overlay.

## Build

```bash
python create_account.py
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

Artifacts:
- `build/client.dll`
- `build/injector.exe`

## Run

1. Launch Minecraft (Java Edition).
2. `injector.exe client.dll`  (defaults to `javaw.exe`).
3. Press the injected overlay — add accounts, click **Apply**.

## How it works

- `client.dll` attaches to the running JVM via `JNI_GetCreatedJavaVMs`.
- A background thread reaches into `net.minecraft.client.Minecraft.getInstance()`,
  finds the live `Session` object by reflection, and overwrites
  `username` / `uuid` / `token`.
- `wglSwapBuffers` is hooked with MinHook to render the ImGui overlay.
