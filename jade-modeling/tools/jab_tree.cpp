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
using GetContextFromHwndFn = BOOL (*)(HWND, long*, AccessibleContext*);
using GetContextInfoFn = BOOL (*)(long, AccessibleContext, AccessibleContextInfo*);
using GetChildFn = AccessibleContext (*)(long, AccessibleContext, jint);
using ReleaseObjectFn = void (*)(long, Java_Object);
using GetTextInfoFn = BOOL (*)(
    long, AccessibleText, AccessibleTextInfo*, jint, jint
);
using GetTextRangeFn = BOOL (*)(
    long, AccessibleText, jint, jint, wchar_t*, short
);
using GetTableInfoFn = BOOL (*)(
    long, AccessibleContext, AccessibleTableInfo*
);
using GetTableCellInfoFn = BOOL (*)(
    long, AccessibleTable, jint, jint, AccessibleTableCellInfo*
);
using GetKeyBindingsFn = BOOL (*)(
    long, AccessibleContext, AccessibleKeyBindings*
);
using GetActionsFn = BOOL (*)(
    long, AccessibleContext, AccessibleActions*
);

struct Bridge {
    HMODULE module = nullptr;
    WindowsRunFn windows_run = nullptr;
    IsJavaWindowFn is_java_window = nullptr;
    GetContextFromHwndFn get_context_from_hwnd = nullptr;
    GetContextInfoFn get_context_info = nullptr;
    GetChildFn get_child = nullptr;
    ReleaseObjectFn release_object = nullptr;
    GetTextInfoFn get_text_info = nullptr;
    GetTextRangeFn get_text_range = nullptr;
    GetTableInfoFn get_table_info = nullptr;
    GetTableCellInfoFn get_table_cell_info = nullptr;
    GetKeyBindingsFn get_key_bindings = nullptr;
    GetActionsFn get_actions = nullptr;
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
                    output << "\\u00" << hex[(ch >> 4) & 0xf] << hex[ch & 0xf];
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
    int max_depth = 40;
    int max_nodes = 50000;
    int nodes_seen = 0;
    bool first = true;
    bool include_text = false;
};

static void print_descendants_json(
    Bridge* bridge,
    long vm_id,
    AccessibleContext parent,
    int depth,
    int max_depth,
    int& count,
    int max_count,
    bool& first
) {
    if (depth > max_depth || count >= max_count) {
        return;
    }
    AccessibleContextInfo parent_info{};
    if (!bridge->get_context_info(vm_id, parent, &parent_info)) {
        return;
    }
    const int child_count = std::max(
        0,
        static_cast<int>(parent_info.childrenCount)
    );
    for (
        int index = 0;
        index < child_count && count < max_count;
        ++index
    ) {
        const AccessibleContext child =
            bridge->get_child(vm_id, parent, index);
        if (child == 0) {
            continue;
        }
        AccessibleContextInfo info{};
        if (bridge->get_context_info(vm_id, child, &info)) {
            if (!first) {
                std::cout << ",";
            }
            first = false;
            ++count;
            std::cout
                << "{"
                << "\"depth\":" << depth << ","
                << "\"index\":" << index << ","
                << "\"name\":\"" << json_escape(utf8(info.name)) << "\","
                << "\"description\":\"" << json_escape(utf8(info.description)) << "\","
                << "\"role\":\"" << json_escape(utf8(info.role_en_US)) << "\","
                << "\"states\":\"" << json_escape(utf8(info.states_en_US)) << "\","
                << "\"x\":" << info.x << ","
                << "\"y\":" << info.y << ","
                << "\"width\":" << info.width << ","
                << "\"height\":" << info.height
                << "}";
            print_descendants_json(
                bridge,
                vm_id,
                child,
                depth + 1,
                max_depth,
                count,
                max_count,
                first
            );
        }
        bridge->release_object(vm_id, child);
    }
}

