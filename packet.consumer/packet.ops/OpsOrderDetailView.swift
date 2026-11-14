import SwiftUI

// Screen 2: one order + the fulfillment buttons. Big touch targets:
// the operator is in a parking lot holding food, not at a desk.
struct OpsOrderDetailView: View {
    @ObservedObject var state: OpsState
    let orderId: String
    @State private var order: CustomerOrder?
    @State private var droneId = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            PacketBand()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let order {
                        header(for: order)
                        if let reason = reasonText(for: order) {
                            Text(reason)
                                .font(PacketFonts.body(size: 13))
                                .foregroundStyle(Color.packetRed)
                        }
                        buttons(for: order)
                    } else {
                        Text("Loading…")
                            .font(PacketFonts.body())
                            .foregroundStyle(.secondary)
                    }
                    if let error {
                        Text(error)
                            .font(PacketFonts.body(size: 13))
                            .foregroundStyle(Color.packetRed)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 24)
            }
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
        .task(id: orderId) {
            droneId = state.defaultDroneId
            for await updated in state.orderService.watchOrder(id: orderId) {
                await MainActor.run { order = updated }
            }
        }
    }

    private func header(for order: CustomerOrder) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                PacketTag(text: order.status.rawValue)
                Spacer()
                Text(String(order.id.suffix(12)))
                    .font(PacketFonts.body(size: 13))
                    .foregroundStyle(.secondary)
            }
            Text("\(order.pickup) → \(order.dropoffPad)")
                .font(PacketFonts.headline(size: 22))
                .foregroundStyle(Color.headlineText)
            Text(order.itemCounts.map { "\($0.value)x \($0.key)" }.joined(separator: ", "))
                .font(PacketFonts.body())
                .foregroundStyle(Color.bodyText)
            if let drone = order.droneId {
                Text("Drone \(drone)")
                    .font(PacketFonts.body(size: 13))
                    .foregroundStyle(.secondary)
            }
            if let cmd = order.commandId {
                Text("Trip \(cmd)")
                    .font(PacketFonts.body(size: 13))
                    .foregroundStyle(.secondary)
            }
        }
    }

    /// The worker stamps dispatch deferrals on the order; surface them verbatim.
    private func reasonText(for order: CustomerOrder) -> String? {
        order.reason
    }

    @ViewBuilder
    private func buttons(for order: CustomerOrder) -> some View {
        switch order.status {
        case .placed:
            TextField("Drone id", text: $droneId)
                .font(PacketFonts.body())
                .padding(12)
                .background(Color.headlineText.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            PacketButton(title: busy ? "Accepting…" : "Accept order") {
                Task { await advance(order, to: .accepted, drone: droneId) }
            }
            .disabled(busy || droneId.isEmpty)
            .opacity(busy || droneId.isEmpty ? 0.5 : 1)
        case .accepted:
            PacketButton(title: busy ? "…" : "Picked up from vendor") {
                Task { await advance(order, to: .pickedUp, drone: nil) }
            }
            .disabled(busy)
        case .pickedUp:
            PacketButton(title: busy ? "…" : "Loaded — release drone") {
                Task { await advance(order, to: .loaded, drone: nil) }
            }
            .disabled(busy)
        case .loaded:
            Text("Flight plan filed, trip released. Watch the fleet map in Phase 2.")
                .font(PacketFonts.body())
                .foregroundStyle(.secondary)
        case .inFlight:
            Text("Drone is flying this order.")
                .font(PacketFonts.body())
                .foregroundStyle(.secondary)
        case .delivered, .failed, .cancelled:
            Text("This order is \(order.status.rawValue).")
                .font(PacketFonts.body())
                .foregroundStyle(.secondary)
        }
    }

    private func advance(_ order: CustomerOrder, to status: OrderStatus, drone: String?) async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            let updated = try await state.orderService.advanceOrder(id: order.id, status: status, droneId: drone)
            await MainActor.run { self.order = updated }
        } catch {
            await MainActor.run { self.error = error.localizedDescription }
        }
    }
}
