
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_account.py
-----------------
Generates the full Alt-Manager project (CMakeLists.txt + all C++ sources).
Run from the repo root:  python create_account.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.resolve()

def w(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"[+] {rel}")

# ---------------------------------------------------------------- .gitignore
w(".gitignore", r"""
build/
out/
*.obj
*.pdb
*.ilk
*.exp
*.lib
*.dll
*.exe
.vs/
.vscode/
__pycache__/
""")

# ---------------------------------------------------------------- CMakeLists
w("CMakeLists.txt", r"""
cmake_minimum_required(VERSION 3.20)
project(AltManager LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 11)

include(FetchContent)

# -------- ImGui (raw source, no add_subdirectory) --------
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG        v1.91.5
    SOURCE_SUBDIR  _skip_subdir
)
FetchContent_MakeAvailable(imgui)

add_library(imgui STATIC
    "${imgui_SOURCE_DIR}/imgui.cpp"
    "${imgui_SOURCE_DIR}/imgui_draw.cpp"
    "${imgui_SOURCE_DIR}/imgui_tables.cpp"
    "${imgui_SOURCE_DIR}/imgui_widgets.cpp"
    "${imgui_SOURCE_DIR}/backends/imgui_impl_win32.cpp"
    "${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp"
)
target_include_directories(imgui PUBLIC
    "${imgui_SOURCE_DIR}"
    "${imgui_SOURCE_DIR}/backends"
)

# -------- MinHook (raw source, compile straight into client.dll) --------
FetchContent_Declare(
    minhook
    GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
    GIT_TAG        v1.3.3
    SOURCE_SUBDIR  _skip_subdir
)
FetchContent_MakeAvailable(minhook)

set(MINHOOK_SOURCES
    "${minhook_SOURCE_DIR}/src/buffer.c"
    "${minhook_SOURCE_DIR}/src/hook.c"
    "${minhook_SOURCE_DIR}/src/trampoline.c"
    "${minhook_SOURCE_DIR}/src/hde/hde64.c"
)
if(EXISTS "${minhook_SOURCE_DIR}/src/hde/table64.c")
    list(APPEND MINHOOK_SOURCES "${minhook_SOURCE_DIR}/src/hde/table64.c")
endif()

# -------- System deps --------
find_package(JNI REQUIRED)
find_package(OpenGL REQUIRED)

# -------- client.dll --------
add_library(client SHARED
    src/client/accounts.cpp
    src/client/jni_helper.cpp
    src/client/gui.cpp
    src/client/hooks.cpp
    src/client/client.cpp
    ${MINHOOK_SOURCES}
)

target_include_directories(client PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src/client"
    "${minhook_SOURCE_DIR}/include"
    ${JNI_INCLUDE_DIRS}
)

target_link_libraries(client PRIVATE
    imgui
    ${JNI_LIBRARIES}
    opengl32
)

set_target_properties(client PROPERTIES
    PREFIX ""
    OUTPUT_NAME "client"
)

# -------- injector.exe --------
add_executable(injector src/injector/injector.cpp)
set_target_properties(injector PROPERTIES OUTPUT_NAME "injector")
""")

# ---------------------------------------------------------------- accounts.h
w("src/client/accounts.h", r"""
#pragma once
#include <mutex>
#include <string>
#include <vector>

struct Account {
    std::string username;
    std::string uuid;
    std::string token;
};

class AccountManager {
public:
    static AccountManager& instance();

    void add(const Account& acc);
    bool remove(size_t index);
    bool set_current(size_t index);

    Account current() const;
    int current_index() const;
    bool has_current() const;
    std::vector<Account> list() const;

private:
    AccountManager() = default;
    mutable std::mutex mtx_;
    std::vector<Account> accounts_;
    int current_ = -1;
};
""")

# ---------------------------------------------------------------- accounts.cpp
w("src/client/accounts.cpp", r"""
#include "accounts.h"

AccountManager& AccountManager::instance() {
    static AccountManager inst;
    return inst;
}

void AccountManager::add(const Account& acc) {
    std::lock_guard<std::mutex> lock(mtx_);
    accounts_.push_back(acc);
    if (current_ < 0) current_ = 0;
}

bool AccountManager::remove(size_t index) {
    std::lock_guard<std::mutex> lock(mtx_);
    if (index >= accounts_.size()) return false;
    accounts_.erase(accounts_.begin() + index);
    if (accounts_.empty()) current_ = -1;
    else if (current_ >= (int)accounts_.size()) current_ = (int)accounts_.size() - 1;
    return true;
}

bool AccountManager::set_current(size_t index) {
    std::lock_guard<std::mutex> lock(mtx_);
    if (index >= accounts_.size()) return false;
    current_ = (int)index;
    return true;
}

Account AccountManager::current() const {
    std::lock_guard<std::mutex> lock(mtx_);
    if (current_ < 0 || current_ >= (int)accounts_.size()) return {};
    return accounts_[current_];
}

int AccountManager::current_index() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return current_;
}

bool AccountManager::has_current() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return current_ >= 0 && current_ < (int)accounts_.size();
}

std::vector<Account> AccountManager::list() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return accounts_;
}
""")

