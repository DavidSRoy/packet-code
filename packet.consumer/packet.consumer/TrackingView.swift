import SwiftUI
import MapKit

// Screen 3: live order tracking. Map + status only; no flight plan.
struct TrackingView: View {
    @ObservedObject var state: AppState

    var body: some View {
        VStack(spacing: 12) {
            if let order = state.activeOrder {
                Text("Status: \(order.status.rawValue)")
                    .font(.headline)
                // Placeholder map. TODO: bind to DroneLocationService (~1Hz).
                Map {
                    Marker("Drop-off", coordinate: CLLocationCoordinate2D(latitude: 47.663, longitude: -122.300))
                }
                .frame(height: 240)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                Text("Order \(order.id)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("No active order yet.")
                    .foregroundStyle(.secondary)
                // Placeholder map so layout is reviewable before telemetry lands.
                Map()
                    .frame(height: 240)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
        .padding()
        .navigationTitle("Tracking")
    }
}
