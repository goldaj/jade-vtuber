#define UNICODE
#define _UNICODE

#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "AccessBridgePackages.h"

using WindowsRunFn = void (*)();
using IsJavaWindowFn = BOOL (*)(HWND);
using GetContextWithFocusFn = BOOL (*)(
    HWND, long*, AccessibleContext*
);
using GetContextInfoFn = BOOL (*)(
    long, AccessibleContext, AccessibleContextInfo*
);
using ReleaseObjectFn = void (*)(long, Java_Object);

static std::string utf8(const wchar_t* value) {
    if (!value || !*value) {
        return {};
    }
    const int length = WideCharToMultiByte(
        CP_UTF8, 0, value, -1, nullptr, 0, nullptr, nullptr
    );
    if (length <= 1) {
        return {};
    }
    std::string result(static_cast<size_t>(length - 1), '\0');
    WideCharToMultiByte(
        CP_UTF8, 0, value, -1, &result[0], length, nullptr, nullptr
    );
    return result;
}

static std::string json_escape(const std::string& value) {
    std::ostringstream output;
    for (unsigned char ch : value) {
        switch (ch) {
            case '\\': output << "\\\\"; break;
            case '"': output << "\\\""; break;
            case '\b': output << "\\b"; break;
            case '\f': output << "\\f"; break;
            case '\n': output << "\\n"; break;
            case '\r': output << "\\r"; break;
            case '\t': output << "\\t"; break;
            default:
                if (ch < 0x20) {
                    const char* hex = "0123456789abcdef";
                    output
                        << "\\u00"
                        << hex[(ch >> 4) & 0xf]
                        << hex[ch & 0xf];
                } else {
                    output << static_cast<char>(ch);
                }
        }
    }
    return output.str();
}

static void pump_messages(DWORD duration_ms) {
    const DWORD end = GetTickCount() + duration_ms;
    MSG message{};
    do {
        while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
        Sleep(10);
    } while (static_cast<LONG>(GetTickCount() - end) < 0);
}

template <typename Function>
static Function load_symbol(HMODULE module, const char* name) {
    return reinterpret_cast<Function>(
        GetProcAddress(module, name)
    );
}

struct WindowSearch {
    IsJavaWindowFn is_java_window = nullptr;
    std::wstring title_fragment;
    std::vector<HWND> matches;
};

static BOOL CALLBACK enum_windows(HWND hwnd, LPARAM parameter) {
    auto* search = reinterpret_cast<WindowSearch*>(parameter);
    if (
        !IsWindowVisible(hwnd)
        || !search->is_java_window(hwnd)
    ) {
        return TRUE;
    }
    const int length = GetWindowTextLengthW(hwnd);
    std::wstring title(
        static_cast<size_t>(std::max(length, 0)) + 1,
        L'\0'
    );
    if (length > 0) {
        GetWindowTextW(hwnd, &title[0], length + 1);
    }
    if (
        search->title_fragment.empty()
        || title.find(search->title_fragment) != std::wstring::npos
    ) {
        search->matches.push_back(hwnd);
    }
    return TRUE;
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 3) {
        std::wcerr
            << L"Usage: jab_focus.exe WINDOWS_ACCESS_BRIDGE_DLL "
            << L"TITLE_FRAGMENT\n";
        return 2;
    }

    HMODULE module = LoadLibraryW(argv[1]);
    if (!module) {
        std::wcerr << L"Could not load bridge DLL.\n";
        return 3;
    }
    const auto windows_run =
        load_symbol<WindowsRunFn>(module, "Windows_run");
    const auto is_java_window =
        load_symbol<IsJavaWindowFn>(module, "isJavaWindow");
    const auto get_focus =
        load_symbol<GetContextWithFocusFn>(
            module,
            "getAccessibleContextWithFocus"
        );
    const auto get_info =
        load_symbol<GetContextInfoFn>(
            module,
            "getAccessibleContextInfo"
        );
    const auto release_object =
        load_symbol<ReleaseObjectFn>(
            module,
            "releaseJavaObject"
        );
    if (
        !windows_run
        || !is_java_window
        || !get_focus
        || !get_info
        || !release_object
    ) {
        std::cerr << "One or more bridge symbols are missing.\n";
        FreeLibrary(module);
        return 4;
    }

    windows_run();
    pump_messages(500);

    WindowSearch search;
    search.is_java_window = is_java_window;
    search.title_fragment = argv[2];
    EnumWindows(enum_windows, reinterpret_cast<LPARAM>(&search));
    if (search.matches.empty()) {
        std::wcerr << L"No matching Java window found.\n";
        FreeLibrary(module);
        return 5;
    }

    long vm_id = 0;
    AccessibleContext context = 0;
    if (
        !get_focus(search.matches.front(), &vm_id, &context)
        || context == 0
    ) {
        std::cerr << "Could not obtain focused context.\n";
        FreeLibrary(module);
        return 6;
    }

    AccessibleContextInfo info{};
    if (!get_info(vm_id, context, &info)) {
        release_object(vm_id, context);
        FreeLibrary(module);
        return 7;
    }
    std::cout
        << "{"
        << "\"name\":\"" << json_escape(utf8(info.name)) << "\","
        << "\"description\":\""
        << json_escape(utf8(info.description)) << "\","
        << "\"role\":\"" << json_escape(utf8(info.role_en_US))
        << "\","
        << "\"states\":\""
        << json_escape(utf8(info.states_en_US)) << "\","
        << "\"x\":" << info.x << ","
        << "\"y\":" << info.y << ","
        << "\"width\":" << info.width << ","
        << "\"height\":" << info.height
        << "}\n";

    release_object(vm_id, context);
    pump_messages(50);
    FreeLibrary(module);
    return 0;
}
