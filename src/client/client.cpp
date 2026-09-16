
#include "hooks.h"
#include "gui.h"
#include "jni_helper.h"
#include "accounts.h"

#include <windows.h>
#include <chrono>
#include <thread>

static HMODULE g_self = nullptr;

static DWORD WINAPI MainThread(LPVOID) {
    // Wait for the host JVM to be fully initialised.
    std::this_thread::sleep_for(std::chrono::seconds(2));

    JNIHelper::attach();
    Hooks::Install();

    // Keep re-applying the selected account (Minecraft may cache it).
    while (true) {
        if (AccountManager::instance().has_current()) {
            auto a = AccountManager::instance().current();
            JNIHelper::apply_account(a.username, a.uuid, a.token);
        }
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hMod, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = hMod;
        DisableThreadLibraryCalls(hMod);
        CreateThread(nullptr, 0, MainThread, nullptr, 0, nullptr);
    }
    return TRUE;
}
