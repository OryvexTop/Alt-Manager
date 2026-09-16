# create_account.py — generates the whole project structure
import pathlib

ROOT = pathlib.Path(__file__).parent

FILES = {}

FILES[".gitignore"] = r"""
build/
*.user
.vs/
__pycache__/
"""
FILES["CMakeLists.txt"] = r"""
cmake_minimum_required(VERSION 3.20)
project(AltManager LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 11)

include(FetchContent)

# ============================================================
#  ImGui — سورس خام دانلود می‌شود (CMakeLists خودش اجرا نمی‌شود)
# ============================================================
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

# ============================================================
#  MinHook — فقط سورس‌ها دانلود می‌شوند، CMakeLists اجرا نمی‌شود
# ============================================================
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

# ============================================================
#  System deps
# ============================================================
find_package(JNI REQUIRED)
find_package(OpenGL REQUIRED)

# ============================================================
#  client.dll  — MinHook مستقیم داخلش کامپایل می‌شود
# ============================================================
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

# ============================================================
#  injector.exe
# ============================================================
add_executable(injector src/injector/injector.cpp)
set_target_properties(injector PROPERTIES OUTPUT_NAME "injector")
"""

# ---------------- CLIENT ----------------

FILES["src/client/accounts.h"] = r"""
#pragma once
#include <string>
#include <vector>

namespace accounts {
    std::vector<std::string>& Get();
    int GetCurrentIndex();
    void SetCurrent(int idx);
    void Add(const std::string& name);
    void Remove(int idx);
    void Load();
    void Save();
}
"""

FILES["src/client/accounts.cpp"] = r"""
#include "accounts.h"
#include <Windows.h>
#include <ShlObj.h>
#include <fstream>

namespace accounts {
    static std::vector<std::string> s_list;
    static int s_current = -1;
    static std::string s_path;

    static std::string Path() {
        char buf[MAX_PATH] = {};
        SHGetFolderPathA(nullptr, CSIDL_APPDATA, nullptr, 0, buf);
        std::string dir = std::string(buf) + "\\.mc-account-switcher";
        CreateDirectoryA(dir.c_str(), nullptr);
        return dir + "\\accounts.txt";
    }

    void Load() {
        s_path = Path();
        s_list.clear();
        s_current = -1;
        std::ifstream f(s_path);
        std::string line;
        while (std::getline(f, line)) {
            if (line.empty()) continue;
            if (line[0] == '*') { s_current = (int)s_list.size(); line = line.substr(1); }
            s_list.push_back(line);
        }
        if (s_current < 0 && !s_list.empty()) s_current = 0;
    }

    void Save() {
        if (s_path.empty()) s_path = Path();
        std::ofstream f(s_path, std::ios::trunc);
        for (size_t i = 0; i < s_list.size(); i++) {
            if ((int)i == s_current) f << "*";
            f << s_list[i] << "\n";
        }
    }

    std::vector<std::string>& Get() { if (s_path.empty()) Load(); return s_list; }
    int  GetCurrentIndex() { if (s_path.empty()) Load(); return s_current; }
    void SetCurrent(int i) { if (i >= 0 && i < (int)s_list.size()) { s_current = i; Save(); } }
    void Add(const std::string& n) { s_list.push_back(n); if (s_current < 0) s_current = 0; Save(); }
    void Remove(int i) {
        if (i < 0 || i >= (int)s_list.size()) return;
        s_list.erase(s_list.begin() + i);
        if (s_current >= (int)s_list.size()) s_current = (int)s_list.size() - 1;
        Save();
    }
}
"""

FILES["src/client/jni_helper.h"] = r"""
#pragma once
#include <string>
namespace jni_helper {
    bool SwitchAccount(const std::string& username);
}
"""

