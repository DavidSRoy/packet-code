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
                OpsFleetView(state: state)
            }
            .tabItem { Label("Fleet", systemImage: "map") }

            NavigationStack {
                OpsSettingsView(state: state)
            }
            .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .tint(.packetRed)
    }
}
