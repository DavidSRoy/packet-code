import SwiftUI

@main
struct packet_opsApp: App {
    init() {
        PacketFonts.register()
    }

    var body: some Scene {
        WindowGroup {
            OpsContentView()
        }
    }
}