FILES["src/client/jni_helper.cpp"] = r"""
#include "jni_helper.h"
#include <Windows.h>
#include <jvmti.h>
#include <jni.h>
#include <string>
#include <vector>

namespace jni_helper {

static JavaVM*  g_jvm   = nullptr;
static jvmtiEnv* g_jvmti = nullptr;

static bool Init() {
    if (g_jvm) return true;
    HMODULE h = GetModuleHandleA("jvm.dll");
    if (!h) return false;
    typedef jint (JNICALL *GetVMs_t)(JavaVM**, jsize, jsize*);
    auto fn = (GetVMs_t)GetProcAddress(h, "JNI_GetCreatedJavaVMs");
    if (!fn) return false;
    jsize n = 0;
    if (fn(&g_jvm, 1, &n) != JNI_OK || n == 0) return false;
    if (g_jvm->GetEnv((void**)&g_jvmti, JVMTI_VERSION_1_2) != JNI_OK) return false;
    jvmtiCapabilities caps = {};
    caps.can_tag_objects = 1;
    g_jvmti->AddCapabilities(&caps);
    return true;
}

struct Klass { jclass k; std::string sig; };

static std::vector<Klass> LoadClasses() {
    std::vector<Klass> out;
    jint n = 0; jclass* arr = nullptr;
    if (g_jvmti->GetLoadedClasses(&n, &arr) != JVMTI_ERROR_NONE) return out;
    for (int i = 0; i < n; i++) {
        char* s = nullptr;
        if (g_jvmti->GetClassSignature(arr[i], &s, nullptr) == JVMTI_ERROR_NONE && s) {
            out.push_back({ arr[i], s });
            g_jvmti->Deallocate((unsigned char*)s);
        }
    }
    g_jvmti->Deallocate((unsigned char*)arr);
    return out;
}

static bool HasFieldOfType(jclass k, const std::string& typeSig) {
    jint n = 0; jfieldID* f = nullptr;
    if (g_jvmti->GetClassFields(k, &n, &f) != JVMTI_ERROR_NONE) return false;
    bool found = false;
    for (int i = 0; i < n && !found; i++) {
        char *name, *sig;
        if (g_jvmti->GetFieldName(k, f[i], &name, &sig, nullptr) == JVMTI_ERROR_NONE) {
            if (typeSig == sig) found = true;
            g_jvmti->Deallocate((unsigned char*)name);
            g_jvmti->Deallocate((unsigned char*)sig);
        }
    }
    g_jvmti->Deallocate((unsigned char*)f);
    return found;
}

// Session class: has a GameProfile field (authlib not obfuscated).
static std::string FindSession(const std::vector<Klass>& ks) {
    for (auto& c : ks) {
        if (c.sig.size() < 4 || c.sig[0] != 'L') continue;
        if (c.sig.rfind("Ljava/", 0) == 0) continue;
        if (c.sig.rfind("Ljavax/", 0) == 0) continue;
        if (c.sig.rfind("Lsun/", 0) == 0) continue;
        if (HasFieldOfType(c.k, "Lcom/mojang/authlib/GameProfile;"))
            return c.sig;
    }
    return "";
}

// Minecraft class: has a field of Session type + a static self-typed field.
static std::string FindMinecraft(const std::vector<Klass>& ks, const std::string& sessionSig) {
    for (auto& c : ks) {
        if (c.sig.size() < 4 || c.sig[0] != 'L') continue;
        if (!HasFieldOfType(c.k, sessionSig)) continue;
        // check for static self field
        jint n = 0; jfieldID* f = nullptr;
        if (g_jvmti->GetClassFields(c.k, &n, &f) != JVMTI_ERROR_NONE) continue;
        bool selfStatic = false;
        for (int i = 0; i < n; i++) {
            char *name, *sig; jint mods;
            if (g_jvmti->GetFieldName(c.k, f[i], &name, &sig, nullptr) == JVMTI_ERROR_NONE) {
                g_jvmti->GetFieldModifiers(c.k, f[i], &mods);
                if ((mods & 0x0008) && c.sig == sig) selfStatic = true;
                g_jvmti->Deallocate((unsigned char*)name);
                g_jvmti->Deallocate((unsigned char*)sig);
            }
        }
        g_jvmti->Deallocate((unsigned char*)f);
        if (selfStatic) return c.sig;
    }
    return "";
}

static jobject GetSingleton(JNIEnv* env, jclass k, const std::string& sig) {
    jint n = 0; jfieldID* f = nullptr;
    if (g_jvmti->GetClassFields(k, &n, &f) != JVMTI_ERROR_NONE) return nullptr;
    jobject r = nullptr;
    for (int i = 0; i < n && !r; i++) {
        char *name, *fsig; jint mods;
        if (g_jvmti->GetFieldName(k, f[i], &name, &fsig, nullptr) == JVMTI_ERROR_NONE) {
            g_jvmti->GetFieldModifiers(k, f[i], &mods);
            if ((mods & 0x0008) && sig == fsig)
                r = env->GetStaticObjectField(k, f[i]);
            g_jvmti->Deallocate((unsigned char*)name);
            g_jvmti->Deallocate((unsigned char*)fsig);
        }
    }
    g_jvmti->Deallocate((unsigned char*)f);
    return r;
}

static jfieldID GetFieldBySig(JNIEnv*, jclass k, const std::string& sig) {
    jint n = 0; jfieldID* f = nullptr;
    if (g_jvmti->GetClassFields(k, &n, &f) != JVMTI_ERROR_NONE) return nullptr;
    jfieldID r = nullptr;
    for (int i = 0; i < n && !r; i++) {
        char *name, *fsig;
        if (g_jvmti->GetFieldName(k, f[i], &name, &fsig, nullptr) == JVMTI_ERROR_NONE) {
            if (sig == fsig) r = f[i];
            g_jvmti->Deallocate((unsigned char*)name);
            g_jvmti->Deallocate((unsigned char*)fsig);
        }
    }
    g_jvmti->Deallocate((unsigned char*)f);
    return r;
}

bool SwitchAccount(const std::string& username) {
    if (!Init()) return false;
    JNIEnv* env = nullptr;
    bool attached = false;
    if (g_jvm->GetEnv((void**)&env, JNI_VERSION_1_8) != JNI_OK) {
        if (g_jvm->AttachCurrentThread((void**)&env, nullptr) != JNI_OK) return false;
        attached = true;
    }

    auto ks = LoadClasses();
    std::string sessionSig = FindSession(ks);
    if (sessionSig.empty()) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    std::string mcSig = FindMinecraft(ks, sessionSig);
    if (mcSig.empty()) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    jclass sessionClass = nullptr, mcClass = nullptr;
    for (auto& c : ks) {
        if (c.sig == sessionSig) sessionClass = c.k;
        if (c.sig == mcSig)      mcClass      = c.k;
    }
    if (!sessionClass || !mcClass) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    jobject mcInstance = GetSingleton(env, mcClass, mcSig);
    if (!mcInstance) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    jfieldID sessionField = GetFieldBySig(env, mcClass, sessionSig);
    if (!sessionField) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    // Offline UUID: UUID.nameUUIDFromBytes(("OfflinePlayer:"+name).getBytes())
    jclass uuidClass = env->FindClass("java/util/UUID");
    jmethodID nameUUID = env->GetStaticMethodID(uuidClass, "nameUUIDFromBytes", "([B)Ljava/util/UUID;");
    std::string seed = "OfflinePlayer:" + username;
    jbyteArray bytes = env->NewByteArray((jsize)seed.size());
    env->SetByteArrayRegion(bytes, 0, (jsize)seed.size(), (const jbyte*)seed.data());
    jobject uuid = env->CallStaticObjectMethod(uuidClass, nameUUID, bytes);

    jstring jname  = env->NewStringUTF(username.c_str());
    jstring jtoken = env->NewStringUTF("0");

    jobject newSession = nullptr;

    // Modern ctor: (String, UUID, String, Optional)
    jmethodID c1 = env->GetMethodID(sessionClass, "<init>",
        "(Ljava/lang/String;Ljava/util/UUID;Ljava/lang/String;Ljava/util/Optional;)V");
    if (c1) {
        jclass opt = env->FindClass("java/util/Optional");
        jmethodID empty = env->GetStaticMethodID(opt, "empty", "()Ljava/util/Optional;");
        jobject e = env->CallStaticObjectMethod(opt, empty);
        newSession = env->NewObject(sessionClass, c1, jname, uuid, jtoken, e);
    }

    // Legacy ctor: (String, String, String, String)
    if (!newSession) {
        env->ExceptionClear();
        jmethodID c2 = env->GetMethodID(sessionClass, "<init>",
            "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V");
        if (c2) {
            jmethodID toString = env->GetMethodID(uuidClass, "toString", "()Ljava/lang/String;");
            jstring us = (jstring)env->CallObjectMethod(uuid, toString);
            jstring t  = env->NewStringUTF("legacy");
            newSession = env->NewObject(sessionClass, c2, jname, us, jtoken, t);
        }
    }

    if (!newSession || env->ExceptionCheck()) {
        env->ExceptionClear();
        if (attached) g_jvm->DetachCurrentThread();
        return false;
    }

    env->SetObjectField(mcInstance, sessionField, newSession);
    if (env->ExceptionCheck()) {
        env->ExceptionClear();
        if (attached) g_jvm->DetachCurrentThread();
        return false;
    }

    if (attached) g_jvm->DetachCurrentThread();
    return true;
}

} // namespace jni_helper
"""

