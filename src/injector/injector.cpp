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
