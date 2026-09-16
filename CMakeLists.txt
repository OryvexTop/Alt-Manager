cmake_minimum_required(VERSION 3.20)

# ============================================================
#  نکته حیاتی: زبان C باید فعال باشد (MinHook با C نوشته شده)
# ============================================================
project(AltManager LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 11)

# ============================================================
#  MinHook — دانلود خودکار با FetchContent
# ============================================================
include(FetchContent)

set(MINHOOK_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(MINHOOK_BUILD_TESTS    OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    minhook
    GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
    GIT_TAG        v1.3.3
)
FetchContent_MakeAvailable(minhook)

# ============================================================
#  Dependencies
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
    ${JNI_INCLUDE_DIRS}
)

target_link_libraries(client PRIVATE
    minhook
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
