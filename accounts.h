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