# ---------------------------------------------------------------- jni_helper.h
w("src/client/jni_helper.h", r"""
#pragma once
#include <jni.h>
#include <string>

class JNIHelper {
public:
    static bool attach();
    static void detach();
    static bool is_attached();
    static JavaVM* vm();
    static JNIEnv* env();

    // Reaches into the running Minecraft JVM and overwrites the live
    // Session's username / uuid / token fields via reflection.
    static bool apply_account(const std::string& username,
                              const std::string& uuid,
                              const std::string& token);
};
""")

# ---------------------------------------------------------------- jni_helper.cpp
w("src/client/jni_helper.cpp", r"""
#include "jni_helper.h"
#include <windows.h>
#include <cstring>
#include <string>

static JavaVM*        g_vm  = nullptr;
static thread_local JNIEnv* t_env = nullptr;

JavaVM* JNIHelper::vm()          { return g_vm; }
JNIEnv* JNIHelper::env()         { return t_env; }
bool    JNIHelper::is_attached() { return t_env != nullptr; }

bool JNIHelper::attach() {
    if (t_env) return true;

    if (!g_vm) {
        jsize count = 0;
        if (JNI_GetCreatedJavaVMs(&g_vm, 1, &count) != JNI_OK || count == 0) {
            g_vm = nullptr;
            return false;
        }
    }

    jint rc = g_vm->GetEnv(reinterpret_cast<void**>(&t_env), JNI_VERSION_1_8);
    if (rc == JNI_EDETACHED) {
        if (g_vm->AttachCurrentThread(reinterpret_cast<void**>(&t_env), nullptr) != JNI_OK) {
            t_env = nullptr;
            return false;
        }
    } else if (rc != JNI_OK) {
        t_env = nullptr;
        return false;
    }
    return true;
}

void JNIHelper::detach() {
    if (g_vm && t_env) {
        g_vm->DetachCurrentThread();
        t_env = nullptr;
    }
}

// ---------------------------------------------------------------- helpers

static jobjectArray call_getDeclaredFields(JNIEnv* e, jclass cls) {
    jclass ccls = e->FindClass("java/lang/Class");
    jmethodID m  = e->GetMethodID(ccls, "getDeclaredFields", "()[Ljava/lang/reflect/Field;");
    if (!m) return nullptr;
    return static_cast<jobjectArray>(e->CallObjectMethod(cls, m));
}

static std::string jstr(JNIEnv* e, jstring s) {
    if (!s) return {};
    const char* c = e->GetStringUTFChars(s, nullptr);
    std::string out = c ? c : "";
    e->ReleaseStringUTFChars(s, c);
    return out;
}

// ---------------------------------------------------------------- apply

bool JNIHelper::apply_account(const std::string& username,
                              const std::string& uuid,
                              const std::string& token) {
    if (!attach()) return false;
    JNIEnv* e = t_env;

    // 1) net.minecraft.client.Minecraft.getInstance()
    jclass mcClass = e->FindClass("net/minecraft/client/Minecraft");
    if (!mcClass) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jmethodID getInstance = e->GetStaticMethodID(
        mcClass, "getInstance", "()Lnet/minecraft/client/Minecraft;");
    if (!getInstance) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jobject mc = e->CallStaticObjectMethod(mcClass, getInstance);
    if (!mc) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    // 2) find the Session field on the Minecraft instance
    jclass mcInstCls   = e->GetObjectClass(mc);
    jclass classCls    = e->FindClass("java/lang/Class");
    jclass fieldCls    = e->FindClass("java/lang/reflect/Field");

    jmethodID fieldGet           = e->GetMethodID(fieldCls, "get", "(Ljava/lang/Object;)Ljava/lang/Object;");
    jmethodID fieldSet           = e->GetMethodID(fieldCls, "set", "(Ljava/lang/Object;Ljava/lang/Object;)V");
    jmethodID fieldSetAccessible = e->GetMethodID(fieldCls, "setAccessible", "(Z)V");
    jmethodID fieldGetType       = e->GetMethodID(fieldCls, "getType", "()Ljava/lang/Class;");
    jmethodID fieldGetName       = e->GetMethodID(fieldCls, "getName", "()Ljava/lang/String;");
    jmethodID classGetName       = e->GetMethodID(classCls, "getName", "()Ljava/lang/String;");

    jobjectArray mcFields = call_getDeclaredFields(e, mcInstCls);
    if (!mcFields) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jobject session = nullptr;
    jsize nf = e->GetArrayLength(mcFields);
    for (jsize i = 0; i < nf && !session; ++i) {
        jobject f = e->GetObjectArrayElement(mcFields, i);

        jclass ftype = static_cast<jclass>(e->CallObjectMethod(f, fieldGetType));
        std::string typeName = jstr(e, static_cast<jstring>(e->CallObjectMethod(ftype, classGetName)));

        if (typeName.find("Session") != std::string::npos) {
            e->CallVoidMethod(f, fieldSetAccessible, JNI_TRUE);
            session = e->CallObjectMethod(f, fieldGet, mc);
        }
    }
    if (!session) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    // 3) overwrite username / uuid / token on the Session instance
    jclass sessionCls = e->GetObjectClass(session);
    jobjectArray sFields = call_getDeclaredFields(e, sessionCls);
    if (!sFields) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jsize nsf = e->GetArrayLength(sFields);
    for (jsize i = 0; i < nsf; ++i) {
        jobject f = e->GetObjectArrayElement(sFields, i);
        std::string name = jstr(e, static_cast<jstring>(e->CallObjectMethod(f, fieldGetName)));

        std::string value;
        if      ((name == "username")   && !username.empty()) value = username;
        else if ((name == "uuid" || name == "playerUUID") && !uuid.empty()) value = uuid;
        else if ((name == "token" || name == "accessToken" || name == "sessionToken")
                 && !token.empty()) value = token;

        if (!value.empty()) {
            e->CallVoidMethod(f, fieldSetAccessible, JNI_TRUE);
            jstring jval = e->NewStringUTF(value.c_str());
            e->CallVoidMethod(f, fieldSet, session, jval);
            e->DeleteLocalRef(jval);
        }
        e->DeleteLocalRef(f);
    }
    return true;
}
""")

