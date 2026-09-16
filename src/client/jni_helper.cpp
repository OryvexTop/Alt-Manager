#include "jni_helper.h"
#include <Windows.h>
#include <jvmti.h>
#include <jni.h>
#include <string>
#include <vector>

namespace jni_helper {

static JavaVM*  g_jvm   = nullptr;
static jvmtiEnv* g_jvmti = nullptr;

static bool Init() {
    if (g_jvm) return true;
    HMODULE h = GetModuleHandleA("jvm.dll");
    if (!h) return false;
    typedef jint (JNICALL *GetVMs_t)(JavaVM**, jsize, jsize*);
    auto fn = (GetVMs_t)GetProcAddress(h, "JNI_GetCreatedJavaVMs");
    if (!fn) return false;
    jsize n = 0;
    if (fn(&g_jvm, 1, &n) != JNI_OK || n == 0) return false;
    if (g_jvm->GetEnv((void**)&g_jvmti, JVMTI_VERSION_1_2) != JNI_OK) return false;
    jvmtiCapabilities caps = {};
    caps.can_tag_objects = 1;
    g_jvmti->AddCapabilities(&caps);
    return true;
}

struct Klass { jclass k; std::string sig; };

static std::vector<Klass> LoadClasses() {
    std::vector<Klass> out;
    jint n = 0; jclass* arr = nullptr;
    if (g_jvmti->GetLoadedClasses(&n, &arr) != JVMTI_ERROR_NONE) return out;
    for (int i = 0; i < n; i++) {
        char* s = nullptr;
        if (g_jvmti->GetClassSignature(arr[i], &s, nullptr) == JVMTI_ERROR_NONE && s) {
            out.push_back({ arr[i], s });
            g_jvmti->Deallocate((unsigned char*)s);
        }
    }
    g_jvmti->Deallocate((unsigned char*)arr);
    return out;
}

static bool HasFieldOfType(jclass k, const std::string& typeSig) {
    jint n = 0; jfieldID* f = nullptr;
    if (g_jvmti->GetClassFields(k, &n, &f) != JVMTI_ERROR_NONE) return false;
    bool found = false;
    for (int i = 0; i < n && !found; i++) {
        char *name, *sig;
        if (g_jvmti->GetFieldName(k, f[i], &name, &sig, nullptr) == JVMTI_ERROR_NONE) {
            if (typeSig == sig) found = true;
            g_jvmti->Deallocate((unsigned char*)name);
            g_jvmti->Deallocate((unsigned char*)sig);
        }
    }
    g_jvmti->Deallocate((unsigned char*)f);
    return found;
}

// Session class: has a GameProfile field (authlib not obfuscated).
static std::string FindSession(const std::vector<Klass>& ks) {
    for (auto& c : ks) {
        if (c.sig.size() < 4 || c.sig[0] != 'L') continue;
        if (c.sig.rfind("Ljava/", 0) == 0) continue;
        if (c.sig.rfind("Ljavax/", 0) == 0) continue;
        if (c.sig.rfind("Lsun/", 0) == 0) continue;
        if (HasFieldOfType(c.k, "Lcom/mojang/authlib/GameProfile;"))
            return c.sig;
    }
    return "";
}

// Minecraft class: has a field of Session type + a static self-typed field.
static std::string FindMinecraft(const std::vector<Klass>& ks, const std::string& sessionSig) {
    for (auto& c : ks) {
        if (c.sig.size() < 4 || c.sig[0] != 'L') continue;
        if (!HasFieldOfType(c.k, sessionSig)) continue;
        // check for static self field
        jint n = 0; jfieldID* f = nullptr;
        if (g_jvmti->GetClassFields(c.k, &n, &f) != JVMTI_ERROR_NONE) continue;
        bool selfStatic = false;
        for (int i = 0; i < n; i++) {
            char *name, *sig; jint mods;
            if (g_jvmti->GetFieldName(c.k, f[i], &name, &sig, nullptr) == JVMTI_ERROR_NONE) {
                g_jvmti->GetFieldModifiers(c.k, f[i], &mods);
                if ((mods & 0x0008) && c.sig == sig) selfStatic = true;
                g_jvmti->Deallocate((unsigned char*)name);
                g_jvmti->Deallocate((unsigned char*)sig);
            }
        }
        g_jvmti->Deallocate((unsigned char*)f);
        if (selfStatic) return c.sig;
    }
    return "";
}

static jobject GetSingleton(JNIEnv* env, jclass k, const std::string& sig) {
    jint n = 0; jfieldID* f = nullptr;
    if (g_jvmti->GetClassFields(k, &n, &f) != JVMTI_ERROR_NONE) return nullptr;
    jobject r = nullptr;
    for (int i = 0; i < n && !r; i++) {
        char *name, *fsig; jint mods;
        if (g_jvmti->GetFieldName(k, f[i], &name, &fsig, nullptr) == JVMTI_ERROR_NONE) {
            g_jvmti->GetFieldModifiers(k, f[i], &mods);
            if ((mods & 0x0008) && sig == fsig)
                r = env->GetStaticObjectField(k, f[i]);
            g_jvmti->Deallocate((unsigned char*)name);
            g_jvmti->Deallocate((unsigned char*)fsig);
        }
    }
    g_jvmti->Deallocate((unsigned char*)f);
    return r;
}

static jfieldID GetFieldBySig(JNIEnv*, jclass k, const std::string& sig) {
    jint n = 0; jfieldID* f = nullptr;
    if (g_jvmti->GetClassFields(k, &n, &f) != JVMTI_ERROR_NONE) return nullptr;
    jfieldID r = nullptr;
    for (int i = 0; i < n && !r; i++) {
        char *name, *fsig;
        if (g_jvmti->GetFieldName(k, f[i], &name, &fsig, nullptr) == JVMTI_ERROR_NONE) {
            if (sig == fsig) r = f[i];
            g_jvmti->Deallocate((unsigned char*)name);
            g_jvmti->Deallocate((unsigned char*)fsig);
        }
    }
    g_jvmti->Deallocate((unsigned char*)f);
    return r;
}

bool SwitchAccount(const std::string& username) {
    if (!Init()) return false;
    JNIEnv* env = nullptr;
    bool attached = false;
    if (g_jvm->GetEnv((void**)&env, JNI_VERSION_1_8) != JNI_OK) {
        if (g_jvm->AttachCurrentThread((void**)&env, nullptr) != JNI_OK) return false;
        attached = true;
    }

    auto ks = LoadClasses();
    std::string sessionSig = FindSession(ks);
    if (sessionSig.empty()) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    std::string mcSig = FindMinecraft(ks, sessionSig);
    if (mcSig.empty()) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    jclass sessionClass = nullptr, mcClass = nullptr;
    for (auto& c : ks) {
        if (c.sig == sessionSig) sessionClass = c.k;
        if (c.sig == mcSig)      mcClass      = c.k;
    }
    if (!sessionClass || !mcClass) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    jobject mcInstance = GetSingleton(env, mcClass, mcSig);
    if (!mcInstance) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    jfieldID sessionField = GetFieldBySig(env, mcClass, sessionSig);
    if (!sessionField) { if (attached) g_jvm->DetachCurrentThread(); return false; }

    // Offline UUID: UUID.nameUUIDFromBytes(("OfflinePlayer:"+name).getBytes())
    jclass uuidClass = env->FindClass("java/util/UUID");
    jmethodID nameUUID = env->GetStaticMethodID(uuidClass, "nameUUIDFromBytes", "([B)Ljava/util/UUID;");
    std::string seed = "OfflinePlayer:" + username;
    jbyteArray bytes = env->NewByteArray((jsize)seed.size());
    env->SetByteArrayRegion(bytes, 0, (jsize)seed.size(), (const jbyte*)seed.data());
    jobject uuid = env->CallStaticObjectMethod(uuidClass, nameUUID, bytes);

    jstring jname  = env->NewStringUTF(username.c_str());
    jstring jtoken = env->NewStringUTF("0");

    jobject newSession = nullptr;

    // Modern ctor: (String, UUID, String, Optional)
    jmethodID c1 = env->GetMethodID(sessionClass, "<init>",
        "(Ljava/lang/String;Ljava/util/UUID;Ljava/lang/String;Ljava/util/Optional;)V");
    if (c1) {
        jclass opt = env->FindClass("java/util/Optional");
        jmethodID empty = env->GetStaticMethodID(opt, "empty", "()Ljava/util/Optional;");
        jobject e = env->CallStaticObjectMethod(opt, empty);
        newSession = env->NewObject(sessionClass, c1, jname, uuid, jtoken, e);
    }

    // Legacy ctor: (String, String, String, String)
    if (!newSession) {
        env->ExceptionClear();
        jmethodID c2 = env->GetMethodID(sessionClass, "<init>",
            "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V");
        if (c2) {
            jmethodID toString = env->GetMethodID(uuidClass, "toString", "()Ljava/lang/String;");
            jstring us = (jstring)env->CallObjectMethod(uuid, toString);
            jstring t  = env->NewStringUTF("legacy");
            newSession = env->NewObject(sessionClass, c2, jname, us, jtoken, t);
        }
    }

    if (!newSession || env->ExceptionCheck()) {
        env->ExceptionClear();
        if (attached) g_jvm->DetachCurrentThread();
        return false;
    }

    env->SetObjectField(mcInstance, sessionField, newSession);
    if (env->ExceptionCheck()) {
        env->ExceptionClear();
        if (attached) g_jvm->DetachCurrentThread();
        return false;
    }

    if (attached) g_jvm->DetachCurrentThread();
    return true;
}

} // namespace jni_helper