FILES["src/client/gui.h"] = r"""
#pragma once
namespace gui { void Render(); }
"""

FILES["src/client/gui.cpp"] = r"""
#include "gui.h"
#include "accounts.h"
#include "jni_helper.h"
#include <imgui.h>
#include <string>
#include <vector>

namespace gui {

static char s_new[64] = "";

void Render() {
    ImGui::SetNextWindowSize(ImVec2(430, 340), ImGuiCond_FirstUseEver);
    ImGui::Begin("Minecraft Offline Account Switcher", nullptr, ImGuiWindowFlags_NoCollapse);

    ImGui::TextColored(ImVec4(0.6f, 0.8f, 1.0f, 1.0f), "Press [UP ARROW] to open/close");
    ImGui::Separator();

    auto& list = accounts::Get();
    int cur = accounts::GetCurrentIndex();

    ImGui::Text("Accounts (%d):", (int)list.size());
    ImGui::BeginChild("##list", ImVec2(0, 180), true);
    for (int i = 0; i < (int)list.size(); i++) {
        bool sel = (i == cur);
        std::string label = list[i] + (sel ? "   [active]" : "");
        if (ImGui::Selectable(label.c_str(), sel)) {
            accounts::SetCurrent(i);
            bool ok = jni_helper::SwitchAccount(list[i]);
            (void)ok;
        }
        if (ImGui::BeginPopupContextItem()) {
            if (ImGui::MenuItem("Delete")) {
                accounts::Remove(i);
                ImGui::EndPopup();
                break;
            }
            ImGui::EndPopup();
        }
    }
    ImGui::EndChild();

    ImGui::InputText("Username", s_new, sizeof(s_new));
    if (ImGui::Button("Add") && s_new[0]) {
        accounts::Add(s_new);
        s_new[0] = 0;
    }
    ImGui::SameLine();
    if (ImGui::Button("Switch now")) {
        if (cur >= 0 && cur < (int)list.size())
            jni_helper::SwitchAccount(list[cur]);
    }
    ImGui::SameLine();
    if (ImGui::Button("Reload"))
        accounts::Load();

    ImGui::End();
}

}
"""

