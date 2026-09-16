
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
