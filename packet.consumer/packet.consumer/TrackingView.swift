import SwiftUI
import MapKit

// Screen 3: live order tracking. Map + status only; no flight plan.
struct TrackingView: View {
    @ObservedObject var state: AppState

    // The shared machine minus its terminal exceptions.
    private static let route: [OrderStatus] = [
        .placed, .accepted, .pickedUp, .loaded, .inFlight, .delivered,
    ]

    private static let stepNames: [OrderStatus: String] = [
        .placed: "Placed",
        .accepted: "Accepted",
        .pickedUp: "Picked up",
        .loaded: "Loaded",
        .inFlight: "In flight",
        .delivered: "Delivered",
    ]

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Tracking")
                            .font(PacketFonts.headline())
                            .foregroundStyle(Color.headlineText)
                        PacketLeadingLines()
                    }
                    if let order = state.activeOrder {
                        statusRow(for: order.status)
                        if order.status == .failed || order.status == .cancelled {
                            Text("This order did not complete.")
                                .font(PacketFonts.body())
                                .foregroundStyle(Color.packetRed)
                        } else {
                            timeline(current: order.status)
                        }
                        // Placeholder map. TODO: bind to DroneLocationService (~1Hz).
                        Map {
                            Marker("Drop-off", coordinate: CLLocationCoordinate2D(latitude: 47.663, longitude: -122.300))
                        }
                        .frame(height: 240)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        Text("Order \(order.id)")
                            .font(PacketFonts.body(size: 13))
                            .foregroundStyle(.secondary)
                    } else {
                        Text("No active order yet.")
                            .font(PacketFonts.body())
                            .foregroundStyle(.secondary)
                        // Placeholder map so layout is reviewable before telemetry lands.
                        Map()
                            .frame(height: 240)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 24)
            }
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func statusRow(for status: OrderStatus) -> some View {
        Group {
            if status == .failed || status == .cancelled {
                Text(status.rawValue.uppercased())
                    .font(PacketFonts.label())
                    .tracking(1.3)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .frame(height: 24)
                    .background(Color.packetRed)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            } else {
                PacketTag(text: Self.stepNames[status, default: status.rawValue])
            }
        }
    }

    private func timeline(current: OrderStatus) -> some View {
        let currentIndex = Self.route.firstIndex(of: current) ?? 0
        return VStack(spacing: 0) {
            ForEach(Array(Self.route.enumerated()), id: \.element) { index, step in
                HStack(spacing: 12) {
                    Circle()
                        .fill(index <= currentIndex ? Color.packetRed : Color.headlineText.opacity(0.2))
                        .frame(width: 10, height: 10)
                    Text(Self.stepNames[step, default: step.rawValue])
                        .font(PacketFonts.body(size: index == currentIndex ? 17 : 15))
                        .foregroundStyle(index <= currentIndex ? Color.bodyText : .secondary)
                    Spacer()
                }
                .padding(.vertical, 6)
            }
        }
    }
}
