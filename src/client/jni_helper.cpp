
#include "jni_helper.h"
#include <windows.h>
#include <cstring>
#include <string>

static JavaVM*        g_vm  = nullptr;
static thread_local JNIEnv* t_env = nullptr;

JavaVM* JNIHelper::vm()          { return g_vm; }
JNIEnv* JNIHelper::env()         { return t_env; }
bool    JNIHelper::is_attached() { return t_env != nullptr; }

bool JNIHelper::attach() {
    if (t_env) return true;

    if (!g_vm) {
        jsize count = 0;
        if (JNI_GetCreatedJavaVMs(&g_vm, 1, &count) != JNI_OK || count == 0) {
            g_vm = nullptr;
            return false;
        }
    }

    jint rc = g_vm->GetEnv(reinterpret_cast<void**>(&t_env), JNI_VERSION_1_8);
    if (rc == JNI_EDETACHED) {
        if (g_vm->AttachCurrentThread(reinterpret_cast<void**>(&t_env), nullptr) != JNI_OK) {
            t_env = nullptr;
            return false;
        }
    } else if (rc != JNI_OK) {
        t_env = nullptr;
        return false;
    }
    return true;
}

void JNIHelper::detach() {
    if (g_vm && t_env) {
        g_vm->DetachCurrentThread();
        t_env = nullptr;
    }
}

// ---------------------------------------------------------------- helpers

static jobjectArray call_getDeclaredFields(JNIEnv* e, jclass cls) {
    jclass ccls = e->FindClass("java/lang/Class");
    jmethodID m  = e->GetMethodID(ccls, "getDeclaredFields", "()[Ljava/lang/reflect/Field;");
    if (!m) return nullptr;
    return static_cast<jobjectArray>(e->CallObjectMethod(cls, m));
}

static std::string jstr(JNIEnv* e, jstring s) {
    if (!s) return {};
    const char* c = e->GetStringUTFChars(s, nullptr);
    std::string out = c ? c : "";
    e->ReleaseStringUTFChars(s, c);
    return out;
}

// ---------------------------------------------------------------- apply

bool JNIHelper::apply_account(const std::string& username,
                              const std::string& uuid,
                              const std::string& token) {
    if (!attach()) return false;
    JNIEnv* e = t_env;

    // 1) net.minecraft.client.Minecraft.getInstance()
    jclass mcClass = e->FindClass("net/minecraft/client/Minecraft");
    if (!mcClass) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jmethodID getInstance = e->GetStaticMethodID(
        mcClass, "getInstance", "()Lnet/minecraft/client/Minecraft;");
    if (!getInstance) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jobject mc = e->CallStaticObjectMethod(mcClass, getInstance);
    if (!mc) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    // 2) find the Session field on the Minecraft instance
    jclass mcInstCls   = e->GetObjectClass(mc);
    jclass classCls    = e->FindClass("java/lang/Class");
    jclass fieldCls    = e->FindClass("java/lang/reflect/Field");

    jmethodID fieldGet           = e->GetMethodID(fieldCls, "get", "(Ljava/lang/Object;)Ljava/lang/Object;");
    jmethodID fieldSet           = e->GetMethodID(fieldCls, "set", "(Ljava/lang/Object;Ljava/lang/Object;)V");
    jmethodID fieldSetAccessible = e->GetMethodID(fieldCls, "setAccessible", "(Z)V");
    jmethodID fieldGetType       = e->GetMethodID(fieldCls, "getType", "()Ljava/lang/Class;");
    jmethodID fieldGetName       = e->GetMethodID(fieldCls, "getName", "()Ljava/lang/String;");
    jmethodID classGetName       = e->GetMethodID(classCls, "getName", "()Ljava/lang/String;");

    jobjectArray mcFields = call_getDeclaredFields(e, mcInstCls);
    if (!mcFields) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jobject session = nullptr;
    jsize nf = e->GetArrayLength(mcFields);
    for (jsize i = 0; i < nf && !session; ++i) {
        jobject f = e->GetObjectArrayElement(mcFields, i);

        jclass ftype = static_cast<jclass>(e->CallObjectMethod(f, fieldGetType));
        std::string typeName = jstr(e, static_cast<jstring>(e->CallObjectMethod(ftype, classGetName)));

        if (typeName.find("Session") != std::string::npos) {
            e->CallVoidMethod(f, fieldSetAccessible, JNI_TRUE);
            session = e->CallObjectMethod(f, fieldGet, mc);
        }
    }
    if (!session) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    // 3) overwrite username / uuid / token on the Session instance
    jclass sessionCls = e->GetObjectClass(session);
    jobjectArray sFields = call_getDeclaredFields(e, sessionCls);
    if (!sFields) { if (e->ExceptionCheck()) e->ExceptionClear(); return false; }

    jsize nsf = e->GetArrayLength(sFields);
    for (jsize i = 0; i < nsf; ++i) {
        jobject f = e->GetObjectArrayElement(sFields, i);
        std::string name = jstr(e, static_cast<jstring>(e->CallObjectMethod(f, fieldGetName)));

        std::string value;
        if      ((name == "username")   && !username.empty()) value = username;
        else if ((name == "uuid" || name == "playerUUID") && !uuid.empty()) value = uuid;
        else if ((name == "token" || name == "accessToken" || name == "sessionToken")
                 && !token.empty()) value = token;

        if (!value.empty()) {
            e->CallVoidMethod(f, fieldSetAccessible, JNI_TRUE);
            jstring jval = e->NewStringUTF(value.c_str());
            e->CallVoidMethod(f, fieldSet, session, jval);
            e->DeleteLocalRef(jval);
        }
        e->DeleteLocalRef(f);
    }
    return true;
}
