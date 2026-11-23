// SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <array>
#include <span>
#include <string_view>

#include "core/libraries/ime/ime_common.h"

namespace Libraries::Ime {

struct ImeKbLayoutModel;
struct ImeKbLayoutSelection;
struct ImeTopPanelLayoutConfig;

enum class ImeKbCurrencyProfile : u8 {
    Euro = 0,
    Dollar = 1,
    Pound = 2,
    Yen = 3,
    Won = 4,
    Automatic = 5,
};

struct ImeKbLanguageProfile {
    OrbisImeLanguage language = OrbisImeLanguage::ENGLISH_US;
    int console_language = 1;
    const char* space_label = "Space";
    const char* accents_label = "à";
    const char* letters_label = "ABC";
    const char* symbols_label = "@#:";
    std::array<const char*, 4> enter_labels{"Done", "Send", "Search", "Go"};
    std::u16string_view preferred_characters{};
    ImeKbCurrencyProfile currency = ImeKbCurrencyProfile::Automatic;
    u8 symbol_pages = 2;
    u8 special_pages = 2;
    // Return nullptr for modes that use the shared default tables.
    const ImeKbLayoutModel* (*layout_provider)(const ImeKbLayoutSelection&) = nullptr;
    const ImeTopPanelLayoutConfig* top_panel_layout = nullptr;
};

std::span<const ImeKbLanguageProfile> GetImeKeyboardLanguageProfiles();
const ImeKbLanguageProfile& GetImeKeyboardLanguageProfile(OrbisImeLanguage language);
OrbisImeLanguage ResolveImeKeyboardLanguage(OrbisImeLanguage supported_languages,
                                            int console_language);

} // namespace Libraries::Ime
