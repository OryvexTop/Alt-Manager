
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
