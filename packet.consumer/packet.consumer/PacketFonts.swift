import SwiftUI
import CoreText

// Runtime font registration. The app generates its Info.plist, so fonts are
// registered from the bundle instead of UIAppFonts keys.
enum PacketFonts {
    static let headlineName = "LibreFranklinThin-SemiBold"
    static let bodyName = "AtkinsonHyperlegibleNext-Regular"
    static let bodyBoldName = "AtkinsonHyperlegibleNext-Bold"
    static let labelName = "BarlowCondensed-SemiBold"

    private static let files = [
        "LibreFranklin-SemiBold",
        "AtkinsonHyperlegibleNext-Regular",
        "AtkinsonHyperlegibleNext-Bold",
        "BarlowCondensed-SemiBold",
        "BarlowCondensed-Bold",
    ]

    static func register() {
        for file in files {
            guard let url = Bundle.main.url(forResource: file, withExtension: "ttf") else { continue }
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
    }

    private static func custom(_ name: String, size: CGFloat, fallback: Font) -> Font {
        UIFont(name: name, size: size) == nil
            ? fallback
            : Font.custom(name, size: size, relativeTo: .body)
    }

    // Rules: Headline Libre 600 30/33, Body Atkinson 17/24, Label Barlow
    // Condensed 600 13 caps +10% tracking.
    static func headline(size: CGFloat = 30) -> Font {
        custom(headlineName, size: size, fallback: .system(size: size, weight: .semibold))
    }

    static func body(size: CGFloat = 17) -> Font {
        custom(bodyName, size: size, fallback: .system(size: size))
    }

    static func label(size: CGFloat = 13) -> Font {
        custom(labelName, size: size, fallback: .system(size: size, weight: .semibold))
    }
}
