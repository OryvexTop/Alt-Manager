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
