
#pragma once
#include <jni.h>
#include <string>

class JNIHelper {
public:
    static bool attach();
    static void detach();
    static bool is_attached();
    static JavaVM* vm();
    static JNIEnv* env();

    // Reaches into the running Minecraft JVM and overwrites the live
    // Session's username / uuid / token fields via reflection.
    static bool apply_account(const std::string& username,
                              const std::string& uuid,
                              const std::string& token);
};
