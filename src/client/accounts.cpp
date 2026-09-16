
#include "accounts.h"

AccountManager& AccountManager::instance() {
    static AccountManager inst;
    return inst;
}

void AccountManager::add(const Account& acc) {
    std::lock_guard<std::mutex> lock(mtx_);
    accounts_.push_back(acc);
    if (current_ < 0) current_ = 0;
}

bool AccountManager::remove(size_t index) {
    std::lock_guard<std::mutex> lock(mtx_);
    if (index >= accounts_.size()) return false;
    accounts_.erase(accounts_.begin() + index);
    if (accounts_.empty()) current_ = -1;
    else if (current_ >= (int)accounts_.size()) current_ = (int)accounts_.size() - 1;
    return true;
}

bool AccountManager::set_current(size_t index) {
    std::lock_guard<std::mutex> lock(mtx_);
    if (index >= accounts_.size()) return false;
    current_ = (int)index;
    return true;
}

Account AccountManager::current() const {
    std::lock_guard<std::mutex> lock(mtx_);
    if (current_ < 0 || current_ >= (int)accounts_.size()) return {};
    return accounts_[current_];
}

int AccountManager::current_index() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return current_;
}

bool AccountManager::has_current() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return current_ >= 0 && current_ < (int)accounts_.size();
}

std::vector<Account> AccountManager::list() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return accounts_;
}
