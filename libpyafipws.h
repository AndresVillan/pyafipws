
#if defined(__GNUG__)

#define EXPORT extern "C" 
#define CONSTRUCTOR __attribute__((constructor))
#define DESTRUCTOR __attribute__((destructor))

#else

#include <windows.h>
#define EXPORT __declspec(dllexport) 
#define CONSTRUCTOR
#define DESTRUCTOR

BOOL WINAPI DllMain(HINSTANCE hInstance, DWORD dwReason, LPVOID lpReserved);

#define WIN32

#endif

EXPORT int test();
