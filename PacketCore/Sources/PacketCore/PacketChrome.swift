import SwiftUI

// Shared Packet chrome, from Packet Design Rules.png.
// Band: 8pt bar under the status bar. Leading lines run from the text margin
// off the right edge. One primary button and one mustard tag per screen.

// 8pt status band, full width.
struct PacketBand: View {
    var body: some View {
        Color.buttonFill
            .frame(height: 8)
            .frame(maxWidth: .infinity)
    }
}

// Leading lines: red / mustard / headline stripes from the margin off the
// right edge.
struct PacketLeadingLines: View {
    var body: some View {
        VStack(spacing: 4) {
            Color.packetRed.frame(height: 4)
            Color.packetMustard.frame(height: 4)
            Color.headlineText.frame(height: 4)
        }
        .frame(maxWidth: .infinity)
    }
}

// Primary button: 56pt tall with a 44pt arrow module.
struct PacketButton: View {
    var title: String
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 0) {
                Text(title)
                    .font(PacketFonts.body())
                    .foregroundStyle(Color.buttonText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, 16)
                Rectangle()
                    .fill(Color.buttonText.opacity(0.35))
                    .frame(width: 1)
                    .padding(.vertical, 12)
                Image(systemName: "arrow.right")
                    .foregroundStyle(Color.buttonText)
                    .frame(width: 44)
            }
            .frame(height: 56)
            .background(Color.buttonFill)
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
}

// Status tag: mustard, 24pt tall, Barlow caps.
struct PacketTag: View {
    var text: String

    var body: some View {
        Text(text.uppercased())
            .font(PacketFonts.label())
            .tracking(1.3)
            .foregroundStyle(Color.packetBlack)
            .padding(.horizontal, 12)
            .frame(height: 24)
            .background(Color.packetMustard)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}
