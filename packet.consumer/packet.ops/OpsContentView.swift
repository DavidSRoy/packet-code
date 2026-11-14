import SwiftUI

struct OpsContentView: View {
    @StateObject private var state = OpsState()

    var body: some View {
        TabView {
            NavigationStack {
                OpsQueueView(state: state)
            }
            .tabItem { Label("Queue", systemImage: "tray.full") }

            NavigationStack {
                OpsSettingsView(state: state)
            }
            .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .tint(.packetRed)
    }
}
