import SwiftUI
import MapKit

// Fleet map: live drone position plus the planned route of every
// non-terminal order assigned to it. Planned-vs-actual in one glance.
struct OpsFleetView: View {
    @ObservedObject var state: OpsState
    @State private var droneId = ""
    @State private var info: DroneStateInfo?
    @State private var routes: [RouteOverlay] = []
    @State private var error: String?
    @State private var cameraPosition: MapCameraPosition = .automatic
    @State private var framed = false

    private struct RouteOverlay: Identifiable {
        let id: String
        let coords: [CLLocationCoordinate2D]
    }

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            VStack(alignment: .leading, spacing: 8) {
                Text("Fleet")
                    .font(PacketFonts.headline())
                    .foregroundStyle(Color.headlineText)
                PacketLeadingLines()
                HStack {
                    TextField("Drone id", text: $droneId)
                        .font(PacketFonts.body())
                        .padding(12)
                        .background(Color.headlineText.opacity(0.06))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    NavigationLink(destination: OpsDroneDetailView(state: state, droneId: droneId)) {
                        PacketTag(text: "Console")
                    }
                    .disabled(droneId.isEmpty)
                }
                statusCard
                if let error {
                    Text(error)
                        .font(PacketFonts.body(size: 13))
                        .foregroundStyle(Color.packetRed)
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            Map(position: $cameraPosition) {
                ForEach(routes) { route in
                    MapPolyline(coordinates: route.coords)
                        .stroke(Color.packetRed, lineWidth: 3)
                }
                if let lat = info?.latitude, let lon = info?.longitude {
                    Annotation("Drone", coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon)) {
                        ZStack {
                            Circle().fill(Color.blue).frame(width: 30, height: 30)
                            Image(systemName: "paperplane.fill")
                                .foregroundStyle(.white)
                                .font(.caption)
                        }
                    }
                }
            }
            .frame(minHeight: 280)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 24)
            Spacer()
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { if droneId.isEmpty { droneId = state.defaultDroneId } }
        .task(id: droneId) {
            framed = false
            cameraPosition = .automatic
            await load()
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await load()
            }
        }
    }

    private var statusCard: some View {
        HStack(spacing: 12) {
            Circle()
                .fill((info?.online ?? false) ? Color.green : Color.gray)
                .frame(width: 10, height: 10)
            if let info {
                Text("Batt \(info.batteryPercent.map(String.init) ?? "?")%")
                    .font(PacketFonts.body(size: 15))
                Text("Pad \(info.currentPad ?? "?")")
                    .font(PacketFonts.body(size: 15))
                if info.controlAllowed == false {
                    Text("CONTROL OFF")
                        .font(PacketFonts.label())
                        .foregroundStyle(Color.packetRed)
                }
            } else {
                Text("No telemetry yet.")
                    .font(PacketFonts.body(size: 15))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button("Recenter") { frameCamera() }
                .font(PacketFonts.label())
        }
    }

    private func load() async {
        guard !droneId.isEmpty else { return }
        do {
            let info = try await state.orderService.fetchDroneState(id: droneId)
            let orders = try await state.orderService.fetchOrders(status: nil)
            let mine = orders.filter {
                $0.droneId == droneId && [.accepted, .pickedUp, .loaded, .inFlight].contains($0.status)
            }
            let overlays: [RouteOverlay] = mine.compactMap { order in
                guard let path = order.flightPlan?.routePath, path.count >= 2 else { return nil }
                return RouteOverlay(
                    id: order.id,
                    coords: path.compactMap { $0.count >= 2
                        ? CLLocationCoordinate2D(latitude: $0[0], longitude: $0[1]) : nil })
            }
            await MainActor.run {
                self.info = info
                self.routes = overlays
                self.error = nil
                if !framed, info.latitude != nil {
                    frameCamera()
                    framed = true
                }
            }
        } catch {
            await MainActor.run { self.error = error.localizedDescription }
        }
    }

    private func frameCamera() {
        var coords = routes.flatMap(\.coords)
        if let lat = info?.latitude, let lon = info?.longitude {
            coords.append(CLLocationCoordinate2D(latitude: lat, longitude: lon))
        }
        guard !coords.isEmpty else { return }
        let lats = coords.map(\.latitude), lons = coords.map(\.longitude)
        cameraPosition = .region(MKCoordinateRegion(
            center: CLLocationCoordinate2D(
                latitude: (lats.min()! + lats.max()!) / 2,
                longitude: (lons.min()! + lons.max()!) / 2),
            span: MKCoordinateSpan(
                latitudeDelta: max((lats.max()! - lats.min()!) * 1.8, 0.005),
                longitudeDelta: max((lons.max()! - lons.min()!) * 1.8, 0.005))))
    }
}
