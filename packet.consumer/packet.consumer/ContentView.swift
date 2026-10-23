import SwiftUI

struct ContentView: View {
    @StateObject private var state = AppState()
    @State private var showSplash = true

    var body: some View {
        ZStack {
            TabView {
            NavigationStack {
                MenuView(state: state)
            }
            .tabItem { Label("Menu", systemImage: "list.bullet") }

            NavigationStack {
                CheckoutView(state: state)
            }
            .tabItem { Label("Checkout", systemImage: "cart") }

            NavigationStack {
                TrackingView(state: state)
            }
            .tabItem { Label("Tracking", systemImage: "map") }
            }
            .tint(.packetRed)
            if showSplash {
                SplashView { showSplash = false }
                    .transition(.opacity)
                    .zIndex(1)
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
