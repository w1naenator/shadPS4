// SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "core/libraries/ime/ime_kb_language.h"

#include <algorithm>

namespace Libraries::Ime {
namespace {

constexpr std::array<ImeKbLanguageProfile, 3> kLanguageProfiles = {{
    {},
    {
        .language = OrbisImeLanguage::ENGLISH_GB,
        .console_language = 18,
        .currency = ImeKbCurrencyProfile::Pound,
    },
    {
        .language = OrbisImeLanguage::POLISH,
        .console_language = 16,
        .space_label = "Spacja",
        .accents_label = "ą",
        .enter_labels = {"Gotowe", "Wyślij", "Wyszukaj", "Przejdź"},
        .preferred_characters = u"ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
        .currency = ImeKbCurrencyProfile::Euro,
        .special_pages = 1,
    },
}};

} // namespace

std::span<const ImeKbLanguageProfile> GetImeKeyboardLanguageProfiles() {
    return kLanguageProfiles;
}

const ImeKbLanguageProfile& GetImeKeyboardLanguageProfile(OrbisImeLanguage language) {
    const auto profile =
        std::ranges::find(kLanguageProfiles, language, &ImeKbLanguageProfile::language);
    return profile != kLanguageProfiles.end() ? *profile : kLanguageProfiles.front();
}

OrbisImeLanguage ResolveImeKeyboardLanguage(OrbisImeLanguage supported_languages,
                                            int console_language) {
    const auto allowed = [&](const ImeKbLanguageProfile& profile) {
        return static_cast<u64>(supported_languages) == 0 ||
               True(supported_languages & profile.language);
    };
    const auto configured = std::ranges::find(kLanguageProfiles, console_language,
                                              &ImeKbLanguageProfile::console_language);
    if (configured != kLanguageProfiles.end() && allowed(*configured)) {
        return configured->language;
    }
    const auto supported = std::ranges::find_if(kLanguageProfiles, allowed);
    return supported != kLanguageProfiles.end() ? supported->language
                                                : kLanguageProfiles.front().language;
}

} // namespace Libraries::Ime
