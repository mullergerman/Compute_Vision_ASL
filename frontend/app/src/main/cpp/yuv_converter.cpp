#include <jni.h>
#include <stdint.h>
#include <libyuv.h>
#include <memory>

extern "C" JNIEXPORT void JNICALL
Java_com_example_computevisionremote_MainActivity_yuv420ToNv21(
        JNIEnv* env,
        jobject /* this */,
        jobject yBuffer, jint yRowStride, jint yPixelStride,
        jobject uBuffer, jint uRowStride, jint uPixelStride,
        jobject vBuffer, jint vRowStride, jint vPixelStride,
        jint width, jint height,
        jobject nv21Buffer) {
    uint8_t* y = static_cast<uint8_t*>(env->GetDirectBufferAddress(yBuffer));
    uint8_t* u = static_cast<uint8_t*>(env->GetDirectBufferAddress(uBuffer));
    uint8_t* v = static_cast<uint8_t*>(env->GetDirectBufferAddress(vBuffer));
    uint8_t* nv21 = static_cast<uint8_t*>(env->GetDirectBufferAddress(nv21Buffer));
    if (!y || !u || !v || !nv21) {
        return;
    }

    size_t frameSize = width * height;
    size_t chromaSize = frameSize / 4;
    std::unique_ptr<uint8_t[]> tmpY(new uint8_t[frameSize]);
    std::unique_ptr<uint8_t[]> tmpU(new uint8_t[chromaSize]);
    std::unique_ptr<uint8_t[]> tmpV(new uint8_t[chromaSize]);

    libyuv::Android420ToI420(
            y, yRowStride,
            u, uRowStride,
            v, vRowStride,
            uPixelStride,
            tmpY.get(), width,
            tmpU.get(), width / 2,
            tmpV.get(), width / 2,
            width, height);

    libyuv::I420ToNV21(
            tmpY.get(), width,
            tmpU.get(), width / 2,
            tmpV.get(), width / 2,
            nv21, width,
            nv21 + frameSize, width,
            width, height);
}
