#include <Windows.h>
#include <cstring>
#include "hooks.h"

static BOOL CALLBACK FindGameWindow(HWND w, LPARAM lp) {
    DWORD wpid = 0;
    GetWindowThreadProcessId(w, &wpid);
    if (wpid != GetCurrentProcessId()) return TRUE;
    if (!IsWindowVisible(w)) return TRUE;
    char cls[256] = {};
    GetClassNameA(w, cls, sizeof(cls));
    // LWJGL/GLFW windows: "GLFW30" (GLFW 3.x), "LWJGL", or fallback: has title "Minecraft"
    bool glfw = (strstr(cls, "GLFW") || strstr(cls, "LWJGL"));
    char title[512] = {};
    GetWindowTextA(w, title, sizeof(title));
    bool mc = (strstr(title, "Minecraft") != nullptr);
    if (glfw || mc) {
        *reinterpret_cast<HWND*>(lp) = w;
        return FALSE;
    }
    return TRUE;
}

static DWORD WINAPI BootThread(LPVOID) {
    HWND hwnd = nullptr;
    for (int i = 0; i < 600 && !hwnd; i++) {
        EnumWindows(FindGameWindow, (LPARAM)&hwnd);
        if (!hwnd) Sleep(100);
    }
    if (hwnd) {
        Sleep(500); // let the game settle
        hooks::Init(hwnd);
    }
    return 0;
}

BOOL WINAPI DllMain(HMODULE mod, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(mod);
        HANDLE t = CreateThread(nullptr, 0, BootThread, nullptr, 0, nullptr);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