FILES["src/client/hooks.h"] = r"""
#pragma once
#include <Windows.h>
namespace hooks { void Init(HWND hwnd); }
"""

FILES["src/client/hooks.cpp"] = r"""
#include "hooks.h"
#include "gui.h"
#include <Windows.h>
#include <MinHook.h>
#include <imgui.h>
#include <imgui_impl_win32.h>
#include <imgui_impl_opengl3.h>

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND, UINT, WPARAM, LPARAM);

namespace hooks {

static HWND        g_hwnd      = nullptr;
static WNDPROC     g_wndproc   = nullptr;
static bool        g_imguiInit = false;
static bool        g_visible   = false;

typedef BOOL(WINAPI* SwapBuffers_t)(HDC);
static SwapBuffers_t g_origSwap = nullptr;

LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_KEYDOWN && (wp == VK_UP || wp == VK_NUMPAD8)) {
        g_visible = !g_visible;
    }
    if (g_visible) {
        ImGui_ImplWin32_WndProcHandler(h, msg, wp, lp);
        switch (msg) {
            case WM_LBUTTONDOWN: case WM_LBUTTONUP:
            case WM_RBUTTONDOWN: case WM_RBUTTONUP:
            case WM_MBUTTONDOWN: case WM_MBUTTONUP:
            case WM_MOUSEMOVE:
            case WM_MOUSEWHEEL:
            case WM_KEYDOWN: case WM_KEYUP: case WM_CHAR:
            case WM_SYSKEYDOWN: case WM_SYSKEYUP:
                return 0;
        }
    }
    return CallWindowProc(g_wndproc, h, msg, wp, lp);
}

BOOL WINAPI hk_SwapBuffers(HDC hdc) {
    if (!g_imguiInit) {
        IMGUI_CHECKVERSION();
        ImGui::CreateContext();
        ImGuiIO& io = ImGui::GetIO();
        io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
        io.IniFilename = nullptr;
        ImGui::StyleColorsDark();
        ImGui_ImplWin32_Init(g_hwnd);
        ImGui_ImplOpenGL3_Init("#version 150");
        g_imguiInit = true;
    }

    if (g_visible) {
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplWin32_NewFrame();
        ImGui::NewFrame();
        gui::Render();
        ImGui::Render();
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
    }
    return g_origSwap(hdc);
}

void Init(HWND hwnd) {
    g_hwnd = hwnd;
    g_wndproc = (WNDPROC)SetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)WndProc);

    MH_Initialize();

    // GLFW uses SwapBuffers(hdc) — hook from gdi32 first, fallback to wglSwapBuffers.
    void* target = (void*)GetProcAddress(GetModuleHandleA("gdi32.dll"), "SwapBuffers");
    if (!target) target = (void*)GetProcAddress(GetModuleHandleA("opengl32.dll"), "wglSwapBuffers");

    if (target) {
        MH_CreateHook(target, &hk_SwapBuffers, (void**)&g_origSwap);
        MH_EnableHook(target);
    }
}

}
"""

