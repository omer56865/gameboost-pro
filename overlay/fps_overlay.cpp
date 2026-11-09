/*
GameBoost Pro - FPS Overlay (DirectX 11/12 Present Hook)
Derleme: cl /O2 /LD fps_overlay.cpp /link d3d11.lib dxgi.lib user32.lib
Çıktı  : fps_overlay.dll  (Python ctypes ile yüklenir)
*/
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <dxgi1_4.h>
#include <stdint.h>
#include <stdio.h>

// ---- Basit vtable hook ----
typedef HRESULT(WINAPI* PFN_Present)(IDXGISwapChain*, UINT, UINT);
static PFN_Present  g_OrigPresent  = nullptr;
static IDXGISwapChain* g_SwapChain = nullptr;

// ---- FPS ölçüm ----
static LARGE_INTEGER g_Freq  = {};
static LARGE_INTEGER g_Last  = {};
static uint32_t      g_Frame = 0;
static float         g_FPS   = 0.0f;
static float         g_Low1  = 0.0f;
static float         g_Frame_ms = 0.0f;
static float         g_FrameBuf[256] = {};
static int           g_BufIdx = 0;

static void UpdateFPS() {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    if (g_Last.QuadPart == 0) { g_Last = now; return; }

    double ms = (double)(now.QuadPart - g_Last.QuadPart)
                / (double)g_Freq.QuadPart * 1000.0;
    g_Last = now;
    g_Frame_ms = (float)ms;
    g_Frame++;

    // Kayan pencere ortalama (256 kare)
    g_FrameBuf[g_BufIdx % 256] = (float)ms;
    g_BufIdx++;

    int n = min(g_BufIdx, 256);
    float sum = 0.0f;
    float worst = 0.0f;
    for (int i = 0; i < n; i++) {
        sum += g_FrameBuf[i];
        if (g_FrameBuf[i] > worst) worst = g_FrameBuf[i];
    }
    float avg_ms = sum / n;
    g_FPS       = avg_ms > 0.0f ? 1000.0f / avg_ms : 0.0f;

    // %1 Low: en uzun kare süresi (yaklaşık)
    int p1 = max(1, n / 100);
    float sorted[256];
    memcpy(sorted, g_FrameBuf, n * sizeof(float));
    // Basit kısmi seçme sıralaması (sadece p1 eleman)
    for (int i = 0; i < p1; i++) {
        int maxIdx = i;
        for (int j = i + 1; j < n; j++)
            if (sorted[j] > sorted[maxIdx]) maxIdx = j;
        float tmp = sorted[i]; sorted[i] = sorted[maxIdx]; sorted[maxIdx] = tmp;
    }
    float low_ms = 0.0f;
    for (int i = 0; i < p1; i++) low_ms += sorted[i];
    low_ms /= p1;
    g_Low1 = low_ms > 0.0f ? 1000.0f / low_ms : 0.0f;
}

// ---- Sahte Present (hook) ----
static HRESULT WINAPI HookedPresent(IDXGISwapChain* chain, UINT SyncInterval, UINT Flags) {
    UpdateFPS();
    return g_OrigPresent(chain, SyncInterval, Flags);
}

// ---- vtable yama ----
static bool PatchVTable(void** vtable, int idx, void* newFn, void** oldFn) {
    DWORD old;
    if (!VirtualProtect(&vtable[idx], sizeof(void*), PAGE_READWRITE, &old)) return false;
    *oldFn = vtable[idx];
    vtable[idx] = newFn;
    VirtualProtect(&vtable[idx], sizeof(void*), old, &old);
    return true;
}

// ======================= Dışa Aktarılan API =======================
extern "C" {

__declspec(dllexport)
int GB_Init() {
    if (g_SwapChain) return 1; // zaten başlatıldı

    QueryPerformanceFrequency(&g_Freq);

    // Geçici bir DXGI SwapChain oluşturarak vtable adresini al
    HWND dummy = CreateWindowA("STATIC", "GB", WS_POPUP, 0, 0, 1, 1, NULL, NULL, NULL, NULL);
    if (!dummy) return -1;

    DXGI_SWAP_CHAIN_DESC desc = {};
    desc.BufferDesc.Format   = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.SampleDesc.Count    = 1;
    desc.BufferUsage         = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount         = 1;
    desc.OutputWindow        = dummy;
    desc.Windowed            = TRUE;
    desc.SwapEffect          = DXGI_SWAP_EFFECT_DISCARD;

    ID3D11Device*        dev = nullptr;
    IDXGISwapChain*      sc  = nullptr;
    ID3D11DeviceContext* ctx = nullptr;
    D3D_FEATURE_LEVEL    fl;

    HRESULT hr = D3D11CreateDeviceAndSwapChain(
        nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0,
        nullptr, 0, D3D11_SDK_VERSION,
        &desc, &sc, &dev, &fl, &ctx);

    DestroyWindow(dummy);
    if (FAILED(hr) || !sc) return -2;

    // vtable[8] = IDXGISwapChain::Present
    void** vtable = *(void***)sc;
    PatchVTable(vtable, 8, (void*)HookedPresent, (void**)&g_OrigPresent);

    g_SwapChain = sc;
    if (dev) dev->Release();
    if (ctx) ctx->Release();
    return 0;
}

__declspec(dllexport)
void GB_GetStats(float* fps, float* low1, float* frame_ms) {
    if (fps)      *fps      = g_FPS;
    if (low1)     *low1     = g_Low1;
    if (frame_ms) *frame_ms = g_Frame_ms;
}

__declspec(dllexport)
uint32_t GB_GetFrameCount() { return g_Frame; }

__declspec(dllexport)
void GB_Shutdown() {
    if (g_SwapChain && g_OrigPresent) {
        void** vtable = *(void***)g_SwapChain;
        DWORD old;
        VirtualProtect(&vtable[8], sizeof(void*), PAGE_READWRITE, &old);
        vtable[8] = (void*)g_OrigPresent;
        VirtualProtect(&vtable[8], sizeof(void*), old, &old);
        g_OrigPresent = nullptr;
    }
    if (g_SwapChain) { g_SwapChain->Release(); g_SwapChain = nullptr; }
}

} // extern "C"

BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_DETACH) GB_Shutdown();
    return TRUE;
}