static void print_context(
    WalkState& state,
    AccessibleContext context,
    int depth,
    int sibling_index
) {
    if (
        context == 0
        || depth > state.max_depth
        || state.nodes_seen >= state.max_nodes
    ) {
        return;
    }

    AccessibleContextInfo info{};
    if (!state.bridge->get_context_info(state.vm_id, context, &info)) {
        return;
    }

    std::string text_content;
    if (
        state.include_text
        && info.accessibleText
        && state.bridge->get_text_info
        && state.bridge->get_text_range
    ) {
        AccessibleTextInfo text_info{};
        if (
            state.bridge->get_text_info(
                state.vm_id,
                static_cast<AccessibleText>(context),
                &text_info,
                info.x,
                info.y
            )
            && text_info.charCount > 0
        ) {
            const int bounded_count = std::min(
                static_cast<int>(text_info.charCount),
                32000
            );
            std::vector<wchar_t> buffer(
                static_cast<size_t>(bounded_count) + 1,
                L'\0'
            );
            if (
                state.bridge->get_text_range(
                    state.vm_id,
                    static_cast<AccessibleText>(context),
                    0,
                    bounded_count - 1,
                    buffer.data(),
                    static_cast<short>(buffer.size())
                )
            ) {
                text_content = utf8(buffer.data());
            }
        }
    }

    AccessibleTableInfo table_info{};
    const bool has_table = (
        (info.accessibleInterfaces & cAccessibleTableInterface) != 0
        && state.bridge->get_table_info
        && state.bridge->get_table_cell_info
        && state.bridge->get_table_info(
            state.vm_id,
            context,
            &table_info
        )
    );
    AccessibleKeyBindings key_bindings{};
    const bool has_key_bindings = (
        state.bridge->get_key_bindings
        && state.bridge->get_key_bindings(
            state.vm_id,
            context,
            &key_bindings
        )
        && key_bindings.keyBindingsCount > 0
    );
    AccessibleActions actions{};
    const bool has_actions = (
        state.bridge->get_actions
        && state.bridge->get_actions(
            state.vm_id,
            context,
            &actions
        )
        && actions.actionsCount > 0
    );

    if (!state.first) {
        std::cout << ",\n";
    }
    state.first = false;
    ++state.nodes_seen;

    std::cout
        << "  {"
        << "\"depth\":" << depth << ","
        << "\"sibling_index\":" << sibling_index << ","
        << "\"name\":\"" << json_escape(utf8(info.name)) << "\","
        << "\"description\":\"" << json_escape(utf8(info.description)) << "\","
        << "\"role\":\"" << json_escape(utf8(info.role_en_US)) << "\","
        << "\"role_local\":\"" << json_escape(utf8(info.role)) << "\","
        << "\"states\":\"" << json_escape(utf8(info.states_en_US)) << "\","
        << "\"x\":" << info.x << ","
        << "\"y\":" << info.y << ","
        << "\"width\":" << info.width << ","
        << "\"height\":" << info.height << ","
        << "\"children\":" << info.childrenCount << ","
        << "\"accessible_action\":" << (info.accessibleAction ? "true" : "false") << ","
        << "\"accessible_selection\":" << (info.accessibleSelection ? "true" : "false") << ","
        << "\"accessible_text\":" << (info.accessibleText ? "true" : "false") << ","
        << "\"text_content\":\"" << json_escape(text_content) << "\","
        << "\"table_row_count\":" << (has_table ? table_info.rowCount : 0) << ","
        << "\"table_column_count\":" << (has_table ? table_info.columnCount : 0) << ","
        << "\"key_bindings\":[";

    if (has_key_bindings) {
        const int key_count = std::max(
            0,
            std::min(
                key_bindings.keyBindingsCount,
                static_cast<int>(MAX_KEY_BINDINGS)
            )
        );
        for (int key_index = 0; key_index < key_count; ++key_index) {
            if (key_index > 0) {
                std::cout << ",";
            }
            const auto& binding =
                key_bindings.keyBindingInfo[key_index];
            std::cout
                << "{"
                << "\"character\":"
                << static_cast<unsigned int>(binding.character)
                << ","
                << "\"modifiers\":" << binding.modifiers
                << "}";
        }
    }

    std::cout << "],\"actions\":[";

    if (has_actions) {
        const int action_count = std::max(
            0,
            std::min(
                static_cast<int>(actions.actionsCount),
                static_cast<int>(MAX_ACTION_INFO)
            )
        );
        for (int action_index = 0; action_index < action_count; ++action_index) {
            if (action_index > 0) {
                std::cout << ",";
            }
            std::cout
                << "\""
                << json_escape(utf8(actions.actionInfo[action_index].name))
                << "\"";
        }
    }

    std::cout << "],\"table_cells\":[";

    if (has_table) {
        bool first_cell = true;
        const int row_count = std::max(
            0,
            std::min(static_cast<int>(table_info.rowCount), 5000)
        );
        const int column_count = std::max(
            0,
            std::min(static_cast<int>(table_info.columnCount), 64)
        );
        for (int row = 0; row < row_count; ++row) {
            for (int column = 0; column < column_count; ++column) {
                AccessibleTableCellInfo cell_info{};
                if (
                    !state.bridge->get_table_cell_info(
                        state.vm_id,
                        table_info.accessibleTable,
                        row,
                        column,
                        &cell_info
                    )
                    || cell_info.accessibleContext == 0
                ) {
                    continue;
                }

                AccessibleContextInfo cell_context_info{};
                const bool has_cell_context = state.bridge->get_context_info(
                    state.vm_id,
                    static_cast<AccessibleContext>(
                        cell_info.accessibleContext
                    ),
                    &cell_context_info
                );
                if (has_cell_context) {
                    if (!first_cell) {
                        std::cout << ",";
                    }
                    first_cell = false;
                    std::cout
                        << "{"
                        << "\"row\":" << row << ","
                        << "\"column\":" << column << ","
                        << "\"index\":" << cell_info.index << ","
                        << "\"selected\":" << (cell_info.isSelected ? "true" : "false") << ","
                        << "\"name\":\"" << json_escape(utf8(cell_context_info.name)) << "\","
                        << "\"description\":\"" << json_escape(utf8(cell_context_info.description)) << "\","
                        << "\"role\":\"" << json_escape(utf8(cell_context_info.role_en_US)) << "\","
                        << "\"states\":\"" << json_escape(utf8(cell_context_info.states_en_US)) << "\","
                        << "\"x\":" << cell_context_info.x << ","
                        << "\"y\":" << cell_context_info.y << ","
                        << "\"width\":" << cell_context_info.width << ","
                        << "\"height\":" << cell_context_info.height << ","
                        << "\"children\":[";
                    int descendant_count = 0;
                    bool first_descendant = true;
                    print_descendants_json(
                        state.bridge,
                        state.vm_id,
                        static_cast<AccessibleContext>(
                            cell_info.accessibleContext
                        ),
                        1,
                        6,
                        descendant_count,
                        200,
                        first_descendant
                    );
                    std::cout << "]}";
                }
                state.bridge->release_object(
                    state.vm_id,
                    cell_info.accessibleContext
                );
            }
        }
    }

    std::cout << "]}";

    const int child_count =
        std::max(0, static_cast<int>(info.childrenCount));
    for (int index = 0; index < child_count; ++index) {
        const AccessibleContext child =
            state.bridge->get_child(state.vm_id, context, index);
        if (child == 0) {
            continue;
        }
        print_context(state, child, depth + 1, index);
        state.bridge->release_object(state.vm_id, child);
        if (state.nodes_seen >= state.max_nodes) {
            break;
        }
    }
}

