import SwiftUI
import MapKit

// Screen 3: live order tracking. Status + map with origin, destination,
// the straight line between them, and the drone's live position.
// The customer app receives drone location only, never the flight plan.
struct TrackingView: View {
    @ObservedObject var state: AppState
    @State private var dronePing: DronePing?
    @State private var cameraPosition: MapCameraPosition = .automatic

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
                        liveMap(for: order)
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
        .task(id: "\(state.useLiveAPI)-\(state.activeOrder?.id ?? "none")") {
            guard let id = state.activeOrder?.id else { return }
            for await updated in state.orderService.watchOrder(id: id) {
                await MainActor.run { state.activeOrder = updated }
            }
        }
        .task(id: "\(state.useLiveAPI)-\(state.activeOrder?.id ?? "none")-\(state.activeOrder?.droneId ?? "none")") {
            guard let order = state.activeOrder else { return }
            await MainActor.run {
                dronePing = nil
                cameraPosition = .region(Self.region(fitting: [order.pickup, order.dropoffPad]))
            }
            guard let droneId = order.droneId else { return }
            for await ping in state.droneLocationService.watchDronePosition(droneId: droneId) {
                await MainActor.run { dronePing = ping }
            }
        }
    }

    /// Straight-line overview: origin marker, destination marker, the line
    /// between them, plus the drone's latest ping when one has arrived.
    private func liveMap(for order: CustomerOrder) -> some View {
        let origin = KnownPads.coords[order.pickup]
        let dest = KnownPads.coords[order.dropoffPad]
        return Map(position: $cameraPosition) {
            if let origin {
                Marker("Pickup (\(order.pickup))", systemImage: "storefront", coordinate: origin)
            }
            if let dest {
                Marker("Drop-off (\(order.dropoffPad))", coordinate: dest)
            }
            if let origin, let dest {
                MapPolyline(coordinates: [origin, dest])
                    .stroke(Color.packetRed, lineWidth: 3)
            }
            if let ping = dronePing {
                Annotation("Drone", coordinate: CLLocationCoordinate2D(
                    latitude: ping.latitude, longitude: ping.longitude)) {
                    ZStack {
                        Circle().fill(Color.blue).frame(width: 30, height: 30)
                        Image(systemName: "paperplane.fill")
                            .foregroundStyle(.white)
                            .font(.caption)
                    }
                }
            }
        }
    }

    /// Frames the origin/destination pair with padding. Unknown pads fall
    /// back to a small region instead of the whole world.
    private static func region(fitting pads: [String]) -> MKCoordinateRegion {
        let coords = pads.compactMap { KnownPads.coords[$0] }
        guard let minLat = coords.map(\.latitude).min(),
              let maxLat = coords.map(\.latitude).max(),
              let minLon = coords.map(\.longitude).min(),
              let maxLon = coords.map(\.longitude).max() else {
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 47.663, longitude: -122.297),
                span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01))
        }
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: (minLat + maxLat) / 2,
                                           longitude: (minLon + maxLon) / 2),
            span: MKCoordinateSpan(latitudeDelta: max((maxLat - minLat) * 1.8, 0.005),
                                   longitudeDelta: max((maxLon - minLon) * 1.8, 0.005)))
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