# ---------------------------------------------------------------- gui.h
w("src/client/gui.h", r"""
#pragma once

namespace GUI {
    void Render();
    void Toggle();
    bool IsVisible();
}
""")

# ---------------------------------------------------------------- gui.cpp
w("src/client/gui.cpp", r"""
#include "gui.h"
#include "accounts.h"
#include "jni_helper.h"

#include <imgui.h>
#include <cstring>

static bool g_visible      = true;
static char g_new_username[64]  = "";
static char g_new_uuid[64]      = "";
static char g_new_token[256]    = "";

void GUI::Toggle()       { g_visible = !g_visible; }
bool GUI::IsVisible()    { return g_visible; }

void GUI::Render() {
    if (!g_visible) return;

    ImGui::SetNextWindowSize(ImVec2(440, 400), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Alt Manager", &g_visible)) { ImGui::End(); return; }

    ImGui::TextUnformatted("Accounts");
    ImGui::Separator();

    auto accounts = AccountManager::instance().list();
    int  current  = AccountManager::instance().current_index();

    for (int i = 0; i < (int)accounts.size(); ++i) {
        const auto& a = accounts[i];
        ImGui::PushID(i);

        bool selected = (i == current);
        if (ImGui::Selectable(a.username.c_str(), selected)) {
            AccountManager::instance().set_current((size_t)i);
            JNIHelper::apply_account(a.username, a.uuid, a.token);
        }

        ImGui::SameLine();
        if (ImGui::SmallButton("Apply")) {
            AccountManager::instance().set_current((size_t)i);
            JNIHelper::apply_account(a.username, a.uuid, a.token);
        }
        ImGui::SameLine();
        if (ImGui::SmallButton("X")) {
            AccountManager::instance().remove((size_t)i);
            ImGui::PopID();
            break;
        }
        ImGui::PopID();
    }

    ImGui::Separator();
    ImGui::TextUnformatted("Add new account");
    ImGui::InputText("Username", g_new_username, sizeof(g_new_username));
    ImGui::InputText("UUID",     g_new_uuid,     sizeof(g_new_uuid));
    ImGui::InputText("Token",    g_new_token,    sizeof(g_new_token));

    if (ImGui::Button("Add")) {
        Account a{g_new_username, g_new_uuid, g_new_token};
        if (!a.username.empty()) {
            AccountManager::instance().add(a);
            std::memset(g_new_username, 0, sizeof(g_new_username));
            std::memset(g_new_uuid,     0, sizeof(g_new_uuid));
            std::memset(g_new_token,    0, sizeof(g_new_token));
        }
    }

    ImGui::End();
}
""")

# ---------------------------------------------------------------- hooks.h
w("src/client/hooks.h", r"""
#pragma once

namespace Hooks {
    bool Install();
    void Uninstall();
}
""")