template <typename Function>
static Function load_symbol(HMODULE module, const char* name) {
    return reinterpret_cast<Function>(GetProcAddress(module, name));
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 3) {
        std::wcerr
            << L"Usage: jab_tree.exe WINDOWS_ACCESS_BRIDGE_DLL TITLE_FRAGMENT "
            << L"[MAX_DEPTH] [MAX_NODES] [INCLUDE_TEXT]\n";
        return 2;
    }

    Bridge bridge;
    bridge.module = LoadLibraryW(argv[1]);
    if (!bridge.module) {
        std::wcerr << L"Could not load bridge DLL: " << argv[1] << L"\n";
        return 3;
    }

    bridge.windows_run =
        load_symbol<WindowsRunFn>(bridge.module, "Windows_run");
    bridge.is_java_window =
        load_symbol<IsJavaWindowFn>(bridge.module, "isJavaWindow");
    bridge.get_context_from_hwnd =
        load_symbol<GetContextFromHwndFn>(
            bridge.module, "getAccessibleContextFromHWND"
        );
    bridge.get_context_info =
        load_symbol<GetContextInfoFn>(
            bridge.module, "getAccessibleContextInfo"
        );
    bridge.get_child =
        load_symbol<GetChildFn>(
            bridge.module, "getAccessibleChildFromContext"
        );
    bridge.release_object =
        load_symbol<ReleaseObjectFn>(bridge.module, "releaseJavaObject");
    bridge.get_text_info =
        load_symbol<GetTextInfoFn>(bridge.module, "getAccessibleTextInfo");
    bridge.get_text_range =
        load_symbol<GetTextRangeFn>(bridge.module, "getAccessibleTextRange");
    bridge.get_table_info =
        load_symbol<GetTableInfoFn>(
            bridge.module, "getAccessibleTableInfo"
        );
    bridge.get_table_cell_info =
        load_symbol<GetTableCellInfoFn>(
            bridge.module, "getAccessibleTableCellInfo"
        );
    bridge.get_key_bindings =
        load_symbol<GetKeyBindingsFn>(
            bridge.module, "getAccessibleKeyBindings"
        );
    bridge.get_actions =
        load_symbol<GetActionsFn>(
            bridge.module, "getAccessibleActions"
        );

    if (
        !bridge.windows_run
        || !bridge.is_java_window
        || !bridge.get_context_from_hwnd
        || !bridge.get_context_info
        || !bridge.get_child
        || !bridge.release_object
        || !bridge.get_text_info
        || !bridge.get_text_range
        || !bridge.get_table_info
        || !bridge.get_table_cell_info
        || !bridge.get_key_bindings
        || !bridge.get_actions
    ) {
        std::cerr << "One or more Java Access Bridge symbols are missing.\n";
        FreeLibrary(bridge.module);
        return 4;
    }

    bridge.windows_run();
    pump_messages(1500);

    WindowSearch search;
    search.bridge = &bridge;
    search.title_fragment = argv[2];
    EnumWindows(enum_windows, reinterpret_cast<LPARAM>(&search));
    if (search.matches.empty()) {
        std::wcerr << L"No matching Java window found for: " << argv[2] << L"\n";
        FreeLibrary(bridge.module);
        return 5;
    }

    const int max_depth = argc >= 4 ? std::max(1, _wtoi(argv[3])) : 40;
    const int max_nodes = argc >= 5 ? std::max(1, _wtoi(argv[4])) : 50000;
    const bool include_text = argc >= 6 && _wtoi(argv[5]) != 0;
    HWND hwnd = search.matches.front();
    long vm_id = 0;
    AccessibleContext root = 0;
    if (!bridge.get_context_from_hwnd(hwnd, &vm_id, &root) || root == 0) {
        std::cerr << "Could not obtain the root accessible context.\n";
        FreeLibrary(bridge.module);
        return 6;
    }

    wchar_t title_buffer[2048]{};
    GetWindowTextW(hwnd, title_buffer, 2048);
    RECT rectangle{};
    GetWindowRect(hwnd, &rectangle);

    std::cout
        << "{\n"
        << "\"window_title\":\"" << json_escape(utf8(title_buffer)) << "\",\n"
        << "\"hwnd\":" << reinterpret_cast<uintptr_t>(hwnd) << ",\n"
        << "\"vm_id\":" << vm_id << ",\n"
        << "\"window_rect\":{"
        << "\"left\":" << rectangle.left << ","
        << "\"top\":" << rectangle.top << ","
        << "\"right\":" << rectangle.right << ","
        << "\"bottom\":" << rectangle.bottom
        << "},\n"
        << "\"nodes\":[\n";

    WalkState state;
    state.bridge = &bridge;
    state.vm_id = vm_id;
    state.max_depth = max_depth;
    state.max_nodes = max_nodes;
    state.include_text = include_text;
    print_context(state, root, 0, 0);

    std::cout
        << "\n],\n"
        << "\"node_count\":" << state.nodes_seen << "\n"
        << "}\n";

    bridge.release_object(vm_id, root);
    pump_messages(100);
    FreeLibrary(bridge.module);
    return 0;
}
