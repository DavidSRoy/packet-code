import SwiftUI

// Packet brand primitives, from Packet Design Rules.png in the repo root.
// Emblem = four corner marks + red block, no name. Wordmark = Libre Franklin
// SemiBold (system semibold until the font file is added).
extension Color {
    static let packetRed = Color(red: 180 / 255, green: 67 / 255, blue: 47 / 255)
    static let packetBlack = Color(red: 17 / 255, green: 17 / 255, blue: 17 / 255)
    static let packetMustard = Color(red: 211 / 255, green: 161 / 255, blue: 63 / 255)

    private static func adaptive(light: Color, dark: Color) -> Color {
        Color(UIColor { traits in
            traits.userInterfaceStyle == .dark ? UIColor(dark) : UIColor(light)
        })
    }

    // Semantic tokens. Light mode is the white tile, dark mode the black tile.
    static let appBackground = adaptive(light: .white, dark: .packetBlack)
    static let headlineText = adaptive(light: .packetBlack, dark: .white)
    static let bodyText = adaptive(light: .packetBlack, dark: .white)
    static let buttonFill = adaptive(light: .packetBlack, dark: .white)
    static let buttonText = adaptive(light: .white, dark: .packetBlack)
}

// Four corner brackets with a red block in the middle.
struct PacketEmblemView: View {
    var markColor: Color
    var size: CGFloat = 120

    var body: some View {
        ZStack {
            Rectangle()
                .fill(Color.packetRed)
                .frame(width: size * 0.24, height: size * 0.2)
            BracketMarks(color: markColor, size: size)
        }
        .frame(width: size, height: size)
    }
}

private struct BracketMarks: View {
    var color: Color
    var size: CGFloat

    var body: some View {
        Canvas { context, canvasSize in
            let w = canvasSize.width
            let h = canvasSize.height
            let inset = size * 0.12
            let len = size * 0.28
            var path = Path()
            // Top-left
            path.move(to: CGPoint(x: inset + len, y: inset))
            path.addLine(to: CGPoint(x: inset, y: inset))
            path.addLine(to: CGPoint(x: inset, y: inset + len))
            // Top-right
            path.move(to: CGPoint(x: w - inset - len, y: inset))
            path.addLine(to: CGPoint(x: w - inset, y: inset))
            path.addLine(to: CGPoint(x: w - inset, y: inset + len))
            // Bottom-left
            path.move(to: CGPoint(x: inset, y: h - inset - len))
            path.addLine(to: CGPoint(x: inset, y: h - inset))
            path.addLine(to: CGPoint(x: inset + len, y: h - inset))
            // Bottom-right
            path.move(to: CGPoint(x: w - inset - len, y: h - inset))
            path.addLine(to: CGPoint(x: w - inset, y: h - inset))
            path.addLine(to: CGPoint(x: w - inset, y: h - inset - len))
            context.stroke(path, with: .color(color), lineWidth: max(2, size / 40))
        }
    }
}

struct PacketWordmarkView: View {
    var color: Color
    var size: CGFloat = 44

    var body: some View {
        Text("Packet")
            .font(PacketFonts.headline(size: size))
            .foregroundStyle(color)
    }
}
