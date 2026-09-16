cmake_minimum_required(VERSION 3.18)
project(MinecraftAccountSwitcher CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

include(FetchContent)

# ---- ImGui ----
FetchContent_Declare(imgui
  GIT_REPOSITORY https://github.com/ocornut/imgui.git
  GIT_TAG v1.90.4)
FetchContent_MakeAvailable(imgui)

# ---- MinHook ----
FetchContent_Declare(minhook
  GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
  GIT_TAG v1.3.3)
FetchContent_MakeAvailable(minhook)

set(MINHOOK_SRC
  ${minhook_SOURCE_DIR}/src/buffer.c
  ${minhook_SOURCE_DIR}/src/hook.c
  ${minhook_SOURCE_DIR}/src/trampoline.c
  ${minhook_SOURCE_DIR}/src/hde/hde64.c)
add_library(minhook STATIC ${MINHOOK_SRC})
target_include_directories(minhook PUBLIC ${minhook_SOURCE_DIR}/include)

# ---- JNI ----
find_package(JNI REQUIRED)

# ---- OpenGL ----
find_package(OpenGL REQUIRED)

set(IMGUI_SOURCES
  ${imgui_SOURCE_DIR}/imgui.cpp
  ${imgui_SOURCE_DIR}/imgui_draw.cpp
  ${imgui_SOURCE_DIR}/imgui_tables.cpp
  ${imgui_SOURCE_DIR}/imgui_widgets.cpp
  ${imgui_SOURCE_DIR}/backends/imgui_impl_win32.cpp
  ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp)

# ---- client.dll ----
add_library(client SHARED
  src/client/client.cpp
  src/client/hooks.cpp
  src/client/gui.cpp
  src/client/accounts.cpp
  src/client/jni_helper.cpp
  ${IMGUI_SOURCES})

target_include_directories(client PRIVATE
  ${imgui_SOURCE_DIR}
  ${imgui_SOURCE_DIR}/backends
  ${JNI_INCLUDE_DIRS})

target_link_libraries(client PRIVATE minhook OpenGL::GL ${JNI_LIBRARIES})

set_target_properties(client PROPERTIES OUTPUT_NAME "client" PREFIX "")

# ---- injector.exe ----
add_executable(injector src/injector/injector.cpp)
target_compile_definitions(injector PRIVATE UNICODE _UNICODE)
set_target_properties(injector PROPERTIES OUTPUT_NAME "injector")
