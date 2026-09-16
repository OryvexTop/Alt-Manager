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
