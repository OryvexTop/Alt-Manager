
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
