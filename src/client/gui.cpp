
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
