#define UNICODE
#define _UNICODE

#include <windows.h>

#include <algorithm>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "AccessBridgePackages.h"

using WindowsRunFn = void (*)();
using IsJavaWindowFn = BOOL (*)(HWND);
using GetContextWithFocusFn = BOOL (*)(HWND, long*, AccessibleContext*);
using GetContextInfoFn = BOOL (*)(
    long, AccessibleContext, AccessibleContextInfo*
);
using GetTopLevelObjectFn = AccessibleContext (*)(long, AccessibleContext);
using GetParentFn = AccessibleContext (*)(long, AccessibleContext);
using GetChildFn = AccessibleContext (*)(long, AccessibleContext, jint);
using ReleaseObjectFn = void (*)(long, Java_Object);

struct Bridge {
    HMODULE module = nullptr;
    WindowsRunFn windows_run = nullptr;
    IsJavaWindowFn is_java_window = nullptr;
    GetContextWithFocusFn get_focus = nullptr;
    GetContextInfoFn get_info = nullptr;
    GetTopLevelObjectFn get_top_level = nullptr;
    GetParentFn get_parent = nullptr;
    GetChildFn get_child = nullptr;
    ReleaseObjectFn release_object = nullptr;
};

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
    return reinterpret_cast<Function>(GetProcAddress(module, name));
}

struct WindowSearch {
    Bridge* bridge = nullptr;
    std::wstring title_fragment;
    std::vector<HWND> matches;
};

static BOOL CALLBACK enum_windows(HWND hwnd, LPARAM parameter) {
    auto* search = reinterpret_cast<WindowSearch*>(parameter);
    if (!IsWindowVisible(hwnd) || !search->bridge->is_java_window(hwnd)) {
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

struct WalkState {
    Bridge* bridge = nullptr;
    long vm_id = 0;
    int max_depth = 20;
    int max_nodes = 1000;
    int nodes_seen = 0;
    bool first = true;
};

static void walk(
    WalkState* state,
    AccessibleContext context,
    int depth
) {
    if (
        context == 0
        || depth > state->max_depth
        || state->nodes_seen >= state->max_nodes
    ) {
        return;
    }

    AccessibleContextInfo info{};
    if (!state->bridge->get_info(state->vm_id, context, &info)) {
        return;
    }

    if (!state->first) {
        std::cout << ",\n";
    }
    state->first = false;
    ++state->nodes_seen;

    std::cout
        << "  {"
        << "\"depth\":" << depth << ","
        << "\"name\":\"" << json_escape(utf8(info.name)) << "\","
        << "\"description\":\""
        << json_escape(utf8(info.description)) << "\","
        << "\"role\":\"" << json_escape(utf8(info.role_en_US)) << "\","
        << "\"states\":\""
        << json_escape(utf8(info.states_en_US)) << "\","
        << "\"x\":" << info.x << ","
        << "\"y\":" << info.y << ","
        << "\"width\":" << info.width << ","
        << "\"height\":" << info.height << ","
        << "\"children\":" << info.childrenCount
        << "}";

    const int child_count = std::max(
        0,
        static_cast<int>(info.childrenCount)
    );
    for (
        int index = 0;
        index < child_count
        && state->nodes_seen < state->max_nodes;
        ++index
    ) {
        const AccessibleContext child =
            state->bridge->get_child(state->vm_id, context, index);
        if (child == 0) {
            continue;
        }
        walk(state, child, depth + 1);
        state->bridge->release_object(state->vm_id, child);
    }
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 3) {
        std::wcerr
            << L"Usage: jab_focus_tree.exe WINDOWS_ACCESS_BRIDGE_DLL "
            << L"TITLE_FRAGMENT [MAX_DEPTH] [MAX_NODES]\n";
        return 2;
    }

    Bridge bridge;
    bridge.module = LoadLibraryW(argv[1]);
    if (!bridge.module) {
        std::wcerr << L"Could not load bridge DLL.\n";
        return 3;
    }

    bridge.windows_run =
        load_symbol<WindowsRunFn>(bridge.module, "Windows_run");
    bridge.is_java_window =
        load_symbol<IsJavaWindowFn>(bridge.module, "isJavaWindow");
    bridge.get_focus =
        load_symbol<GetContextWithFocusFn>(
            bridge.module,
            "getAccessibleContextWithFocus"
        );
    bridge.get_info =
        load_symbol<GetContextInfoFn>(
            bridge.module,
            "getAccessibleContextInfo"
        );
    bridge.get_top_level =
        load_symbol<GetTopLevelObjectFn>(
            bridge.module,
            "getTopLevelObject"
        );
    bridge.get_parent =
        load_symbol<GetParentFn>(
            bridge.module,
            "getAccessibleParentFromContext"
        );
    bridge.get_child =
        load_symbol<GetChildFn>(
            bridge.module,
            "getAccessibleChildFromContext"
        );
    bridge.release_object =
        load_symbol<ReleaseObjectFn>(
            bridge.module,
            "releaseJavaObject"
        );

    if (
        !bridge.windows_run
        || !bridge.is_java_window
        || !bridge.get_focus
        || !bridge.get_info
        || !bridge.get_child
        || !bridge.release_object
    ) {
        std::cerr << "One or more bridge symbols are missing.\n";
        FreeLibrary(bridge.module);
        return 4;
    }

    bridge.windows_run();
    pump_messages(500);

    WindowSearch search;
    search.bridge = &bridge;
    search.title_fragment = argv[2];
    EnumWindows(enum_windows, reinterpret_cast<LPARAM>(&search));
    if (search.matches.empty()) {
        std::wcerr << L"No matching Java window found.\n";
        FreeLibrary(bridge.module);
        return 5;
    }

    long vm_id = 0;
    AccessibleContext focused = 0;
    for (HWND candidate : search.matches) {
        long candidate_vm_id = 0;
        AccessibleContext candidate_focused = 0;
        if (
            bridge.get_focus(
                candidate,
                &candidate_vm_id,
                &candidate_focused
            )
            && candidate_focused != 0
        ) {
            vm_id = candidate_vm_id;
            focused = candidate_focused;
            break;
        }
    }
    if (focused == 0) {
        std::cerr << "Could not obtain focused context.\n";
        FreeLibrary(bridge.module);
        return 6;
    }

    AccessibleContext root = 0;
    if (bridge.get_top_level) {
        root = bridge.get_top_level(vm_id, focused);
    }
    if (root == 0 && bridge.get_parent) {
        root = focused;
        while (true) {
            const AccessibleContext parent =
                bridge.get_parent(vm_id, root);
            if (parent == 0) {
                break;
            }
            if (root != focused) {
                bridge.release_object(vm_id, root);
            }
            root = parent;
        }
    }
    if (root == 0) {
        root = focused;
    }

    WalkState state;
    state.bridge = &bridge;
    state.vm_id = vm_id;
    if (argc >= 4) {
        state.max_depth = std::max(0, _wtoi(argv[3]));
    }
    if (argc >= 5) {
        state.max_nodes = std::max(1, _wtoi(argv[4]));
    }

    std::cout << "{\n\"nodes\":[\n";
    walk(&state, root, 0);
    std::cout
        << "\n],\n\"node_count\":" << state.nodes_seen << "\n}\n";

    if (root != focused) {
        bridge.release_object(vm_id, root);
    }
    bridge.release_object(vm_id, focused);
    pump_messages(50);
    FreeLibrary(bridge.module);
    return 0;
}