# ---------------------------------------------------------------- hooks.cpp
w("src/client/hooks.cpp", r"""
#include "hooks.h"
#include "gui.h"

#include <MinHook.h>
#include <windows.h>
#include <GL/gl.h>

#include <imgui.h>
#include <imgui_impl_win32.h>
#include <imgui_impl_opengl3.h>

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(
    HWND, UINT, WPARAM, LPARAM);

using SwapBuffersFn = BOOL(WINAPI*)(HDC);

static SwapBuffersFn g_origSwapBuffers = nullptr;
static HWND          g_hwnd            = nullptr;
static WNDPROC       g_origWndProc     = nullptr;
static bool          g_imguiReady      = false;

static LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wp, LPARAM lp) {
    if (g_imguiReady && ImGui_ImplWin32_WndProcHandler(hWnd, msg, wp, lp))
        return TRUE;
    return CallWindowProc(g_origWndProc, hWnd, msg, wp, lp);
}

static BOOL WINAPI HookedSwapBuffers(HDC hdc) {
    if (!g_imguiReady) {
        g_hwnd = WindowFromDC(hdc);
        if (g_hwnd) {
            ImGui::CreateContext();
            ImGui::StyleColorsDark();
            ImGui_ImplWin32_Init(g_hwnd);
            ImGui_ImplOpenGL3_Init("#version 130");
            g_origWndProc = (WNDPROC)SetWindowLongPtr(
                g_hwnd, GWLP_WNDPROC, (LONG_PTR)WndProc);
            g_imguiReady = true;
        }
    }

    if (g_imguiReady) {
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplWin32_NewFrame();
        ImGui::NewFrame();

        GUI::Render();

        ImGui::Render();
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
    }

    return g_origSwapBuffers(hdc);
}

bool Hooks::Install() {
    if (MH_Initialize() != MH_OK) return false;

    HMODULE gdi = GetModuleHandleA("gdi32.dll");
    if (!gdi) return false;

    void* target = (void*)GetProcAddress(gdi, "SwapBuffers");
    if (!target) return false;

    if (MH_CreateHook(target, (LPVOID)&HookedSwapBuffers,
                      (LPVOID*)&g_origSwapBuffers) != MH_OK)
        return false;

    return MH_EnableHook(target) == MH_OK;
}

void Hooks::Uninstall() {
    MH_DisableHook(MH_ALL_HOOKS);
    MH_Uninitialize();
}
""")

# ---------------------------------------------------------------- client.cpp
w("src/client/client.cpp", r"""
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
""")

# ---------------------------------------------------------------- injector.cpp
w("src/injector/injector.cpp", r"""
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <string>

static DWORD FindProcess(const wchar_t* name) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;

    PROCESSENTRY32W pe{};
    pe.dwSize = sizeof(pe);
    DWORD pid = 0;

    if (Process32FirstW(snap, &pe)) {
        do {
            if (_wcsicmp(pe.szExeFile, name) == 0) {
                pid = pe.th32ProcessID;
                break;
            }
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return pid;
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 2) {
        std::wprintf(L"Usage: injector.exe <path-to-client.dll> [process.exe]\n");
        return 1;
    }

    const wchar_t* dllPath  = argv[1];
    const wchar_t* procName = (argc >= 3) ? argv[2] : L"javaw.exe";

    DWORD pid = FindProcess(procName);
    if (!pid) {
        std::wprintf(L"Process '%ls' not found.\n", procName);
        return 2;
    }

    HANDLE proc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!proc) {
        std::wprintf(L"OpenProcess failed: %lu\n", GetLastError());
        return 3;
    }

    SIZE_T pathLen = (wcslen(dllPath) + 1) * sizeof(wchar_t);
    LPVOID remote = VirtualAllocEx(proc, nullptr, pathLen,
                                   MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote) {
        CloseHandle(proc);
        return 4;
    }

    WriteProcessMemory(proc, remote, dllPath, pathLen, nullptr);

    HMODULE k32 = GetModuleHandleW(L"kernel32.dll");
    auto loadLib = (LPTHREAD_START_ROUTINE)GetProcAddress(k32, "LoadLibraryW");

    HANDLE th = CreateRemoteThread(proc, nullptr, 0, loadLib, remote, 0, nullptr);
    if (!th) {
        VirtualFreeEx(proc, remote, 0, MEM_RELEASE);
        CloseHandle(proc);
        return 5;
    }

    WaitForSingleObject(th, INFINITE);

    CloseHandle(th);
    VirtualFreeEx(proc, remote, 0, MEM_RELEASE);
    CloseHandle(proc);

    std::wprintf(L"Injected '%ls' into PID %lu.\n", dllPath, pid);
    return 0;
}
""")

# ---------------------------------------------------------------- README
w("README.md", r"""
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
""")

print("")
print("Project generated successfully.")
