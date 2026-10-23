import SwiftUI

struct ContentView: View {
    @StateObject private var state = AppState()

    var body: some View {
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
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