FILES["src/client/client.cpp"] = r"""
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
"""

# ---------------- INJECTOR ----------------

FILES["src/injector/injector.cpp"] = r"""
#include <Windows.h>
#include <TlHelp32.h>
#include <filesystem>
#include <string>
#include <cstdio>

static DWORD FindProcess(const wchar_t* name) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;
    PROCESSENTRY32W pe{}; pe.dwSize = sizeof(pe);
    DWORD pid = 0;
    if (Process32FirstW(snap, &pe)) {
        do {
            if (_wcsicmp(pe.szExeFile, name) == 0) { pid = pe.th32ProcessID; break; }
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return pid;
}

static bool Inject(DWORD pid, const std::wstring& dll) {
    HANDLE proc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!proc) return false;

    SIZE_T size = (dll.size() + 1) * sizeof(wchar_t);
    LPVOID remote = VirtualAllocEx(proc, nullptr, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote) { CloseHandle(proc); return false; }

    WriteProcessMemory(proc, remote, dll.c_str(), size, nullptr);

    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    auto loadLib = (LPTHREAD_START_ROUTINE)GetProcAddress(k32, "LoadLibraryW");

    HANDLE th = CreateRemoteThread(proc, nullptr, 0, loadLib, remote, 0, nullptr);
    if (!th) { VirtualFreeEx(proc, remote, 0, MEM_RELEASE); CloseHandle(proc); return false; }

    WaitForSingleObject(th, 10000);
    CloseHandle(th);
    VirtualFreeEx(proc, remote, 0, MEM_RELEASE);
    CloseHandle(proc);
    return true;
}

int wmain(int argc, wchar_t** argv) {
    std::wstring dll;
    if (argc >= 2) dll = argv[1];
    else {
        wchar_t buf[MAX_PATH] = {};
        GetModuleFileNameW(nullptr, buf, MAX_PATH);
        dll = (std::filesystem::path(buf).parent_path() / L"client.dll").wstring();
    }

    if (GetFileAttributesW(dll.c_str()) == INVALID_FILE_ATTRIBUTES) {
        wprintf(L"[!] client.dll not found at: %s\n", dll.c_str());
        return 1;
    }

    wprintf(L"[*] Waiting for javaw.exe / java.exe...\n");
    DWORD pid = 0;
    while (!pid) {
        pid = FindProcess(L"javaw.exe");
        if (!pid) pid = FindProcess(L"java.exe");
        if (!pid) Sleep(1000);
    }

    wprintf(L"[*] Found process PID %lu. Injecting %s...\n", pid, dll.c_str());
    if (!Inject(pid, dll)) {
        wprintf(L"[!] Injection failed. Try running as Administrator.\n");
        return 1;
    }
    wprintf(L"[+] Injected successfully. Press the UP ARROW in-game to open the UI.\n");
    return 0;
}
"""

# ---------------- README ----------------

FILES["README.md"] = r"""
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
"""

def main():
    for rel, content in FILES.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.lstrip("\n"), encoding="utf-8")
        print(f"[+] {rel}")
    print("\nProject generated successfully.")

if __name__ == "__main__":
    main()