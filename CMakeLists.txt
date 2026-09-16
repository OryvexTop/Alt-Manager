cmake_minimum_required(VERSION 3.20)
project(AltManager LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 11)

# ============================================================
#  FetchContent
# ============================================================
include(FetchContent)

# ---------- MinHook ----------
set(MINHOOK_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(MINHOOK_BUILD_TESTS    OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    minhook
    GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
    GIT_TAG        v1.3.3
)
FetchContent_MakeAvailable(minhook)

# ---------- ImGui ----------
# ریپوی ImGui خودش CMakeLists.txt ندارد، پس فقط دانلود می‌شود
# و ما خودمان یک تارگت می‌سازیم.
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG        v1.91.5
    SOURCE_SUBDIR  _no_cmake_here   # باعث می‌شود add_subdirectory صدا زده نشود
)
FetchContent_MakeAvailable(imgui)

add_library(imgui STATIC
    "${imgui_SOURCE_DIR}/imgui.cpp"
    "${imgui_SOURCE_DIR}/imgui_draw.cpp"
    "${imgui_SOURCE_DIR}/imgui_tables.cpp"
    "${imgui_SOURCE_DIR}/imgui_widgets.cpp"
    "${imgui_SOURCE_DIR}/backends/imgui_impl_win32.cpp"
    "${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp"
)

target_include_directories(imgui PUBLIC
    "${imgui_SOURCE_DIR}"
    "${imgui_SOURCE_DIR}/backends"
)

# ============================================================
#  System deps
# ============================================================
find_package(JNI REQUIRED)
find_package(OpenGL REQUIRED)

# ============================================================
#  client.dll
# ============================================================
add_library(client SHARED
    src/client/accounts.cpp
    src/client/jni_helper.cpp
    src/client/gui.cpp
    src/client/hooks.cpp
    src/client/client.cpp
)

target_include_directories(client PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src/client"
    "${minhook_SOURCE_DIR}/include"        # <-- مهم: مسیر MinHook.h
    ${JNI_INCLUDE_DIRS}
)

target_link_libraries(client PRIVATE
    minhook
    imgui
    ${JNI_LIBRARIES}
    opengl32
)

set_target_properties(client PROPERTIES
    PREFIX ""
    OUTPUT_NAME "client"
)

# ============================================================
#  injector.exe
# ============================================================
add_executable(injector
    src/injector/injector.cpp
)

set_target_properties(injector PROPERTIES
    OUTPUT_NAME "injector"
)
