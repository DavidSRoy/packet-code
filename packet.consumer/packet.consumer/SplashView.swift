import SwiftUI

// Splash: emblem sits left of the wordmark and slides right into place
// while the wordmark fades in on the same animation, holds, then exits.
// Always uses the dark-tile language: black tile, white marks, red block.
// Guaranteed on screen for at least 750ms.
struct SplashView: View {
    var onDone: () -> Void

    @State private var emblemOffsetX: CGFloat = -160
    @State private var wordmarkOpacity = 0.0
    @State private var wordmarkScale: CGFloat = 1.25
    @State private var splashOpacity = 1.0

    private static let minVisibleMs: UInt64 = 750

    var body: some View {
        HStack(spacing: 14) {
            PacketEmblemView(markColor: .white, size: 72)
                .offset(x: emblemOffsetX)
            PacketWordmarkView(color: .white, size: 40)
                .opacity(wordmarkOpacity)
                .scaleEffect(wordmarkScale)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.packetBlack)
        .opacity(splashOpacity)
        .task {
            let start = ContinuousClock.now
            withAnimation(.easeOut(duration: 0.6)) {
                emblemOffsetX = 0
                wordmarkOpacity = 1
                wordmarkScale = 1.0
            }
            let elapsed = start.duration(to: .now)
            let remaining = Duration.milliseconds(Int64(Self.minVisibleMs)) - elapsed
            if remaining > .zero {
                try? await Task.sleep(for: remaining)
            }
            // Small hold so the lockup reads before exit.
            try? await Task.sleep(for: .milliseconds(200))
            withAnimation(.easeOut(duration: 0.25)) {
                splashOpacity = 0
            }
            try? await Task.sleep(for: .milliseconds(260))
            onDone()
        }
    }
}
