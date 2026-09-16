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
